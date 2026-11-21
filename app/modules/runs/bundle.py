from app.errors import ReviewError
from app.manifest import canonical, digest, fingerprint
from app.modules.intake.catalog import restore_package


def make_bundle(archive):
    manifest, snapshot, pinned = archive
    key, sources, contract = fingerprint(restore_package(pinned), manifest["rule_version"])
    if (key != manifest["run_id"] or sources != manifest["sources"] or contract != manifest["contract_sha256"]
            or digest(canonical(snapshot).encode()) != manifest["result_sha256"]):
        raise ReviewError("SNAPSHOT_DAMAGED", "归档摘要不符", 409)
    return canonical({"format": "wafer-evidence-v1", "manifest": manifest,
                      "input": pinned, "snapshot": snapshot}).encode("utf-8")
