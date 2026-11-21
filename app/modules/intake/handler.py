from fastapi import APIRouter

from app.dependencies import Archive
from app.modules.intake.catalog import CATALOG

router = APIRouter(prefix="/api")


@router.get("/samples")
def samples():
    return [{"id": key, "label": label} for key, label in CATALOG.items()]


@router.get("/runs/{run_id}/intake")
def intake(archive: Archive):
    _, snapshot, _ = archive
    excluded = {"BLANK_ROW", "REPEATED_HEADER", "COLUMN_COUNT"}
    return {"files": snapshot["files"], "issues": [row for row in snapshot["rows"] if row["code"] in excluded]}
