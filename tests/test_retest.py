from copy import deepcopy

from app.modules.retest.arbitrate import decide


def test_valid_second_measurement_overrides_failure_and_normalizes_width(snapshot):
    # TRAP-06
    cell = snapshot["decisions"]["W-07"]["2,3"]
    assert (cell["result"], cell["attempt"], cell["bin"]) == ("PASS", 2, 1)
    assert cell["history"][0]["result"] == "FAIL"
    row = next(row for row in snapshot["rows"] if row["id"] == "probe-b.csv:2")
    assert (row["fields"]["attempt"], row["fields"]["bin"]) == ("２", "１")


def test_numeric_attempt_precedence_ignores_arrival_order(snapshot):
    # TRAP-19
    cell = snapshot["decisions"]["W-07"]["0,1"]
    assert cell["sources"][-2:] == ["probe-b.csv:9", "probe-b.csv:10"]
    assert [(item["attempt"], item["result"]) for item in cell["history"]] == [(1,"FAIL"),(2,"FAIL"),(10,"PASS")]


def test_same_attempt_conflict_does_not_fall_back_to_earlier_pass(snapshot):
    # TRAP-14
    cell = snapshot["decisions"]["W-07"]["3,3"]
    assert (cell["attempt"], cell["result"], cell["bin"]) == (2, "CONFLICT", None)
    assert cell["history"][0]["result"] == "PASS"
    codes = {row["id"]: row["code"] for row in snapshot["rows"] if row["id"] in cell["evidence"]}
    assert codes == {"probe-a.csv:544":"SAME_ATTEMPT_CONFLICT", "probe-b.csv:3":"SAME_ATTEMPT_CONFLICT"}


def test_same_failure_different_bins_still_conflict(snapshot):
    cell = snapshot["decisions"]["W-07"]["4,4"]
    rows = [row for row in snapshot["rows"] if row["id"] in cell["evidence"]]
    assert cell["result"] == "CONFLICT"
    assert {row["measurement"]["bin"] for row in rows} == {8,9}
    assert all(row["bucket"] == "isolated" for row in rows)


def test_missing_later_value_does_not_override_prior_failure(snapshot):
    # TRAP-07
    cell = snapshot["decisions"]["W-07"]["1,-1"]
    row = next(row for row in snapshot["rows"] if row["id"] == "probe-b.csv:7")
    assert (row["code"], row["fields"]["result"]) == ("NO_RESULT", "N/A")
    assert (cell["result"], cell["attempt"], cell["bin"]) == ("FAIL",1,5)


def test_newer_valid_attempt_resolves_historical_conflict(snapshot):
    cell = snapshot["decisions"]["W-07"]["-1,0"]
    assert [step["result"] for step in cell["history"]] == ["FAIL", "CONFLICT", "PASS"]
    assert cell["evidence"] == ["probe-b.csv:5"]


def test_duplicate_selection_stable_if_same_values_arrive_in_reverse(snapshot):
    rows = [deepcopy(row) for row in snapshot["rows"] if row["id"] in {"probe-a.csv:154", "probe-b.csv:11"}]
    output = decide({1: list(reversed(rows))})
    assert output["result"] == "FAIL" and output["evidence"] == ["probe-a.csv:154", "probe-b.csv:11"]
    assert [(row["source"], row["bucket"]) for row in rows] == [("probe-a.csv", "accepted"), ("probe-b.csv", "duplicate")]


def test_retest_filter_returns_only_current_conflicts(client, run_base):
    url = run_base + "/retest/W-07"
    data = client.get(url, params={"result": "CONFLICT"}).json()
    assert {(cell["x"], cell["y"]) for cell in data["cells"]} == {(3,3), (4,4)}
    assert {row["code"] for row in data["issues"]} == {"BAD_ATTEMPT", "NO_RESULT", "BAD_RESULT", "BAD_BIN",
                                                      "SAME_ATTEMPT_CONFLICT", "DUPLICATE_RESULT"}
    assert client.get(url, params={"result": "HOLD"}).status_code == 422
