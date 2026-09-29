from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import utils
from app.database import get_db
from app.projections import (
    collect_data_points,
    fit_pace_curve,
    latest_erg_test,
    pauls_split,
    project_regression,
    standard_distances,
)
from app.schemas import ProjectionRow, ProjectionsOut

router = APIRouter(prefix="/projections", tags=["projections"])


@router.get("", response_model=ProjectionsOut)
def get_projections(
    distance: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ProjectionsOut:
    fit = fit_pace_curve(collect_data_points(db))
    reference = latest_erg_test(db)
    reference_split = (
        utils.split_seconds(reference.time_seconds, reference.distance_meters)
        if reference is not None
        else None
    )
    distances = [distance] if distance is not None else standard_distances
    rows = []
    for meters in distances:
        row = ProjectionRow(meters=meters)
        if fit is not None:
            split = project_regression(fit, meters)
            row.regression_split_seconds = split
            row.regression_split_formatted = utils.format_split(split)
            row.regression_watts = utils.watts(split * meters / 500.0, meters)
        if reference_split is not None:
            split = pauls_split(reference.distance_meters, reference_split, meters)
            row.pauls_split_seconds = split
            row.pauls_split_formatted = utils.format_split(split)
            row.pauls_watts = utils.watts(split * meters / 500.0, meters)
        rows.append(row)
    pauls_reference = None
    if reference is not None and reference_split is not None:
        pauls_reference = {
            "id": reference.id,
            "date": reference.date,
            "distance_meters": reference.distance_meters,
            "split_seconds": reference_split,
        }
    return ProjectionsOut(model=fit, pauls_reference=pauls_reference, rows=rows)
