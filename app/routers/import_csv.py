import csv
import datetime
import io
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ErgTest, IntervalPiece, Workout
from app.schemas import ImportResult
from app.utils import parse_split

router = APIRouter(prefix="/import", tags=["import"])

KINDS = {"workout", "test"}
WORKOUT_TYPES = {"steady_state", "intervals", "test", "other"}
COLUMNS = {
    "date",
    "kind",
    "workout_type",
    "meters",
    "time_seconds",
    "split",
    "avg_hr",
    "max_hr",
    "spm",
    "notes",
    "workout_notes",
}


@dataclass
class PlannedPiece:
    meters: int
    time_seconds: float
    avg_hr: int | None
    max_hr: int | None
    spm: float | None
    notes: str | None


@dataclass
class PlannedWorkout:
    date: datetime.date
    workout_type: str
    notes: str | None
    pieces: list[PlannedPiece]


@dataclass
class PlannedTest:
    date: datetime.date
    distance_meters: int
    time_seconds: float
    avg_hr: int | None
    max_hr: int | None
    notes: str | None


def row_error(row_number: int, message: str) -> HTTPException:
    return HTTPException(status_code=422, detail=f"row {row_number}: {message}")


def optional_text(values: dict[str, str], column: str) -> str | None:
    return values.get(column) or None


def parse_optional_hr(
    row_number: int, values: dict[str, str], column: str
) -> int | None:
    value = values.get(column) or ""
    if not value:
        return None
    try:
        number = float(value)
    except ValueError:
        raise row_error(row_number, f"invalid {column}: {value}")
    if number != int(number):
        raise row_error(row_number, f"{column} must be an integer")
    return int(number)


def parse_optional_float(
    row_number: int, values: dict[str, str], column: str
) -> float | None:
    value = values.get(column) or ""
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        raise row_error(row_number, f"invalid {column}: {value}")


def read_rows(text: str) -> list[tuple[int, dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = [name.strip() for name in reader.fieldnames or []]
    unknown = sorted(
        {name for name in fieldnames if name and name not in COLUMNS}
    )
    if unknown:
        raise HTTPException(
            status_code=422, detail=f"unknown columns: {', '.join(unknown)}"
        )
    reader.fieldnames = fieldnames
    rows: list[tuple[int, dict[str, str]]] = []
    for raw in reader:
        if raw.get(None):
            raise row_error(len(rows) + 1, "too many values")
        values = {
            key: (value or "").strip()
            for key, value in raw.items()
            if key is not None
        }
        if not any(values.values()):
            continue
        rows.append((len(rows) + 1, values))
    return rows


def parse_row(row_number: int, values: dict[str, str]) -> PlannedWorkout | PlannedTest:
    date_value = values.get("date") or ""
    if not date_value:
        raise row_error(row_number, "date is required")
    try:
        date = datetime.date.fromisoformat(date_value)
    except ValueError:
        raise row_error(row_number, f"invalid date: {date_value}")

    meters_value = values.get("meters") or ""
    if not meters_value:
        raise row_error(row_number, "meters is required")
    try:
        meters = int(meters_value)
    except ValueError:
        raise row_error(row_number, f"invalid meters: {meters_value}")
    if meters <= 0:
        raise row_error(row_number, "meters must be > 0")

    kind = values.get("kind") or "workout"
    if kind not in KINDS:
        raise row_error(row_number, f"invalid kind: {kind}")

    time_value = values.get("time_seconds") or ""
    split_value = values.get("split") or ""
    if bool(time_value) == bool(split_value):
        raise row_error(
            row_number, "provide exactly one of time_seconds or split"
        )
    if time_value:
        try:
            time_seconds = float(time_value)
        except ValueError:
            raise row_error(row_number, f"invalid time_seconds: {time_value}")
        if time_seconds <= 0:
            raise row_error(row_number, "time_seconds must be > 0")
    else:
        try:
            split_seconds = parse_split(split_value)
        except ValueError:
            raise row_error(row_number, f"invalid split: {split_value}")
        time_seconds = split_seconds * meters / 500.0

    if kind == "test":
        for column in ("workout_type", "spm", "workout_notes"):
            if values.get(column):
                raise row_error(
                    row_number, f"{column} not allowed on test rows"
                )
        return PlannedTest(
            date=date,
            distance_meters=meters,
            time_seconds=time_seconds,
            avg_hr=parse_optional_hr(row_number, values, "avg_hr"),
            max_hr=parse_optional_hr(row_number, values, "max_hr"),
            notes=optional_text(values, "notes"),
        )

    workout_type = values.get("workout_type") or "other"
    if workout_type not in WORKOUT_TYPES:
        raise row_error(row_number, f"invalid workout_type: {workout_type}")
    return PlannedWorkout(
        date=date,
        workout_type=workout_type,
        notes=optional_text(values, "workout_notes"),
        pieces=[
            PlannedPiece(
                meters=meters,
                time_seconds=time_seconds,
                avg_hr=parse_optional_hr(row_number, values, "avg_hr"),
                max_hr=parse_optional_hr(row_number, values, "max_hr"),
                spm=parse_optional_float(row_number, values, "spm"),
                notes=optional_text(values, "notes"),
            )
        ],
    )


def group_rows(
    parsed: list[PlannedWorkout | PlannedTest],
) -> tuple[list[PlannedWorkout], list[PlannedTest]]:
    workouts: list[PlannedWorkout] = []
    tests: list[PlannedTest] = []
    current: PlannedWorkout | None = None
    for item in parsed:
        if isinstance(item, PlannedTest):
            tests.append(item)
            current = None
            continue
        if current is not None and (
            current.date,
            current.workout_type,
        ) == (item.date, item.workout_type):
            current.pieces.extend(item.pieces)
            if current.notes is None:
                current.notes = item.notes
        else:
            workouts.append(item)
            current = item
    return workouts, tests


def build_workout(plan: PlannedWorkout) -> Workout:
    return Workout(
        date=plan.date,
        workout_type=plan.workout_type,
        notes=plan.notes,
        pieces=[
            IntervalPiece(
                sequence=sequence,
                meters=piece.meters,
                time_seconds=piece.time_seconds,
                avg_hr=piece.avg_hr,
                max_hr=piece.max_hr,
                spm=piece.spm,
                notes=piece.notes,
            )
            for sequence, piece in enumerate(plan.pieces, start=1)
        ],
    )


def build_test(plan: PlannedTest) -> ErgTest:
    return ErgTest(
        date=plan.date,
        distance_meters=plan.distance_meters,
        time_seconds=plan.time_seconds,
        avg_hr=plan.avg_hr,
        max_hr=plan.max_hr,
        notes=plan.notes,
    )


@router.post("/csv", response_model=ImportResult)
async def import_csv(
    file: UploadFile, db: Session = Depends(get_db)
) -> ImportResult:
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=422, detail="file must be UTF-8 encoded"
        ) from exc
    parsed = [parse_row(number, values) for number, values in read_rows(text)]
    workouts, tests = group_rows(parsed)
    for plan in workouts:
        db.add(build_workout(plan))
    for plan in tests:
        db.add(build_test(plan))
    db.commit()
    return ImportResult(
        workouts_created=len(workouts),
        tests_created=len(tests),
        pieces_created=sum(len(plan.pieces) for plan in workouts),
    )
