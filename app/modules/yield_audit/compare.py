from collections import Counter
from decimal import Decimal, ROUND_HALF_UP

from app.modules.retest.arbitrate import cell_key

STATUSES = {"PASS": "passed", "FAIL": "failed", "PENDING": "pending", "CONFLICT": "conflict"}
COUNT_FIELDS = ("valid", *STATUSES.values())
ROW_BUCKETS = ("accepted", "isolated", "duplicate", "blank", "header")


def percent(numerator, denominator):
    if denominator == 0:
        return None
    return str((Decimal(numerator) * 100 / Decimal(denominator)).quantize(Decimal("0.01"), ROUND_HALF_UP))


def summarize(counts):
    return dict(counts, yield_pct=percent(counts["passed"], counts["valid"]),
                coverage_pct=percent(counts["passed"] + counts["failed"] + counts["conflict"], counts["valid"]))


def compare(spec, masks, decisions, rows, intake):
    ledger = {item.wafer: item.model_dump() for item in spec.ledger}
    wafers = []
    for wafer, mask in masks.items():
        cells = decisions[wafer]
        active = {cell_key(x, y) for x, y, reason in mask["cells"] if reason == "ACTIVE"}
        states = Counter(cell["result"] for cell in cells.values())
        actual = {"valid": len(active), **{field: states[state] for state, field in STATUSES.items()}}
        missing = sorted(active - cells.keys())
        extra = sorted(cells.keys() - active)
        balanced = not missing and not extra and actual["valid"] == sum(actual[field] for field in STATUSES.values())
        reference = ledger.pop(wafer, None)
        delta = {field: actual[field] - reference[field] for field in COUNT_FIELDS} if reference else None
        wafers.append({"wafer": wafer, **summarize(actual), "balanced": balanced, "missing": missing, "extra": extra,
                       "reference": reference, "delta": delta,
                       "status": "MISSING_REFERENCE" if reference is None else "DIFFERENCE" if any(delta.values()) else "MATCH"})

    counts = Counter(row["bucket"] for row in rows)
    declared = sum(item["data_count"] for item in intake)
    row_audit = {"total": len(rows), "declared_data": declared,
                 **{key: counts[key] for key in ROW_BUCKETS}}
    handled = sum(counts[key] for key in ROW_BUCKETS)
    row_audit["balanced"] = len(rows) == handled and declared == handled - counts["blank"] - counts["header"]
    lot = summarize({field: sum(wafer[field] for wafer in wafers) for field in COUNT_FIELDS})
    integrity = row_audit["balanced"] and all(wafer["balanced"] for wafer in wafers)
    status = "UNBALANCED" if not integrity else "REVIEW" if ledger or any(
        wafer["status"] != "MATCH" for wafer in wafers) else "MATCH"
    return {"lot": spec.lot, "summary": lot, "wafers": wafers, "rows": row_audit,
            "unknown_reference": sorted(ledger), "status": status}
