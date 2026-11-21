from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.dependencies import Archive, Service
from app.modules.runs.bundle import make_bundle

router = APIRouter(prefix="/api/runs")


class RunRequest(BaseModel):
    sample: str


@router.get("")
def runs(service: Service):
    return service.store.list()


@router.post("", status_code=201)
def start(request: RunRequest, service: Service, response: Response):
    result = service.start(request.sample)
    if result["reused"]:
        response.status_code = 200
    return result


@router.post("/{run_id}/rerun")
def rerun(run_id: str, service: Service):
    return service.rerun(run_id)


@router.get("/{run_id}")
def run(archive: Archive):
    return archive[0]


@router.get("/{run_id}/export")
def export_bundle(archive: Archive):
    filename = f'wafer-{archive[0]["run_id"][:16]}.json'
    return Response(make_bundle(archive), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
