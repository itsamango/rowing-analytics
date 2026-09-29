import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from app import utils

WorkoutType = Literal["steady_state", "intervals", "test", "other"]


class PieceCreate(BaseModel):
    meters: int
    time_seconds: float
    avg_hr: int | None = None
    max_hr: int | None = None
    spm: float | None = None
    notes: str | None = None


class PieceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sequence: int
    meters: int
    time_seconds: float
    avg_hr: int | None = None
    max_hr: int | None = None
    spm: float | None = None
    notes: str | None = None

    @computed_field
    @property
    def split_seconds(self) -> float | None:
        return utils.split_seconds(self.time_seconds, self.meters)

    @computed_field
    @property
    def split_formatted(self) -> str | None:
        return utils.format_split(utils.split_seconds(self.time_seconds, self.meters))

    @computed_field
    @property
    def watts(self) -> float | None:
        return utils.watts(self.time_seconds, self.meters)


class WorkoutCreate(BaseModel):
    date: datetime.date
    workout_type: WorkoutType
    notes: str | None = None
    pieces: list[PieceCreate] = Field(default_factory=list)


class WorkoutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: datetime.date
    workout_type: WorkoutType
    notes: str | None = None
    pieces: list[PieceOut] = Field(default_factory=list)

    @computed_field
    @property
    def total_meters(self) -> int | None:
        return sum(piece.meters for piece in self.pieces) if self.pieces else None

    @computed_field
    @property
    def total_time_seconds(self) -> float | None:
        return sum(piece.time_seconds for piece in self.pieces) if self.pieces else None


class QuickLogCreate(BaseModel):
    date: datetime.date = Field(default_factory=datetime.date.today)
    workout_type: WorkoutType = "steady_state"
    meters: int = Field(gt=0)
    time_seconds: float | None = Field(default=None, gt=0)
    split: str | None = None
    avg_hr: int | None = None
    max_hr: int | None = None
    spm: float | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def resolve_time(self) -> "QuickLogCreate":
        if (self.time_seconds is None) == (self.split is None):
            raise ValueError("provide exactly one of time_seconds or split")
        if self.split is not None:
            self.time_seconds = utils.parse_split(self.split) * self.meters / 500.0
        return self


class ErgTestCreate(BaseModel):
    date: datetime.date
    distance_meters: int
    time_seconds: float
    avg_hr: int | None = None
    max_hr: int | None = None
    notes: str | None = None


class ImportResult(BaseModel):
    workouts_created: int
    tests_created: int
    pieces_created: int


class ErgTestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: datetime.date
    distance_meters: int
    time_seconds: float
    avg_hr: int | None = None
    max_hr: int | None = None
    notes: str | None = None

    @computed_field
    @property
    def split_formatted(self) -> str | None:
        return utils.format_split(
            utils.split_seconds(self.time_seconds, self.distance_meters)
        )


class PaceModelOut(BaseModel):
    a: float
    b: float
    r2: float
    n_points: int
    n_distinct_distances: int


class PaulsReferenceOut(BaseModel):
    id: int
    date: datetime.date
    distance_meters: int
    split_seconds: float


class ProjectionRow(BaseModel):
    meters: int
    regression_split_seconds: float | None = None
    regression_split_formatted: str | None = None
    regression_watts: float | None = None
    pauls_split_seconds: float | None = None
    pauls_split_formatted: str | None = None
    pauls_watts: float | None = None


class ProjectionsOut(BaseModel):
    model: PaceModelOut | None = None
    pauls_reference: PaulsReferenceOut | None = None
    rows: list[ProjectionRow] = Field(default_factory=list)


class WeeklyMeters(BaseModel):
    week_start: datetime.date
    meters: int


class StatsOut(BaseModel):
    total_workouts: int
    total_pieces: int
    total_tests: int
    total_meters: int
    total_time_seconds: float
    avg_hr: float | None
    weekly_meters: list[WeeklyMeters] = Field(default_factory=list)
    best_tests: list[ErgTestOut] = Field(default_factory=list)
