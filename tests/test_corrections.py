import json
from concurrent.futures import ThreadPoolExecutor

import pytest


def fail_cell(client, run_base, wafer="W-08"):
    cells = client.get(f"{run_base}/retest/{wafer}?result=FAIL").json()["cells"]
    cell = sorted(cells, key=lambda item: (item["x"], item["y"]))[0]
    return {"wafer": wafer, "x": cell["x"], "y": cell["y"], "attempt": cell["attempt"] + 1,
            "result": "PASS", "bin": 1, "note": "迟到复测"}


def publish(client, run_base, records):
    return client.post(run_base + "/corrections", json={"records": records})


def test_preview_shows_release_flip_and_delta_change_without_persisting(client, run_base):
    record = fail_cell(client, run_base)
    response = client.post(run_base + "/corrections/preview", json={"records": [record]})
    assert response.status_code == 200, response.text
    document = response.json()
    transition = document["transitions"][0]
    assert (transition["before"]["result"], transition["after"]["result"]) == ("FAIL", "PASS")
    assert (transition["release_before"], transition["release_after"]) == ("HELD", "RELEASABLE")
    wafer = next(item for item in document["wafers"] if item["wafer"] == "W-08")
    assert (wafer["before"]["passed"], wafer["after"]["passed"]) == (229, 230)
    assert (wafer["before"]["failed"], wafer["after"]["failed"]) == (10, 9)
    assert wafer["delta_before"] == {"valid": 0, "passed": 1, "failed": -1, "pending": 0, "conflict": 0}
    assert wafer["delta_after"] == {"valid": 0, "passed": 2, "failed": -2, "pending": 0, "conflict": 0}
    point = {"x": record["x"], "y": record["y"]}
    assert point in wafer["releasable_after"]
    assert point not in [(item["x"], item["y"]) for item in wafer["held_after"]]
    assert document["summary"]["after"]["yield_pct"] == "89.86"
    assert client.get(run_base + "/corrections").json() == []


def test_publish_retry_reuses_single_version_with_original_timestamp(client, run_base):
    record = fail_cell(client, run_base)
    first = publish(client, run_base, [record])
    assert first.status_code == 201 and first.json()["reused"] is False
    retry = publish(client, run_base, [record])
    assert retry.status_code == 200 and retry.json()["reused"] is True
    assert retry.json()["document"] == first.json()["document"]
    versions = client.get(run_base + "/corrections").json()
    assert [item["correction_id"] for item in versions] == [first.json()["document"]["correction_id"]]
    assert versions[0]["transitions"] == 1 and versions[0]["wafers"] == ["W-08"]


def test_same_correction_content_is_one_version_regardless_of_order_or_duplicates(client, run_base):
    first = {"wafer": "W-08", "x": -4, "y": 4, "attempt": 2, "result": "FAIL", "bin": 5, "note": ""}
    second = {"wafer": "W-08", "x": -4, "y": 4, "attempt": 3, "result": "PASS", "bin": 1, "note": ""}
    base = publish(client, run_base, [first, second])
    assert base.status_code == 201
    reordered = publish(client, run_base, [second, first])
    duplicated = publish(client, run_base, [first, second, dict(first)])
    assert reordered.status_code == duplicated.status_code == 200
    assert {base.json()["document"]["correction_id"], reordered.json()["document"]["correction_id"],
            duplicated.json()["document"]["correction_id"]} == {base.json()["document"]["correction_id"]}
    assert len(client.get(run_base + "/corrections").json()) == 1


def test_publish_failure_keeps_previous_versions_and_base_run(client, run_base):
    record = fail_cell(client, run_base)
    assert publish(client, run_base, [record]).status_code == 201
    initial = client.get(run_base).json()
    store = client.app.state.runs.store
    with store.connect() as connection:
        connection.execute("CREATE TRIGGER fail_correction AFTER INSERT ON release_corrections "
                           "BEGIN SELECT RAISE(ABORT, 'injected failure'); END")
    other = dict(record, y=record["y"] - 1, note="第二笔")
    failed = publish(client, run_base, [other])
    assert (failed.status_code, failed.json()["code"]) == (503, "STORAGE_ERROR")
    versions = client.get(run_base + "/corrections").json()
    assert len(versions) == 1 and client.get(run_base).json() == initial
    with store.connect() as connection:
        connection.execute("DROP TRIGGER fail_correction")
    assert publish(client, run_base, [other]).status_code == 201
    assert len(client.get(run_base + "/corrections").json()) == 2


def test_parallel_publish_commits_one_version(client, run_base):
    record = fail_cell(client, run_base)
    service = client.app.state.runs
    run_id = run_base.rsplit("/", 1)[-1]
    from app.modules.corrections.schema import LateRecord
    records = [LateRecord(**record)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: service.publish_correction(run_id, records), range(4)))
    assert sum(not result["reused"] for result in results) == 1
    assert len({result["document"]["correction_id"] for result in results}) == 1
    assert len(service.store.list_corrections(run_id)) == 1


