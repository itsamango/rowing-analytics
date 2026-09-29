from __future__ import annotations

import datetime

from sqlalchemy import Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Workout(Base):
    __tablename__ = "workouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    workout_type: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    pieces: Mapped[list[IntervalPiece]] = relationship(
        back_populates="workout",
        cascade="all, delete-orphan",
        order_by="IntervalPiece.sequence",
    )


class IntervalPiece(Base):
    __tablename__ = "interval_pieces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workout_id: Mapped[int] = mapped_column(ForeignKey("workouts.id"))
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    meters: Mapped[int] = mapped_column(Integer, nullable=False)
    time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    avg_hr: Mapped[int | None] = mapped_column(Integer)
    max_hr: Mapped[int | None] = mapped_column(Integer)
    spm: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)

    workout: Mapped[Workout] = relationship(back_populates="pieces")


class ErgTest(Base):
    __tablename__ = "erg_tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    distance_meters: Mapped[int] = mapped_column(Integer, nullable=False)
    time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    avg_hr: Mapped[int | None] = mapped_column(Integer)
    max_hr: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
