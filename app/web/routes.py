import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import services, utils
from app.database import get_db
from app.models import Workout
from app.schemas import ErgTestCreate, QuickLogCreate, StatsOut
from app.web import queries

APP_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = APP_DIR / "static"
TEMPLATES_DIR = APP_DIR / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["web"])

WORKOUT_TYPES = ("steady_state", "intervals", "test", "other")


def distance_label(meters: int) -> str:
    if meters % 1000 == 0:
        return f"{meters // 1000}k"
    return f"{meters}m"


def week_label(week_start: datetime.date) -> str:
    return f"{week_start.strftime('%b')} {week_start.day}"


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    total = int(round(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_hr(avg_hr: float | None) -> str:
    if avg_hr is None:
        return "—"
    return str(int(round(avg_hr)))


def format_decimal(value: float | None) -> str:
    if value is None:
        return "—"
    if value == int(value):
        return str(int(value))
    return f"{value:.1f}"


def format_int_or_dash(value: int | None) -> str:
    return "—" if value is None else str(value)


def workout_tabs(active_type: str | None) -> list[dict[str, Any]]:
    tabs = [{"label": "All", "href": "/ui/workouts", "active": active_type is None}]
    for workout_type in WORKOUT_TYPES:
        tabs.append(
            {
                "label": workout_type,
                "href": f"/ui/workouts?type={workout_type}",
                "active": active_type == workout_type,
            }
        )
    return tabs


def quick_log_defaults() -> dict[str, str]:
    return {
        "date": datetime.date.today().isoformat(),
        "workout_type": "steady_state",
        "meters": "",
        "split": "",
        "total_time": "",
        "avg_hr": "",
        "max_hr": "",
        "spm": "",
        "notes": "",
    }


def erg_test_defaults() -> dict[str, str]:
    return {
        "date": datetime.date.today().isoformat(),
        "distance": "",
        "time": "",
        "avg_hr": "",
        "max_hr": "",
        "notes": "",
    }


def form_value(form: Any, key: str) -> str:
    return str(form.get(key) or "").strip()


def parse_date(value: str) -> datetime.date | None:
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


def parse_number(
    label: str, value: str, converter: Any
) -> tuple[Any, str | None]:
    if not value:
        return None, f"{label} is required."
    try:
        number = converter(value)
    except ValueError:
        return None, f"{label} must be a number."
    if number <= 0:
        return None, f"{label} must be greater than zero."
    return number, None


def parse_optional_number(
    label: str, value: str, converter: Any
) -> tuple[Any, str | None]:
    if not value:
        return None, None
    return parse_number(label, value, converter)


def render_quick_log(
    request: Request,
    quick_values: dict[str, str],
    erg_values: dict[str, str],
    errors: list[str] | None = None,
    active_form: str = "workout",
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="quick_log.html",
        context={
            "quick_values": quick_values,
            "erg_values": erg_values,
            "workout_types": WORKOUT_TYPES,
            "errors": errors or [],
            "active_form": active_form,
        },
    )


def build_chart_data(
    stats: StatsOut,
    hr_points: list[dict[str, Any]],
    progression: dict[int, list[dict[str, Any]]],
) -> dict[str, Any]:
    weekly_meters = {
        "labels": [week_label(week.week_start) for week in stats.weekly_meters],
        "values": [week.meters for week in stats.weekly_meters],
    }
    hr_vs_split = [
        {**point, "split_formatted": utils.format_split(point["split_seconds"])}
        for point in hr_points
    ]
    test_progression = []
    for distance in sorted(progression):
        points = [
            {
                "date": point["date"],
                "split_seconds": point["split_seconds"],
                "split_formatted": utils.format_split(point["split_seconds"]),
                "time_seconds": point["time_seconds"],
                "time_formatted": utils.format_split(point["time_seconds"]),
            }
            for point in progression[distance]
        ]
        test_progression.append(
            {
                "distance_meters": distance,
                "label": distance_label(distance),
                "points": points,
            }
        )
    return {
        "weekly_meters": weekly_meters,
        "hr_vs_split": hr_vs_split,
        "test_progression": test_progression,
    }


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard(
    request: Request, db: Session = Depends(get_db), saved: str = ""
) -> HTMLResponse:
    stats = queries.get_stats(db)
    hr_points = queries.hr_vs_split_points(db)
    progression = queries.test_progression(db)
    best_cards = [
        {
            "label": f"Best {distance_label(test.distance_meters)}",
            "split_formatted": test.split_formatted,
        }
        for test in stats.best_tests[:4]
    ]
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "stats": stats,
            "best_cards": best_cards,
            "has_hr_data": bool(hr_points),
            "has_tests": bool(progression),
            "chart_data": build_chart_data(stats, hr_points, progression),
            "test_saved": saved == "test",
        },
    )


