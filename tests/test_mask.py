from app.modules.intake.contract import Geometry
from app.modules.mask.geometry import make_mask, position


def test_each_wafer_has_its_own_real_mask(snapshot):
    assert snapshot["masks"]["W-07"]["counts"] == {"ACTIVE":313, "OUTSIDE_DISC":184, "EDGE_EXCLUSION":118, "NOTCH_VOID":10}
    assert snapshot["masks"]["W-08"]["counts"] == {"ACTIVE":249, "OUTSIDE_DISC":124, "EDGE_EXCLUSION":61, "NOTCH_VOID":7}


def test_edge_boundary_is_inclusive_and_diagonal_is_radial(package):
    geometry = package.spec.wafers[0]
    assert [position(geometry, x, y) for x, y in [(6,8),(0,10),(7,8),(9,9)]] == [
        "ACTIVE", "ACTIVE", "EDGE_EXCLUSION", "OUTSIDE_DISC"]


def test_notch_has_inclusive_inner_edge_and_excludes_active_radius(package):
    geometry = package.spec.wafers[0]
    assert [position(geometry, x, y) for x, y in [(1,-9),(1,-8),(2,-9),(0,-12),(0,-13)]] == [
        "NOTCH_VOID", "ACTIVE", "ACTIVE", "NOTCH_VOID", "OUT_OF_GRID"]


def test_geometry_without_notch_or_exclusion_has_no_reserved_cells():
    mask = make_mask(Geometry(wafer="W", radius=3, edge=0, notch_depth=0, notch_half_width=0))
    assert mask["counts"] == {"OUTSIDE_DISC":20, "ACTIVE":29}
    assert mask["cells"][0] == (-3,3,"OUTSIDE_DISC")
    assert mask["cells"][-1] == (3,-3,"OUTSIDE_DISC")


def test_invalid_physical_cells_have_no_final_decision(snapshot):
    for code, point in [("NOTCH_VOID", (0,-10)), ("EDGE_EXCLUSION", (12,0)),
                        ("OUTSIDE_DISC", (12,12)), ("OUT_OF_GRID", (50,0))]:
        row = next(row for row in snapshot["rows"] if row["code"] == code)
        assert row["transform"]["canonical"] == list(point)
        assert f"{point[0]},{point[1]}" not in snapshot["decisions"]["W-07"]


def test_unmeasured_active_dies_stay_in_denominator(snapshot):
    cells = snapshot["decisions"]["W-07"]
    pending = [cell for cell in cells.values() if cell["result"] == "PENDING"]
    assert len(cells) == 313
    assert len(pending) == 13
    assert all(cell["attempt"] is None for cell in pending)


def test_cell_inspection_drills_into_invalid_source_and_validates_bounds(client, run_base):
    url = run_base + "/mask/W-07/cell"
    cell = client.get(url, params={"x":0, "y":-10}).json()
    assert cell["eligibility"] == "NOTCH_VOID" and cell["decision"] is None
    assert cell["evidence"][0]["code"] == "NOTCH_VOID"
    invalid = client.get(url, params={"x":13, "y":0})
    assert (invalid.status_code, invalid.json()["code"]) == (422, "OUT_OF_GRID")
    assert client.get(run_base + "/mask/W-99").json()["code"] == "WAFER_NOT_FOUND"
