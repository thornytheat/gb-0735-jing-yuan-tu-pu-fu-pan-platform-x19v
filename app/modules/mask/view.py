from app.dependencies import for_wafer
from app.errors import ReviewError
from app.modules.intake.contract import Geometry
from app.modules.mask.geometry import position
from app.modules.retest.arbitrate import cell_key
from app.reasons import REASONS


def grid(snapshot, wafer):
    mask = for_wafer(snapshot["masks"], wafer)
    decisions = snapshot["decisions"][wafer]
    groups = {cell_key(*point): group["id"] for group in snapshot["clusters"][wafer] for point in group["points"]}
    return {"geometry": mask["geometry"], "counts": mask["counts"], "cells": [
        {"x": x, "y": y, "eligibility": eligibility,
         "result": decisions.get(cell_key(x, y), {}).get("result"), "cluster": groups.get(cell_key(x, y))}
        for x, y, eligibility in mask["cells"]
    ]}


def inspect(snapshot, wafer, x, y):
    mask = for_wafer(snapshot["masks"], wafer)
    eligibility = position(Geometry.model_validate(mask["geometry"]), x, y)
    if eligibility == "OUT_OF_GRID":
        raise ReviewError(eligibility, "坐标超出晶圆图", 422)
    rows = [row for row in snapshot["rows"] if row.get("wafer") == wafer
            and row.get("transform", {}).get("canonical") == [x, y]]
    decision = snapshot["decisions"][wafer].get(cell_key(x, y))
    cluster = next((item["id"] for item in snapshot["clusters"][wafer]
                    if any(px == x and py == y for px, py in item["points"])), None)
    return {"wafer": wafer, "x": x, "y": y, "eligibility": eligibility,
            "reason": REASONS.get(eligibility), "decision": decision, "cluster": cluster, "evidence": rows}
