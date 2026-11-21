from typing import Annotated

from fastapi import Depends, Request

from app.errors import ReviewError


def run_service(request: Request):
    return request.app.state.runs


def run_archive(run_id: str, request: Request):
    return request.app.state.runs.store.get(run_id)


Service = Annotated[object, Depends(run_service)]
Archive = Annotated[tuple, Depends(run_archive)]


def for_wafer(mapping, wafer):
    if wafer not in mapping:
        raise ReviewError("WAFER_NOT_FOUND", "此批次无对应晶圆", 404)
    return mapping[wafer]
