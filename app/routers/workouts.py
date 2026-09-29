import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import services
from app.database import get_db
from app.models import Workout
from app.schemas import QuickLogCreate, WorkoutCreate, WorkoutOut

router = APIRouter(prefix="/workouts", tags=["workouts"])


def get_workout_or_404(db: Session, workout_id: int) -> Workout:
    workout = db.get(Workout, workout_id)
    if workout is None:
        raise HTTPException(status_code=404, detail="workout not found")
    return workout


@router.post("", response_model=WorkoutOut, status_code=201)
def create_workout(data: WorkoutCreate, db: Session = Depends(get_db)) -> Workout:
    return services.create_workout(db, data)


@router.post("/quick-log", response_model=WorkoutOut, status_code=201)
def quick_log(data: QuickLogCreate, db: Session = Depends(get_db)) -> Workout:
    return services.create_workout(db, services.quick_log_to_workout_create(data))


@router.get("", response_model=list[WorkoutOut])
def list_workouts(
    workout_type: str | None = Query(default=None, alias="type"),
    since: datetime.date | None = None,
    until: datetime.date | None = None,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
) -> list[Workout]:
    stmt = select(Workout)
    if workout_type is not None:
        stmt = stmt.where(Workout.workout_type == workout_type)
    if since is not None:
        stmt = stmt.where(Workout.date >= since)
    if until is not None:
        stmt = stmt.where(Workout.date <= until)
    stmt = stmt.order_by(Workout.date.desc(), Workout.id.desc()).limit(limit)
    return list(db.scalars(stmt))


@router.get("/{workout_id}", response_model=WorkoutOut)
def get_workout(workout_id: int, db: Session = Depends(get_db)) -> Workout:
    return get_workout_or_404(db, workout_id)


@router.put("/{workout_id}", response_model=WorkoutOut)
def replace_workout(
    workout_id: int, data: WorkoutCreate, db: Session = Depends(get_db)
) -> Workout:
    workout = get_workout_or_404(db, workout_id)
    workout.date = data.date
    workout.workout_type = data.workout_type
    workout.notes = data.notes
    workout.pieces = [
        services.build_piece(i, piece) for i, piece in enumerate(data.pieces, start=1)
    ]
    db.commit()
    return workout


@router.delete("/{workout_id}", status_code=204)
def delete_workout(workout_id: int, db: Session = Depends(get_db)) -> None:
    workout = get_workout_or_404(db, workout_id)
    db.delete(workout)
    db.commit()
