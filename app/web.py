from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import ROOT

router = APIRouter()
templates = Jinja2Templates(directory=ROOT / "app/templates")
PAGES = {
    "mask": ("有效芯粒", "/", "▦"),
    "intake": ("图档采信", "/intake", "▤"),
    "coordinates": ("坐标对表", "/coordinates", "⊕"),
    "retest": ("复测裁决", "/retest", "≋"),
    "clusters": ("缺陷簇", "/clusters", "▧"),
    "yield": ("良率勾稽", "/yield", "≡"),
    "runs": ("图批复盘", "/runs", "▣"),
}
NAV = ("intake", "coordinates", "mask", "retest", "clusters", "yield", "runs")


@router.get("/healthz", include_in_schema=False)
def health():
    return {"status": "ok"}


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
@router.get("/intake", response_class=HTMLResponse, include_in_schema=False)
@router.get("/coordinates", response_class=HTMLResponse, include_in_schema=False)
@router.get("/retest", response_class=HTMLResponse, include_in_schema=False)
@router.get("/clusters", response_class=HTMLResponse, include_in_schema=False)
@router.get("/yield", response_class=HTMLResponse, include_in_schema=False)
@router.get("/runs", response_class=HTMLResponse, include_in_schema=False)
def workspace(request: Request):
    stage = request.url.path.strip("/") or "mask"
    return templates.TemplateResponse(request, "base.html", {"stage": stage, "pages": PAGES, "nav": NAV})
