from fastapi import APIRouter

from app.dependencies import Archive

router = APIRouter(prefix="/api/runs/{run_id}")


@router.get("/yield")
def reconciliation(archive: Archive):
    snapshot = archive[1]
    return {**snapshot["audit"], "reasons": snapshot["reasons"],
            "isolated": [row for row in snapshot["rows"] if row["bucket"] == "isolated"]}
