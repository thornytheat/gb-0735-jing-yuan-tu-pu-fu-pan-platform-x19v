import base64
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

from app.config import RULE_VERSION
from app.manifest import canonical, fingerprint
from app.modules.intake.contract import InputPackage
from app.modules.runs.service import RunService


def test_repeat_submission_reuses_id_manifest_and_row_count(client, run_base):
    first = client.get(run_base).json()
    repeat = client.post("/api/runs", json={"sample":"mixed"})
    assert repeat.status_code == 200 and repeat.json() == {"manifest":first,"reused":True}
    assert client.get("/api/runs").json() == [first]
    assert client.get(run_base + "/yield").json()["rows"]["total"] == 569


def test_parallel_start_commits_one_archive(client):
    service = client.app.state.runs
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(service.start, ["mixed"] * 4))
    assert sum(not result["reused"] for result in results) == 1
    assert len({result["manifest"]["run_id"] for result in results}) == len(service.store.list()) == 1
    assert len({result["manifest"]["duration_ms"] for result in results}) == 1


def test_rerun_recomputes_pinned_input_without_catalog(client, run_base):
    store = client.app.state.runs.store
    service = RunService(store, loader=lambda _: None)
    manifest = client.get(run_base).json()
    assert service.rerun(manifest["run_id"]) == {"manifest":manifest,"reused":True,"verified":True}
    assert len(store.list()) == 1


def test_truncated_second_source_leaves_previous_snapshot_untouched(client, run_base):
    initial = client.get(run_base).json()
    reply = client.post("/api/runs", json={"sample":"truncated"})
    assert (reply.status_code, reply.json()["code"]) == (422, "RECORD_COUNT_MISMATCH")
    assert client.get("/api/runs").json() == [initial]
    assert client.get(run_base).json() == initial


def test_sqlite_publish_error_rolls_back_and_retry_is_safe(client, run_base):
    store = client.app.state.runs.store
    with store.connect() as connection:
        connection.execute("CREATE TRIGGER fail_write AFTER INSERT ON wafer_runs BEGIN SELECT RAISE(ABORT, 'injected failure'); END")
    failed = client.post("/api/runs", json={"sample":"baseline"})
    assert (failed.status_code, failed.json()["code"]) == (503, "STORAGE_ERROR")
    assert len(store.list()) == 1
    with store.connect() as connection:
        connection.execute("DROP TRIGGER fail_write")
    assert client.post("/api/runs", json={"sample":"baseline"}).status_code == 201
    assert len(store.list()) == 2


def test_result_or_pinned_mutation_blocks_export_and_rerun(client, run_base):
    service = client.app.state.runs
    manifest = client.get(run_base).json()
    with service.store.connect() as connection:
        connection.execute("UPDATE wafer_runs SET snapshot = ? WHERE run_id = ?", ("{}", manifest["run_id"]))
    for failed in [client.post(run_base + "/rerun"), client.get(run_base + "/export")]:
        assert (failed.status_code, failed.json()["code"]) == (409, "SNAPSHOT_DAMAGED")
    assert len(service.store.list()) == 1


def test_bundle_preserves_original_bytes_and_gives_reproducible_hashes(client, run_base, package):
    response = client.get(run_base + "/export")
    assert response.status_code == 200 and response.headers["content-disposition"].startswith("attachment;")
    data = response.json()
    manifest = data["manifest"]
    assert data["format"] == "wafer-evidence-v1" and manifest["rule_version"] == RULE_VERSION
    assert manifest["result_sha256"] == hashlib.sha256(canonical(data["snapshot"]).encode()).hexdigest()
    assert manifest["contract_sha256"] == hashlib.sha256(canonical(data["input"]["spec"]).encode()).hexdigest()
    for filename, encoded in data["input"]["files_base64"].items():
        blob = base64.b64decode(encoded)
        assert blob == package.files[filename]
        assert manifest["sources"][filename]["sha256"] == hashlib.sha256(blob).hexdigest()
    assert client.get(run_base + "/export").content == response.content


def test_raw_bytes_contract_and_rules_participate_in_run_identity(package):
    key, _, _ = fingerprint(package)
    revised = package.spec.model_copy(update={"lot":"FT26-OTHER"})
    files = dict(package.files)
    files["probe-a.csv"] += b"\n"
    assert len({key, fingerprint(package, version="wafer-2")[0], fingerprint(InputPackage(revised, package.files))[0],
                fingerprint(InputPackage(package.spec, files))[0]}) == 4


def test_replay_rejects_old_rule_version(client, run_base):
    service = client.app.state.runs
    manifest = client.get(run_base).json()
    edited = dict(manifest, rule_version="wafer-0.8")
    with service.store.connect() as connection:
        connection.execute("UPDATE wafer_runs SET manifest = ? WHERE run_id = ?", (json.dumps(edited), manifest["run_id"]))
    response = client.post(run_base + "/rerun")
    assert (response.status_code, response.json()["code"]) == (409, "RULE_VERSION_CHANGED")
