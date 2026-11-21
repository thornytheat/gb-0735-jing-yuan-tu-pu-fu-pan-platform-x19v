from collections import Counter

from app.modules.clusters.components import components
from app.modules.coordinates.transform import align
from app.modules.intake.reader import ingest
from app.modules.mask.geometry import screen
from app.modules.retest.arbitrate import arbitrate
from app.modules.yield_audit.compare import compare


def calculate(package):
    rows, intake = ingest(package)
    transforms = align(package.spec, rows)
    masks = screen(package.spec, rows)
    decisions = arbitrate(masks, rows)
    clusters = {wafer: components(cells) for wafer, cells in decisions.items()}
    audit = compare(package.spec, masks, decisions, rows, intake)
    reasons = Counter(row["code"] for row in rows if row["bucket"] == "isolated")
    return {"files": intake, "transforms": transforms, "masks": masks, "decisions": decisions,
            "clusters": clusters, "audit": audit, "reasons": dict(sorted(reasons.items())), "rows": rows}
