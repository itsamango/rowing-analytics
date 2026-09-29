import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ErgTest, IntervalPiece, Workout
from app.schemas import StatsOut, WeeklyMeters

router = APIRouter(prefix="/stats", tags=["stats"])


def week_start(date: datetime.date) -> datetime.date:
    return date - datetime.timedelta(days=date.weekday())


@router.get("", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)) -> StatsOut:
    workouts = list(db.scalars(select(Workout)))
    pieces = list(db.scalars(select(IntervalPiece)))
    tests = list(db.scalars(select(ErgTest)))

    total_meters = sum(piece.meters for piece in pieces)
    total_time_seconds = sum(piece.time_seconds for piece in pieces)

    hr_pieces = [piece for piece in pieces if piece.avg_hr is not None]
    if hr_pieces:
        hr_time = sum(piece.time_seconds for piece in hr_pieces)
        avg_hr = sum(piece.avg_hr * piece.time_seconds for piece in hr_pieces) / hr_time
    else:
        avg_hr = None

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
