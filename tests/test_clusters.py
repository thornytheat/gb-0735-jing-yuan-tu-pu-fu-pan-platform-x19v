import json

from app.manifest import canonical
from app.modules.clusters.components import components


def test_diagonal_failures_are_two_distinct_clusters(snapshot):
    groups = snapshot["clusters"]["W-07"]
    assert groups[-2]["points"] == [(5,-3)]
    assert groups[-1]["points"] == [(6,-4)]
    assert (groups[-2]["id"], groups[-1]["id"]) == ("C06", "C07")


def test_recovered_bridge_splits_streak(snapshot):
    groups = {group["id"]: group for group in snapshot["clusters"]["W-07"]}
    assert groups["C03"]["points"] == [(0,3), (0,2)]
    assert (0,0) in groups["C05"]["points"]
    assert not any((0,1) in group["points"] for group in groups.values())


def test_conflicts_and_historical_failures_do_not_count_as_members(snapshot):
    points = {point for group in snapshot["clusters"]["W-07"] for point in group["points"]}
    assert {(3,3),(4,4),(2,3),(-1,0)}.isdisjoint(points)
    assert len(points) == 23


def test_cluster_transitive_members_have_bounds_and_bins(snapshot):
    first = snapshot["clusters"]["W-07"][0]
    assert first["size"] == 6 and first["anchor"] == (-3,6)
    assert first["bounds"] == [-3,4,-1,6]
    assert first["bins"] == {"4":1,"6":5}
    assert (-1,4) in first["points"]


def test_ordering_is_spatial_not_decision_insertion_order(snapshot):
    decisions = snapshot["decisions"]["W-07"]
    assert components(dict(reversed(list(decisions.items())))) == snapshot["clusters"]["W-07"]


def test_cluster_membership_is_partition_of_failed_dies_on_each_wafer(snapshot):
    for wafer, groups in snapshot["clusters"].items():
        members = [point for group in groups for point in group["points"]]
        assert set(members) == {(cell["x"], cell["y"]) for cell in snapshot["decisions"][wafer].values() if cell["result"] == "FAIL"}
        assert len(members) == len(set(members))
    assert len(snapshot["clusters"]["W-08"]) == 4


def test_cluster_detail_returns_raw_and_missing_cluster_is_404(client, run_base):
    result = client.get(run_base + "/clusters/W-07/C05").json()
    assert result["size"] == 6
    assert {row["id"] for row in result["rows"]} == set(result["evidence"])
    assert "probe-a.csv:154" in result["evidence"] and "probe-b.csv:11" in result["evidence"]
    response = client.get(run_base + "/clusters/W-07/C99")
    assert (response.status_code, response.json()["code"]) == (404, "CLUSTER_NOT_FOUND")


def test_multi_digit_bin_histogram_has_stable_archive_serialization():
    cells = {"0,0": {"x":0,"y":0,"result":"FAIL","bin":2,"evidence":["p.csv:2"]},
             "1,0": {"x":1,"y":0,"result":"FAIL","bin":10,"evidence":["p.csv:3"]}}
    groups = components(cells)
    assert groups[0]["bins"] == {"2":1,"10":1}
    raw = canonical(groups)
    assert canonical(json.loads(raw)) == raw
