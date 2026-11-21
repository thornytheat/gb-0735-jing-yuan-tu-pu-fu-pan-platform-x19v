from collections import Counter

from app.reasons import classify


def position(geometry, x, y):
    r = geometry.radius
    if max(abs(x), abs(y)) > r:
        return "OUT_OF_GRID"
    square_distance = x * x + y * y
    if square_distance > r * r:
        return "OUTSIDE_DISC"
    if geometry.notch_depth and y <= -r + geometry.notch_depth and abs(x) <= geometry.notch_half_width:
        return "NOTCH_VOID"
    if square_distance > (r - geometry.edge) ** 2:
        return "EDGE_EXCLUSION"
    return "ACTIVE"


def make_mask(geometry):
    coords = range(-geometry.radius, geometry.radius + 1)
    cells = [(x, y, position(geometry, x, y)) for y in reversed(coords) for x in coords]
    counts = Counter(cell[2] for cell in cells)
    return {"geometry": geometry.model_dump(), "cells": cells, "counts": dict(counts)}


def screen(spec, rows):
    geometries = {geometry.wafer: geometry for geometry in spec.wafers}
    for row in rows:
        if row["bucket"] != "candidate":
            continue
        reason = position(geometries[row["wafer"]], *row["transform"]["canonical"])
        if reason != "ACTIVE":
            classify(row, "isolated", reason)
    return {wafer: make_mask(geometry) for wafer, geometry in geometries.items()}
