from copy import deepcopy

from app.modules.yield_audit.compare import compare, percent


def test_audit_uses_valid_denominator_not_only_measured(snapshot):
    audit = snapshot["audit"]
    assert audit["summary"] == {"valid":562,"passed":504,"failed":33,"pending":23,"conflict":2,
                                "yield_pct":"89.68","coverage_pct":"95.91"}
    assert [(row["wafer"], row["yield_pct"]) for row in audit["wafers"]] == [("W-07","87.86"), ("W-08","91.97")]


def test_reference_comparison_detects_offsetting_differences(snapshot):
    first, second = snapshot["audit"]["wafers"]
    assert first["status"] == "MATCH" and second["status"] == "DIFFERENCE"
    assert second["delta"] == {"valid":0,"passed":1,"failed":-1,"pending":0,"conflict":0}
    assert second["balanced"] is True
    assert snapshot["audit"]["status"] == "REVIEW"


def test_input_conservation_has_disjoint_buckets(snapshot):
    actual = snapshot["audit"]["rows"]
    assert actual == {"total":569,"declared_data":566,"accepted":544,"isolated":18,"duplicate":4,
                      "blank":1,"header":2,"balanced":True}
    assert len({row["id"] for row in snapshot["rows"]}) == 569


def test_set_reconciliation_catches_same_count_displaced_cell(package, snapshot):
    decisions = deepcopy(snapshot["decisions"])
    decisions["W-07"]["12,12"] = decisions["W-07"].pop("0,0")
    audit = compare(package.spec, snapshot["masks"], decisions, snapshot["rows"], snapshot["files"])
    wafer = audit["wafers"][0]
    assert wafer["balanced"] is False and audit["status"] == "UNBALANCED"
    assert wafer["missing"] == ["0,0"] and wafer["extra"] == ["12,12"]


def test_missing_and_extra_ledger_wafers_are_distinct(package, snapshot):
    extra = package.spec.ledger[0].model_copy(update={"wafer": "W-99"})
    spec = package.spec.model_copy(update={"ledger": [extra, package.spec.ledger[1]]})
    audit = compare(spec, snapshot["masks"], snapshot["decisions"], snapshot["rows"], snapshot["files"])
    assert audit["unknown_reference"] == ["W-99"]
    assert audit["wafers"][0]["status"] == "MISSING_REFERENCE"
    assert audit["status"] == "REVIEW"


def test_percent_handles_empty_denominator_and_half_up():
    assert percent(0,0) is None
    assert percent(1,32) == "3.13"
    assert percent(1,6) == "16.67"


def test_reason_distribution_matches_returned_isolated_rows(client, run_base):
    audit = client.get(run_base + "/yield").json()
    assert len(audit["isolated"]) == sum(audit["reasons"].values()) == 18
    assert audit["reasons"]["SAME_ATTEMPT_CONFLICT"] == 6
    assert all(row["raw"] and row["line"] > 0 for row in audit["isolated"])
