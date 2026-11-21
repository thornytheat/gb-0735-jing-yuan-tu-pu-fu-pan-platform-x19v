from collections import defaultdict

from app.modules.retest.measurements import measure
from app.reasons import classify


def cell_key(x, y):
    return f"{x},{y}"


def decide(attempts):
    history = []
    for attempt, rows in sorted(attempts.items()):
        ordered = sorted(rows, key=lambda row: (row["source"], row["line"]))
        values = {(row["measurement"]["result"], row["measurement"]["bin"]) for row in ordered}
        result, bin_code = next(iter(values)) if len(values) == 1 else ("CONFLICT", None)
        if result == "CONFLICT":
            for row in ordered:
                classify(row, "isolated", "SAME_ATTEMPT_CONFLICT")
        else:
            ordered[0]["bucket"] = "accepted"
            for row in ordered[1:]:
                classify(row, "duplicate", "DUPLICATE_RESULT")
        history.append({"attempt": attempt, "result": result, "bin": bin_code,
                        "evidence": [row["id"] for row in ordered]})
    return {**history[-1], "history": history}


def arbitrate(masks, rows):
    measurements = defaultdict(lambda: defaultdict(list))
    evidence = defaultdict(list)
    for row in rows:
        if "transform" not in row:
            continue
        key = (row["wafer"], *row["transform"]["canonical"])
        evidence[key].append(row["id"])
        if row["bucket"] == "candidate":
            value = measure(row)
            if value is not None:
                measurements[key][value[0]].append(row)

    results = {}
    for wafer, mask in masks.items():
        cells = {}
        for x, y, eligibility in mask["cells"]:
            key = (wafer, x, y)
            incoming = evidence.get(key, [])
            if eligibility == "ACTIVE":
                attempts = measurements.get(key)
                decision = decide(attempts) if attempts else {"result": "PENDING", "attempt": None,
                                                               "bin": None, "evidence": [], "history": []}
                cells[cell_key(x, y)] = {"x": x, "y": y, **decision, "sources": incoming}
        results[wafer] = cells
    return results
