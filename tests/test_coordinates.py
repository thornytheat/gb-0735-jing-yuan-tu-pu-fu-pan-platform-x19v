from app.modules.coordinates.transform import normalize
from app.modules.intake.contract import Source


def test_asymmetric_rotation_sign_is_derived_from_notch():
    cases = {"S": ([4, 2], 0), "W": ([-2, 4], 90), "N": ([-4, -2], 180), "E": ([2, -4], 270)}
    for notch, (point, angle) in cases.items():
        source = Source(name="p.csv", records=1, notch=notch)
        result = normalize(source, 4, 2)
        assert (result["canonical"], result["turn_degrees"]) == (point, angle)


def test_mirror_changes_rotation_needed_for_notch():
    source = Source(name="p.csv", records=1, notch="E", mirror=True)
    assert normalize(source, 1, 0)["canonical"] == [0, -1]
    assert normalize(source, 4, 2)["canonical"] == [-2, -4]


def test_origin_and_axis_reversal_precede_mirror(package):
    result = normalize(package.spec.sources[1], 97, 202)
    assert result == {"translated": [-3, -2], "mirrored": [3, -2], "turn_degrees": 90, "canonical": [2, 3]}


def test_leftward_raw_x_axis_and_signed_origin():
    source = Source(name="p.csv", records=1, notch="S", origin_x=-8, origin_y=3, x_left=True, y_down=True)
    assert normalize(source, -13, -2)["canonical"] == [5, 5]


def test_distinct_raw_tools_land_on_same_wafer_coordinate(snapshot):
    actual = {row["id"]: row for row in snapshot["rows"]}
    assert actual["probe-a.csv:99"]["fields"]["x"] == "242"
    assert actual["probe-b.csv:2"]["fields"]["x"] == "97"
    assert actual["probe-a.csv:99"]["transform"]["canonical"] == actual["probe-b.csv:2"]["transform"]["canonical"] == [2, 3]


def test_bad_coordinates_and_unknown_wafer_keep_distinct_reasons(snapshot):
    issues = {row["code"]: row for row in snapshot["rows"] if row["code"] in {"BAD_COORDINATE", "UNKNOWN_WAFER"}}
    assert issues["BAD_COORDINATE"]["fields"]["x"] == "240.5"
    assert issues["UNKNOWN_WAFER"]["wafer"] == "W-99"
    assert all("transform" not in row for row in issues.values())


def test_probe_validation_and_source_membership(client, run_base):
    url = run_base + "/coordinates/probe"
    tested = client.get(url, params={"source":"probe-b.csv", "x":97, "y":202})
    assert tested.json()["canonical"] == [2, 3]
    assert client.get(url, params={"source":"probe-b.csv", "x":"2.1", "y":0}).status_code == 422
    missing = client.get(url, params={"source":"bogus.csv", "x":0, "y":0})
    assert (missing.status_code, missing.json()["code"]) == (404, "SOURCE_NOT_FOUND")