@router.get("/ui/workouts", response_class=HTMLResponse, include_in_schema=False)
def workouts_page(
    request: Request,
    db: Session = Depends(get_db),
    workout_type: str | None = Query(default=None, alias="type"),
    limit: int = Query(default=100, ge=1, le=500),
) -> HTMLResponse:
    rows = queries.list_workout_rows(db, workout_type, limit)
    display_rows = [
        {
            "id": row["id"],
            "date": row["date"],
            "workout_type": row["workout_type"],
            "piece_count": row["piece_count"],
            "total_meters": row["total_meters"],
            "total_time": format_duration(row["total_time_seconds"]),
            "avg_hr": format_hr(row["avg_hr"]),
            "notes": row["notes"] or "—",
        }
        for row in rows
    ]
    return templates.TemplateResponse(
        request=request,
        name="workouts.html",
        context={
            "rows": display_rows,
            "tabs": workout_tabs(workout_type),
        },
    )


@router.get(
    "/ui/workouts/{workout_id}", response_class=HTMLResponse, include_in_schema=False
)
def workout_detail_page(
    request: Request,
    workout_id: int,
    db: Session = Depends(get_db),
    saved: str = "",
) -> HTMLResponse:
    workout = db.get(Workout, workout_id)
    if workout is None:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "heading": "Workout not found",
                "message": f"No workout with id {workout_id} exists.",
            },
            status_code=404,
        )
    pieces = list(workout.pieces)
    piece_rows = []
    for piece in pieces:
        split = utils.split_seconds(piece.time_seconds, piece.meters)
        watts = utils.watts(piece.time_seconds, piece.meters)
        piece_rows.append(
            {
                "sequence": piece.sequence,
                "meters": piece.meters,
                "time": utils.format_split(piece.time_seconds) or "—",
                "split": utils.format_split(split) or "—",
                "watts": f"{watts:.1f}" if watts is not None else "—",
                "avg_hr": format_int_or_dash(piece.avg_hr),
                "max_hr": format_int_or_dash(piece.max_hr),
                "spm": format_decimal(piece.spm),
                "notes": piece.notes or "—",
            }
        )
    totals = {
        "meters": sum(piece.meters for piece in pieces),
        "time": format_duration(sum(piece.time_seconds for piece in pieces)),
        "avg_hr": format_hr(queries.duration_weighted_hr(pieces)),
    }
    return templates.TemplateResponse(
        request=request,
        name="workout_detail.html",
        context={
            "workout": workout,
            "pieces": piece_rows,
            "totals": totals,
            "saved": saved == "1",
        },
    )


@router.get("/ui/quick-log", response_class=HTMLResponse, include_in_schema=False)
def quick_log_page(request: Request) -> HTMLResponse:
    return render_quick_log(request, quick_log_defaults(), erg_test_defaults())


