from fastapi import APIRouter

from app.dependencies import Archive, for_wafer
from app.errors import ReviewError

router = APIRouter(prefix="/api/runs/{run_id}/clusters")


@router.get("/{wafer}")
def clusters(archive: Archive, wafer: str):
    return for_wafer(archive[1]["clusters"], wafer)


@router.get("/{wafer}/{group_id}")
def cluster(archive: Archive, wafer: str, group_id: str):
    snapshot = archive[1]
    for group in for_wafer(snapshot["clusters"], wafer):
        if group["id"] == group_id:
            ids = set(group["evidence"])
            return {**group, "rows": [row for row in snapshot["rows"] if row["id"] in ids]}
    raise ReviewError("CLUSTER_NOT_FOUND", "缺陷簇未找到", 404)
