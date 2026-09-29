import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import utils
from app.models import ErgTest, IntervalPiece

standard_distances = [500, 1000, 2000, 5000, 6000, 10000, 21097, 42195]


def fit_pace_curve(points: list[tuple[float, float]]) -> dict | None:
    distinct_distances = {meters for meters, _ in points}
    if len(distinct_distances) < 2:
        return None
    n = len(points)
    xs = [math.log2(meters) for meters, _ in points]
    ys = [split for _, split in points]
    xbar = sum(xs) / n
    ybar = sum(ys) / n
    sxx = sum((x - xbar) ** 2 for x in xs)
    syy = sum((y - ybar) ** 2 for y in ys)
    sxy = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys))
    if sxx == 0:
        return None
    b = sxy / sxx
    a = ybar - b * xbar
    if syy == 0:
        r2 = 1.0 if b == 0 else 0.0
    else:
        r2 = sxy * sxy / (sxx * syy)
    return {
        "a": a,
        "b": b,
        "r2": r2,
        "n_points": n,
        "n_distinct_distances": len(distinct_distances),
    }


def project_regression(fit: dict, meters: float) -> float:
    return fit["a"] + fit["b"] * math.log2(meters)


def pauls_split(
    ref_meters: float,
    ref_split: float,
    meters: float,
    seconds_per_doubling: float = 5.0,
) -> float:
    return ref_split + seconds_per_doubling * math.log2(meters / ref_meters)


def collect_data_points(db: Session) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for piece in db.scalars(select(IntervalPiece).where(IntervalPiece.meters >= 100)):
        split = utils.split_seconds(piece.time_seconds, piece.meters)
        if split is not None:
            points.append((float(piece.meters), split))
    for test in db.scalars(select(ErgTest)):
        split = utils.split_seconds(test.time_seconds, test.distance_meters)
        if split is not None:
            points.append((float(test.distance_meters), split))
    return points


def latest_erg_test(db: Session) -> ErgTest | None:
    stmt = select(ErgTest).order_by(ErgTest.date.desc(), ErgTest.id.desc()).limit(1)
    return db.scalars(stmt).first()