@router.post("/ui/quick-log", response_class=HTMLResponse, include_in_schema=False)
async def quick_log_submit(
    request: Request, db: Session = Depends(get_db)
) -> Response:
    form = await request.form()
    values = {
        "date": form_value(form, "date"),
        "workout_type": form_value(form, "workout_type"),
        "meters": form_value(form, "meters"),
        "split": form_value(form, "split"),
        "total_time": form_value(form, "total_time"),
        "avg_hr": form_value(form, "avg_hr"),
        "max_hr": form_value(form, "max_hr"),
        "spm": form_value(form, "spm"),
        "notes": form_value(form, "notes"),
    }
    errors: list[str] = []

    date = parse_date(values["date"])
    if date is None:
        errors.append("Enter a valid date (YYYY-MM-DD).")

    workout_type = values["workout_type"] or "steady_state"
    if workout_type not in WORKOUT_TYPES:
        errors.append("Choose a valid workout type.")

    meters, error = parse_number("Meters", values["meters"], int)
    if error:
        errors.append(error)

    split_raw = values["split"]
    total_time_raw = values["total_time"]
    if split_raw and total_time_raw:
        errors.append("Fill in Split or Total time, not both.")
    elif not split_raw and not total_time_raw:
        errors.append("Fill in Split or Total time — exactly one.")

    time_seconds: float | None = None
    if split_raw:
        try:
            utils.parse_split(split_raw)
        except ValueError:
            errors.append(f'Could not read split "{split_raw}" — try a format like 2:05.0.')
    if total_time_raw:
        try:
            time_seconds = utils.parse_split(total_time_raw)
        except ValueError:
            errors.append(
                f'Could not read total time "{total_time_raw}" — try a format like 42:30.'
            )

    avg_hr, error = parse_optional_number("Avg HR", values["avg_hr"], int)
    if error:
        errors.append(error)
    max_hr, error = parse_optional_number("Max HR", values["max_hr"], int)
    if error:
        errors.append(error)
    spm, error = parse_optional_number("SPM", values["spm"], float)
    if error:
        errors.append(error)

    if not errors:
        try:
            quick_log = QuickLogCreate(
                date=date,
                workout_type=workout_type,
                meters=meters,
                split=split_raw or None,
                time_seconds=time_seconds if total_time_raw else None,
                avg_hr=avg_hr,
                max_hr=max_hr,
                spm=spm,
                notes=values["notes"] or None,
            )
        except ValidationError:
            errors.append("Could not save the workout — check the values above.")
        else:
            workout = services.create_workout(
                db, services.quick_log_to_workout_create(quick_log)
            )
            return RedirectResponse(
                f"/ui/workouts/{workout.id}?saved=1", status_code=303
            )

    return render_quick_log(
        request,
        values,
        erg_test_defaults(),
        errors=errors,
        active_form="workout",
    )


@router.post("/ui/erg-test", response_class=HTMLResponse, include_in_schema=False)
async def erg_test_submit(
    request: Request, db: Session = Depends(get_db)
) -> Response:
    form = await request.form()
    values = {
        "date": form_value(form, "date"),
        "distance": form_value(form, "distance"),
        "time": form_value(form, "time"),
        "avg_hr": form_value(form, "avg_hr"),
        "max_hr": form_value(form, "max_hr"),
        "notes": form_value(form, "notes"),
    }
    errors: list[str] = []

    date = parse_date(values["date"])
    if date is None:
        errors.append("Enter a valid date (YYYY-MM-DD).")

    distance, error = parse_number("Distance", values["distance"], int)
    if error:
        errors.append(error)

    time_raw = values["time"]
    time_seconds: float | None = None
    if not time_raw:
        errors.append("Time is required.")
    else:
        try:
            time_seconds = utils.parse_split(time_raw)
        except ValueError:
            errors.append(f'Could not read time "{time_raw}" — try a format like 7:52.5.')

    avg_hr, error = parse_optional_number("Avg HR", values["avg_hr"], int)
    if error:
        errors.append(error)
    max_hr, error = parse_optional_number("Max HR", values["max_hr"], int)
    if error:
        errors.append(error)

    if not errors:
        try:
            erg_test = ErgTestCreate(
                date=date,
                distance_meters=distance,
                time_seconds=time_seconds,
                avg_hr=avg_hr,
                max_hr=max_hr,
                notes=values["notes"] or None,
            )
        except ValidationError:
            errors.append("Could not save the test — check the values above.")
        else:
            services.create_erg_test(db, erg_test)
            return RedirectResponse("/?saved=test", status_code=303)

    return render_quick_log(
        request,
        quick_log_defaults(),
        values,
        errors=errors,
        active_form="erg_test",
    )
