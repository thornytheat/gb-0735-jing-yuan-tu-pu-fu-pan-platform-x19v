import base64
import binascii

from pydantic import ValidationError

from app.config import MAX_INPUT_BYTES, ROOT
from app.errors import ReviewError
from app.modules.intake.contract import InputPackage, Sample

CATALOG = {
    "mixed": "复判混合样例",
    "baseline": "单档基准样例",
    "truncated": "截断探针图",
}


def load_sample(sample, root=ROOT / "sample_data"):
    if sample not in CATALOG:
        raise ReviewError("SAMPLE_NOT_FOUND", "样例未登记", 404)
    try:
        spec = Sample.model_validate_json((root / f"{sample}.json").read_bytes())
    except (OSError, ValidationError) as exc:
        raise ReviewError("BAD_CONTRACT", "无法读取样例契约") from exc
    if spec.sample != sample:
        raise ReviewError("BAD_CONTRACT", "样例标识不符")

    files = {}
    budget = MAX_INPUT_BYTES
    for source in spec.sources:
        try:
            with (root / source.name).open("rb") as stream:
                blob = stream.read(budget + 1)
        except OSError as exc:
            raise ReviewError("SOURCE_MISSING", f"缺少图档 {source.name}") from exc
        if len(blob) > budget:
            raise ReviewError("SOURCE_TOO_LARGE", "图档合计超过 2 MiB", 413)
        files[source.name] = blob
        budget -= len(blob)
    return InputPackage(spec, files)


def restore_package(pinned):
    try:
        spec = Sample.model_validate(pinned["spec"])
        files = {name: base64.b64decode(raw, validate=True) for name, raw in pinned["files_base64"].items()}
        if set(files) != {source.name for source in spec.sources}:
            raise ValueError("来源清单不符")
    except (KeyError, TypeError, AttributeError, ValueError, binascii.Error) as exc:
        raise ReviewError("SNAPSHOT_DAMAGED", "运行归档无法读取", 409) from exc
    return InputPackage(spec, files)
