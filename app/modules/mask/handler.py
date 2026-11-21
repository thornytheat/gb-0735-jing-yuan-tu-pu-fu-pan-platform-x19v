from fastapi import APIRouter

from app.dependencies import Archive
from app.modules.mask.view import grid, inspect

router = APIRouter(prefix="/api/runs/{run_id}/mask")


@router.get("/{wafer}")
def mask(archive: Archive, wafer: str):
    return grid(archive[1], wafer)


@router.get("/{wafer}/cell")
def cell(archive: Archive, wafer: str, x: int, y: int):
    return inspect(archive[1], wafer, x, y)
