from collections import defaultdict
from datetime import datetime, timezone

from app.config import CORRECTION_VERSION
from app.errors import ReviewError
from app.manifest import canonical, digest
from app.modules.retest.arbitrate import cell_key
from app.modules.yield_audit.compare import COUNT_FIELDS, STATUSES, summarize

HELD_RESULTS = ("FAIL", "PENDING", "CONFLICT")


def release_state(result):
    return "RELEASABLE" if result == "PASS" else "HELD"


def normalize(records):
    """同批更正在内容相同时只保留一份，排序后得到确定性的版本标识。"""
    unique = {tuple(record.model_dump().values()): record for record in records}
    return sorted(unique.values(),
                  key=lambda r: (r.wafer, r.x, r.y, r.attempt, r.result, r.bin, r.note))


def validate(record, decisions, attempts):
    if record.wafer not in decisions:
        raise ReviewError("CORRECTION_UNKNOWN_WAFER", f"晶圆 {record.wafer} 不在本批", 422)
    if (record.result == "PASS") != (record.bin == 1):
        raise ReviewError("CORRECTION_BAD_BIN", "分档与判定不符：通过为 1，失败为 2–999", 422)
    cell = decisions[record.wafer].get(cell_key(record.x, record.y))
    if cell is None:
        raise ReviewError("CORRECTION_CELL_NOT_ACTIVE",
                          f"({record.x}, {record.y}) 不是 {record.wafer} 的有效芯粒", 422)
    key = (record.wafer, record.x, record.y)
    latest = attempts.setdefault(key, max((step["attempt"] for step in cell["history"]), default=0))
    if record.attempt == latest:
        raise ReviewError("CORRECTION_ATTEMPT_CONFLICT",
                          f"测次 T{record.attempt} 已存在，迟到复测须使用更新测次", 422)
    if record.attempt < latest:
        raise ReviewError("CORRECTION_STALE_ATTEMPT",
                          f"测次 T{record.attempt} 不新于现有测次 T{latest}，无法更正", 422)
    attempts[key] = record.attempt
    return cell


def build_correction(manifest, snapshot, records):
    """按迟到复测推导放行更正，不改写原图批，只生成可追溯的新版本文档。"""
    records = normalize(records)
    decisions = snapshot["decisions"]
    attempts = {}
    groups = defaultdict(list)
    cells = {}
    for record in records:
        cells[(record.wafer, record.x, record.y)] = validate(record, decisions, attempts)
        groups[(record.wafer, record.x, record.y)].append(record)

    transitions = []
    overrides = defaultdict(dict)
    for key, group in sorted(groups.items()):
        wafer, x, y = key
        cell = cells[key]
        late = [{"attempt": r.attempt, "result": r.result, "bin": r.bin, "evidence": [], "late": True}
                for r in group]
        final = group[-1]
        before = {"result": cell["result"], "attempt": cell["attempt"], "bin": cell["bin"]}
        after = {"result": final.result, "attempt": final.attempt, "bin": final.bin}
        overrides[wafer][cell_key(x, y)] = final.result
        transitions.append({"wafer": wafer, "x": x, "y": y, "before": before, "after": after,
                            "release_before": release_state(before["result"]),
                            "release_after": release_state(after["result"]),
                            "history_before": cell["history"], "history_after": cell["history"] + late})

    audit = {wafer["wafer"]: wafer for wafer in snapshot["audit"]["wafers"]}
    wafers = []
    for wafer, cells_by_key in decisions.items():
        reference = audit[wafer]["reference"]
        before = {field: audit[wafer][field] for field in COUNT_FIELDS}
        after = dict(before)
        disposition = []
        for key, cell in cells_by_key.items():
            original, revised = cell["result"], overrides[wafer].get(key, cell["result"])
            if revised != original:
                after[STATUSES[original]] -= 1
                after[STATUSES[revised]] += 1
            disposition.append((cell["x"], cell["y"], revised))
        disposition.sort(key=lambda item: (-item[1], item[0]))
        delta_after = ({field: after[field] - reference[field] for field in COUNT_FIELDS}
                       if reference else None)
        wafers.append({"wafer": wafer, "before": summarize(before), "after": summarize(after),
                       "reference": reference, "delta_before": audit[wafer]["delta"], "delta_after": delta_after,
                       "releasable_after": [{"x": x, "y": y} for x, y, result in disposition if result == "PASS"],
                       "held_after": [{"x": x, "y": y, "result": result}
                                      for x, y, result in disposition if result in HELD_RESULTS]})

    lot = {side: summarize({field: sum(wafer[side][field] for wafer in wafers) for field in COUNT_FIELDS})
           for side in ("before", "after")}
    identity = canonical([CORRECTION_VERSION, manifest["run_id"],
                          [record.model_dump() for record in records]])
    return {"correction_id": digest(identity.encode()), "correction_version": CORRECTION_VERSION,
            "run_id": manifest["run_id"], "rule_version": manifest["rule_version"],
            "base_result_sha256": manifest["result_sha256"], "lot": manifest["lot"],
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "records": [record.model_dump() for record in records],
            "transitions": transitions, "wafers": wafers, "summary": lot}
