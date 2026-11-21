import re
import unicodedata
from collections import Counter

from app.reasons import classify

VECTOR = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}
TURNS = {(0, -1): 0, (-1, 0): 1, (0, 1): 2, (1, 0): 3}


def integer(value):
    text = unicodedata.normalize("NFKC", value).strip()
    if not re.fullmatch(r"[+-]?[0-9]{1,7}", text):
        raise ValueError("应为整数")
    return int(text)


def normalize(source, x, y):
    dx = (x - source.origin_x) * (-1 if source.x_left else 1)
    dy = (y - source.origin_y) * (-1 if source.y_down else 1)
    nx, ny = VECTOR[source.notch]
    mirrored = (-dx if source.mirror else dx, dy)
    turns = TURNS[(-nx if source.mirror else nx, ny)]
    cx, cy = mirrored
    for _ in range(turns):
        cx, cy = -cy, cx
    return {"translated": [dx, dy], "mirrored": list(mirrored), "turn_degrees": turns * 90,
            "canonical": [cx, cy]}


def align(spec, rows):
    sources = {source.name: source for source in spec.sources}
    wafers = {geometry.wafer for geometry in spec.wafers}
    for row in rows:
        if row["bucket"] != "candidate":
            continue
        fields = row["fields"]
        row["wafer"] = fields["wafer"].strip()
        if row["wafer"] not in wafers:
            classify(row, "isolated", "UNKNOWN_WAFER")
            continue
        try:
            x, y = integer(fields["x"]), integer(fields["y"])
        except ValueError:
            classify(row, "isolated", "BAD_COORDINATE")
            continue
        row["transform"] = normalize(sources[row["source"]], x, y)
    counts = Counter(row["source"] for row in rows if "transform" in row)
    return [{**source.model_dump(), "aligned": counts[source.name]} for source in spec.sources]
