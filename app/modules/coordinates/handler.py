from typing import Annotated

from fastapi import APIRouter, Query

from app.dependencies import Archive
from app.errors import ReviewError
from app.modules.coordinates.transform import normalize
from app.modules.intake.contract import Source

router = APIRouter(prefix="/api/runs/{run_id}/coordinates")
RawCoordinate = Annotated[int, Query(ge=-9_999_999, le=9_999_999)]


@router.get("")
def coordinates(archive: Archive):
    _, snapshot, _ = archive
    track = [row for row in snapshot["rows"] if "transform" in row]
    rejects = [row for row in snapshot["rows"] if row["code"] in {"BAD_COORDINATE", "UNKNOWN_WAFER"}]
    return {"sources": snapshot["transforms"], "rows": track, "issues": rejects}


@router.get("/probe")
def probe(archive: Archive, source: str, x: RawCoordinate, y: RawCoordinate):
    _, snapshot, _ = archive
    for record in snapshot["transforms"]:
        if record["name"] == source:
            return normalize(Source.model_validate(record), x, y)
    raise ReviewError("SOURCE_NOT_FOUND", "此批次无对应图档", 404)
