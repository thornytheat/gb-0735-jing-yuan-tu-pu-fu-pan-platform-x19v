from fastapi import APIRouter, Response

from app.dependencies import Archive, Service
from app.modules.corrections.schema import CorrectionRequest

router = APIRouter(prefix="/api/runs/{run_id}/corrections")


def brief(document):
    return {"correction_id": document["correction_id"], "created_at": document["created_at"],
            "records": len(document["records"]), "transitions": len(document["transitions"]),
            "wafers": sorted({step["wafer"] for step in document["transitions"]}),
            "after": document["summary"]["after"]}


@router.get("")
def corrections(archive: Archive, service: Service):
    return [brief(document) for document in service.store.list_corrections(archive[0]["run_id"])]


@router.post("/preview")
def preview(request: CorrectionRequest, service: Service, run_id: str):
    return service.preview_correction(run_id, request.records)


@router.post("", status_code=201)
def publish(request: CorrectionRequest, service: Service, run_id: str, response: Response):
    result = service.publish_correction(run_id, request.records)
    if result["reused"]:
        response.status_code = 200
    return result


@router.get("/{correction_id}")
def correction(archive: Archive, service: Service, correction_id: str):
    return service.store.get_correction(archive[0]["run_id"], correction_id)
