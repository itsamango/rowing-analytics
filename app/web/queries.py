import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import utils
from app.models import ErgTest, IntervalPiece, Workout
from app.schemas import StatsOut, WeeklyMeters


def week_start(date: datetime.date) -> datetime.date:
    return date - datetime.timedelta(days=date.weekday())


def duration_weighted_hr(pieces: list[IntervalPiece]) -> float | None:
    hr_pieces = [piece for piece in pieces if piece.avg_hr is not None]
    if not hr_pieces:
        return None
    hr_time = sum(piece.time_seconds for piece in hr_pieces)
    return sum(piece.avg_hr * piece.time_seconds for piece in hr_pieces) / hr_time


def get_stats(db: Session) -> StatsOut:
    workouts = list(db.scalars(select(Workout)))
    pieces = list(db.scalars(select(IntervalPiece)))
    tests = list(db.scalars(select(ErgTest)))

    total_meters = sum(piece.meters for piece in pieces)
    total_time_seconds = sum(piece.time_seconds for piece in pieces)
    avg_hr = duration_weighted_hr(pieces)

    current_week = week_start(datetime.date.today())
    week_starts = [
        current_week - datetime.timedelta(weeks=ago) for ago in range(7, -1, -1)
    ]
    meters_by_week = {start: 0 for start in week_starts}
    workout_dates = {workout.id: workout.date for workout in workouts}
    for piece in pieces:
        date = workout_dates.get(piece.workout_id)
        if date is None:
            continue
        start = week_start(date)
        if start in meters_by_week:
            meters_by_week[start] += piece.meters

    best_by_distance: dict[int, ErgTest] = {}
    for test in tests:
        best = best_by_distance.get(test.distance_meters)
        if best is None or test.time_seconds < best.time_seconds:
            best_by_distance[test.distance_meters] = test

    return StatsOut(
        total_workouts=len(workouts),
        total_pieces=len(pieces),
        total_tests=len(tests),
        total_meters=total_meters,
        total_time_seconds=total_time_seconds,
        avg_hr=avg_hr,
        weekly_meters=[
            WeeklyMeters(week_start=start, meters=meters_by_week[start])
            for start in week_starts
        ],
        best_tests=[
            best_by_distance[distance] for distance in sorted(best_by_distance)
        ],
    )


def list_workout_rows(
    db: Session, workout_type: str | None = None, limit: int = 100
) -> list[dict[str, Any]]:
    stmt = select(Workout)
    if workout_type is not None:
        stmt = stmt.where(Workout.workout_type == workout_type)
    stmt = stmt.order_by(Workout.date.desc(), Workout.id.desc()).limit(limit)
    rows: list[dict[str, Any]] = []
    for workout in db.scalars(stmt):
        pieces = list(workout.pieces)
        rows.append(
            {
                "id": workout.id,
                "date": workout.date,
                "workout_type": workout.workout_type,
                "piece_count": len(pieces),
                "total_meters": sum(piece.meters for piece in pieces),
                "total_time_seconds": sum(piece.time_seconds for piece in pieces),
                "avg_hr": duration_weighted_hr(pieces),
                "notes": workout.notes,
            }
        )
    return rows


def hr_vs_split_points(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(
        select(IntervalPiece, Workout)
        .join(Workout, IntervalPiece.workout_id == Workout.id)
        .where(IntervalPiece.avg_hr.is_not(None))
        .order_by(Workout.date, IntervalPiece.workout_id, IntervalPiece.sequence)
    ).all()
    points: list[dict[str, Any]] = []
    for piece, workout in rows:
        split = utils.split_seconds(piece.time_seconds, piece.meters)
        if split is None:
            continue
        points.append(
            {
                "date": workout.date.isoformat(),
                "workout_type": workout.workout_type,
                "meters": piece.meters,
                "split_seconds": split,
                "avg_hr": piece.avg_hr,
            }
        )
    return points


def test_progression(db: Session) -> dict[int, list[dict[str, Any]]]:
    tests = db.scalars(select(ErgTest).order_by(ErgTest.date, ErgTest.id)).all()
    progression: dict[int, list[dict[str, Any]]] = {}
    for test in tests:
        split = utils.split_seconds(test.time_seconds, test.distance_meters)
        if split is None:
            continue
        progression.setdefault(test.distance_meters, []).append(
            {
                "date": test.date.isoformat(),
                "split_seconds": split,
                "time_seconds": test.time_seconds,
            }
        )
    return progression
