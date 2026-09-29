from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import services
from app.database import get_db
from app.models import ErgTest
from app.schemas import ErgTestCreate, ErgTestOut

router = APIRouter(prefix="/erg-tests", tags=["erg-tests"])


def get_erg_test_or_404(db: Session, erg_test_id: int) -> ErgTest:
    erg_test = db.get(ErgTest, erg_test_id)
    if erg_test is None:
        raise HTTPException(status_code=404, detail="erg test not found")
    return erg_test


@router.post("", response_model=ErgTestOut, status_code=201)
def create_erg_test(data: ErgTestCreate, db: Session = Depends(get_db)) -> ErgTest:
    return services.create_erg_test(db, data)


@router.get("", response_model=list[ErgTestOut])
def list_erg_tests(
    distance: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ErgTest]:
    stmt = select(ErgTest)
    if distance is not None:
        stmt = stmt.where(ErgTest.distance_meters == distance)
    stmt = stmt.order_by(ErgTest.date.desc(), ErgTest.id.desc())
    return list(db.scalars(stmt))


@router.get("/best", response_model=ErgTestOut)
def get_best_erg_test(distance: int, db: Session = Depends(get_db)) -> ErgTest:
    stmt = (
        select(ErgTest)
        .where(ErgTest.distance_meters == distance)
        .order_by(ErgTest.time_seconds.asc(), ErgTest.date.desc(), ErgTest.id.desc())
        .limit(1)
    )
    erg_test = db.scalars(stmt).first()
    if erg_test is None:
        raise HTTPException(status_code=404, detail=f"no erg test at distance {distance}")
    return erg_test


@router.get("/{erg_test_id}", response_model=ErgTestOut)
def get_erg_test(erg_test_id: int, db: Session = Depends(get_db)) -> ErgTest:
    return get_erg_test_or_404(db, erg_test_id)


@router.put("/{erg_test_id}", response_model=ErgTestOut)
def replace_erg_test(
    erg_test_id: int, data: ErgTestCreate, db: Session = Depends(get_db)
) -> ErgTest:
    erg_test = get_erg_test_or_404(db, erg_test_id)
    erg_test.date = data.date
    erg_test.distance_meters = data.distance_meters
    erg_test.time_seconds = data.time_seconds
    erg_test.avg_hr = data.avg_hr
    erg_test.max_hr = data.max_hr
    erg_test.notes = data.notes
    db.commit()
    return erg_test


@router.delete("/{erg_test_id}", status_code=204)
def delete_erg_test(erg_test_id: int, db: Session = Depends(get_db)) -> None:
    erg_test = get_erg_test_or_404(db, erg_test_id)
    db.delete(erg_test)
    db.commit()
