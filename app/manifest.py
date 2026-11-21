import base64
import hashlib
import json

from app.config import RULE_VERSION


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint(package, version=RULE_VERSION):
    sources = {
        name: {"bytes": len(blob), "sha256": digest(blob)}
        for name, blob in sorted(package.files.items())
    }
    contract = digest(canonical(package.spec.model_dump()).encode())
    key = digest(canonical([version, contract, sources]).encode())
    return key, sources, contract


def pin(package):
    return {
        "spec": package.spec.model_dump(),
        "files_base64": {name: base64.b64encode(blob).decode("ascii") for name, blob in package.files.items()},
    }
