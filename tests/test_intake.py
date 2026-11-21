import pytest

from app.errors import ReviewError
from app.modules.intake.catalog import load_sample
from app.modules.intake.reader import read_source
from app.modules.runs.pipeline import calculate


def test_bom_source_preserves_wafer_column(package):
    # TRAP-02
    rows, info = read_source(package.spec.sources[0], package.files["probe-a.csv"])
    assert (info["encoding"], info["data_count"], rows[0]["fields"]["wafer"]) == ("utf-8-sig", 554, "W-07")


def test_gb_source_decodes_chinese_values(package):
    # TRAP-01
    rows, info = read_source(package.spec.sources[1], package.files["probe-b.csv"])
    assert (info["encoding"], rows[0]["fields"]["note"]) == ("gb18030", "夹具重压")
    assert rows[0]["fields"]["result"] == "通过"


def test_multiline_evidence_has_physical_span(snapshot):
    # TRAP-03
    row = next(row for row in snapshot["rows"] if row["id"] == "probe-a.csv:154")
    assert row["end_line"] == 155
    assert row["fields"]["note"] == "探针接触波动, 二次确认\n交接：夜班"
    assert snapshot["files"][0]["physical_lines"] == 558


def test_segment_headers_advance_reordered_contract(snapshot):
    # TRAP-04, TRAP-17
    assert [source["segments"] for source in snapshot["files"]] == [2, 2]
    row = next(row for row in snapshot["rows"] if row["id"] == "probe-b.csv:9")
    assert row["raw"][1:6] == ["200", "99", "10", "1", "PASS"]
    assert (row["fields"]["x"], row["fields"]["y"]) == ("99", "200")


def test_width_mismatch_retains_all_raw_fields(snapshot):
    # TRAP-05
    bad = [row for row in snapshot["rows"] if row["code"] == "COLUMN_COUNT"]
    assert [(row["id"], row["raw"][-1], row["bucket"]) for row in bad] == [("probe-a.csv:558", "多一栏", "isolated")]


def test_empty_header_and_blank_are_separate(package):
    # TRAP-18
    source = package.spec.sources[0].model_copy(update={"records": 0})
    files = [(b"", "EMPTY_FILE"), (b"\r\n\r\n", "BLANK_FILE"),
             (b"wafer,x,y,attempt,result,bin,note\r\n", "HEADER_ONLY")]
    for blob, code in files:
        with pytest.raises(ReviewError) as error:
            read_source(source, blob)
        assert error.value.code == code


def test_complete_looking_truncation_fails_manifest_count():
    # TRAP-16
    with pytest.raises(ReviewError) as error:
        calculate(load_sample("truncated"))
    assert error.value.code == "RECORD_COUNT_MISMATCH"
    assert "声明 47 行，实收 3 行" in str(error.value)


def test_invalid_encoding_and_unclosed_quoted_record(package):
    source = package.spec.sources[0]
    for blob, code in [(b"\x00\xff", "BAD_ENCODING"),
                       (b'wafer,x,y,attempt,result,bin,note\nW-07,0,0,1,P,1,"broken', "BROKEN_CSV")]:
        with pytest.raises(ReviewError) as error:
            read_source(source, blob)
        assert error.value.code == code
