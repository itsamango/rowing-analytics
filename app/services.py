from sqlalchemy.orm import Session

from app.models import ErgTest, IntervalPiece, Workout
from app.schemas import ErgTestCreate, PieceCreate, QuickLogCreate, WorkoutCreate


def build_piece(sequence: int, data: PieceCreate) -> IntervalPiece:
    return IntervalPiece(
        sequence=sequence,
        meters=data.meters,
        time_seconds=data.time_seconds,
        avg_hr=data.avg_hr,
        max_hr=data.max_hr,
        spm=data.spm,
        notes=data.notes,
    )


def quick_log_to_workout_create(data: QuickLogCreate) -> WorkoutCreate:
    return WorkoutCreate(
        date=data.date,
        workout_type=data.workout_type,
        notes=data.notes,
        pieces=[
            PieceCreate(
                meters=data.meters,
                time_seconds=data.time_seconds,
                avg_hr=data.avg_hr,
                max_hr=data.max_hr,
                spm=data.spm,
            )
        ],
    )


def create_workout(db: Session, data: WorkoutCreate) -> Workout:
    workout = Workout(
        date=data.date,
        workout_type=data.workout_type,
        notes=data.notes,
        pieces=[build_piece(i, piece) for i, piece in enumerate(data.pieces, start=1)],
    )
    db.add(workout)
    db.commit()
    return workout


def create_erg_test(db: Session, data: ErgTestCreate) -> ErgTest:
    erg_test = ErgTest(
        date=data.date,
        distance_meters=data.distance_meters,
        time_seconds=data.time_seconds,
        avg_hr=data.avg_hr,
        max_hr=data.max_hr,
        notes=data.notes,
    )
    db.add(erg_test)
    db.commit()
    return erg_test
