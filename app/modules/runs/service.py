from datetime import datetime, timezone
from time import perf_counter

from app.config import RULE_VERSION
from app.errors import ReviewError
from app.manifest import canonical, digest, fingerprint, pin
from app.modules.intake.catalog import load_sample, restore_package
from app.modules.runs.pipeline import calculate


class RunService:
    def __init__(self, store, loader=load_sample):
        self.store = store
        self.loader = loader

    def start(self, sample):
        started = perf_counter()
        package = self.loader(sample)
        key, sources, contract = fingerprint(package)
        snapshot = calculate(package)
        result_hash = digest(canonical(snapshot).encode())
        manifest = {"run_id": key, "sample": sample, "label": package.spec.label, "lot": package.spec.lot,
                    "wafers": [wafer.wafer for wafer in package.spec.wafers], "rule_version": RULE_VERSION,
                    "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "duration_ms": round((perf_counter() - started) * 1000), "sources": sources,
                    "contract_sha256": contract, "result_sha256": result_hash,
                    "summary": snapshot["audit"]["summary"], "status": snapshot["audit"]["status"]}
        recorded, created = self.store.put(manifest, snapshot, pin(package))
        if recorded["result_sha256"] != result_hash:
            raise ReviewError("REPLAY_DIVERGED", "同版结果发生变化", 409)
        return {"manifest": recorded, "reused": not created}

    def rerun(self, run_id):
        manifest, snapshot, pinned = self.store.get(run_id)
        if manifest["rule_version"] != RULE_VERSION:
            raise ReviewError("RULE_VERSION_CHANGED", "旧规则版本无法重算", 409)
        package = restore_package(pinned)
        key, _, _ = fingerprint(package)
        if key != run_id or digest(canonical(snapshot).encode()) != manifest["result_sha256"]:
            raise ReviewError("SNAPSHOT_DAMAGED", "归档摘要不符", 409)
        actual = digest(canonical(calculate(package)).encode())
        if actual != manifest["result_sha256"]:
            raise ReviewError("REPLAY_DIVERGED", "复算摘要不符", 409)
        return {"manifest": manifest, "reused": True, "verified": True}
