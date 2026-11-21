import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from app.config import DEFAULT_SAMPLE, ROOT, database_path
from app.errors import ReviewError
from app.modules.clusters import handler as clusters
from app.modules.coordinates import handler as coordinates
from app.modules.intake import handler as intake
from app.modules.mask import handler as mask
from app.modules.retest import handler as retest
from app.modules.runs import handler as runs
from app.modules.runs.service import RunService
from app.modules.yield_audit import handler as yield_audit
from app.store import RunStore
from app.web import router as web


def create_app(db=None, seed=True):
    @asynccontextmanager
    async def lifespan(instance):
        await run_in_threadpool(instance.state.runs.store.initialize)
        if seed and not await run_in_threadpool(instance.state.runs.store.list):
            await run_in_threadpool(instance.state.runs.start, DEFAULT_SAMPLE)
        yield

    instance = FastAPI(title="晶圆图谱复判台", lifespan=lifespan)
    instance.state.runs = RunService(RunStore(db or database_path()))
    instance.mount("/static", StaticFiles(directory=ROOT / "app/static"), name="static")
    for module in (intake, coordinates, mask, retest, clusters, yield_audit, runs):
        instance.include_router(module.router)
    instance.include_router(web)
    instance.add_exception_handler(ReviewError, review_error)
    instance.add_exception_handler(sqlite3.Error, storage_error)
    return instance


async def review_error(request: Request, exc: ReviewError):
    return JSONResponse({"code": exc.code, "message": str(exc)}, status_code=exc.status)


async def storage_error(request: Request, exc: sqlite3.Error):
    return JSONResponse({"code": "STORAGE_ERROR", "message": "归档暂不可用，请重试"}, status_code=503)


app = create_app()
