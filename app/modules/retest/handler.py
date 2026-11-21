from typing import Literal

from fastapi import APIRouter

from app.dependencies import Archive, for_wafer

router = APIRouter(prefix="/api/runs/{run_id}")


@router.get("/retest/{wafer}")
def retest(archive: Archive, wafer: str, result: Literal["PASS", "FAIL", "PENDING", "CONFLICT"] | None = None):
    snapshot = archive[1]
    cells = for_wafer(snapshot["decisions"], wafer)
    reasons = {"BAD_ATTEMPT", "NO_RESULT", "BAD_RESULT", "BAD_BIN", "SAME_ATTEMPT_CONFLICT", "DUPLICATE_RESULT"}
    return {"cells": [cell for cell in cells.values() if result is None or result == cell["result"]],
            "issues": [row for row in snapshot["rows"] if row.get("wafer") == wafer and row["code"] in reasons]}