def test_correction_preserves_base_snapshot_and_original_chain(client, run_base):
    before = {suffix: client.get(run_base + suffix).json() for suffix in ("", "/yield", "/retest/W-08")}
    bundle = client.get(run_base + "/export").content
    record = fail_cell(client, run_base)
    document = publish(client, run_base, [record]).json()["document"]
    for suffix, original in before.items():
        assert client.get(run_base + suffix).json() == original, suffix
    assert client.get(run_base + "/export").content == bundle
    assert client.post(run_base + "/rerun").json()["verified"] is True
    cell = next(item for item in before["/retest/W-08"]["cells"]
                if item["x"] == record["x"] and item["y"] == record["y"])
    transition = document["transitions"][0]
    assert transition["history_before"] == cell["history"]
    assert transition["history_after"][:-1] == cell["history"]
    late = transition["history_after"][-1]
    assert (late["attempt"], late["result"], late["bin"], late["late"]) == (record["attempt"], "PASS", 1, True)
    stored = client.get(run_base + "/corrections/" + document["correction_id"]).json()
    assert stored["base_result_sha256"] == before[""]["result_sha256"]


def test_correction_record_is_scoped_to_its_run(client, run_base):
    other = client.post("/api/runs", json={"sample": "baseline"}).json()["manifest"]
    document = publish(client, run_base, [fail_cell(client, run_base)]).json()["document"]
    assert client.get(run_base + "/corrections").json()[0]["correction_id"] == document["correction_id"]
    other_base = "/api/runs/" + other["run_id"]
    assert client.get(other_base + "/corrections").json() == []
    missing = client.get(other_base + "/corrections/" + document["correction_id"])
    assert (missing.status_code, missing.json()["code"]) == (404, "CORRECTION_NOT_FOUND")


@pytest.mark.parametrize("patch,code", [
    ({"x": 99}, "CORRECTION_CELL_NOT_ACTIVE"),
    ({"wafer": "W-99"}, "CORRECTION_UNKNOWN_WAFER"),
    ({"bin": 5}, "CORRECTION_BAD_BIN"),
    ({"result": "未知"}, 422),
])
def test_invalid_correction_records_are_rejected(client, run_base, patch, code):
    record = {**fail_cell(client, run_base), **patch}
    response = publish(client, run_base, [record])
    assert response.status_code == 422
    if isinstance(code, str):
        assert response.json()["code"] == code
    assert client.get(run_base + "/corrections").json() == []


def test_late_record_must_use_newer_attempt_than_existing_chain(client, run_base):
    # W-07 (2,3) 的测次链为 T1 失败 → T2 通过
    stale = {"wafer": "W-07", "x": 2, "y": 3, "attempt": 1, "result": "PASS", "bin": 1}
    conflict = dict(stale, attempt=2)
    for record, code in [(stale, "CORRECTION_STALE_ATTEMPT"), (conflict, "CORRECTION_ATTEMPT_CONFLICT")]:
        response = publish(client, run_base, [record])
        assert (response.status_code, response.json()["code"]) == (422, code)
    assert client.get(run_base + "/corrections").json() == []


def test_same_attempt_same_cell_with_different_values_conflicts(client, run_base):
    record = fail_cell(client, run_base)
    twin = dict(record, result="FAIL", bin=7)
    response = publish(client, run_base, [record, twin])
    assert (response.status_code, response.json()["code"]) == (422, "CORRECTION_ATTEMPT_CONFLICT")


def test_correction_on_tampered_or_outdated_archive_rejected(client, run_base):
    record = fail_cell(client, run_base)
    service = client.app.state.runs
    manifest = client.get(run_base).json()
    with service.store.connect() as connection:
        original = connection.execute("SELECT snapshot FROM wafer_runs WHERE run_id = ?",
                                      (manifest["run_id"],)).fetchone()[0]
        connection.execute("UPDATE wafer_runs SET snapshot = ? WHERE run_id = ?", ("{}", manifest["run_id"]))
    damaged = publish(client, run_base, [record])
    assert (damaged.status_code, damaged.json()["code"]) == (409, "SNAPSHOT_DAMAGED")
    with service.store.connect() as connection:
        connection.execute("UPDATE wafer_runs SET snapshot = ? WHERE run_id = ?",
                           (original, manifest["run_id"]))
    assert service.rerun(manifest["run_id"])["verified"] is True  # 归档未受写入影响
    edited = dict(manifest, rule_version="wafer-0.8")
    with service.store.connect() as connection:
        connection.execute("UPDATE wafer_runs SET manifest = ? WHERE run_id = ?",
                           (json.dumps(edited), manifest["run_id"]))
    outdated = publish(client, run_base, [record])
    assert (outdated.status_code, outdated.json()["code"]) == (409, "RULE_VERSION_CHANGED")
    assert client.get(run_base + "/corrections").json() == []


def test_handover_page_serves_correction_panel(client):
    response = client.get("/yield")
    assert response.status_code == 200
    for marker in ("放行更正", 'id="correction-form"', 'id="correction-preview"',
                   'id="correction-publish"', 'id="correction-versions"'):
        assert marker in response.text
