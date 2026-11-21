import csv
import io
import unicodedata
from collections import Counter

from app.errors import ReviewError
from app.reasons import classify

HEADER = ("wafer", "x", "y", "attempt", "result", "bin", "note")
OLD_NAMES = {"片号": "wafer", "列": "x", "行": "y", "测次": "attempt",
             "判定": "result", "分档": "bin", "备注": "note"}


def decode(blob, name):
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            text = blob.decode(encoding)
        except UnicodeDecodeError:
            continue
        if "\x00" not in text:
            if encoding == "utf-8-sig" and not blob.startswith(b"\xef\xbb\xbf"):
                encoding = "utf-8"
            return text, encoding
        break
    raise ReviewError("BAD_ENCODING", f"{name} 编码无效")


def header(fields):
    normalized = [unicodedata.normalize("NFKC", value.lstrip("\ufeff")).strip().lower() for value in fields]
    return tuple(OLD_NAMES.get(value, value) for value in normalized)


def read_source(source, blob):
    text, encoding = decode(blob, source.name)
    if not text:
        raise ReviewError("EMPTY_FILE", f"{source.name} 是空文件")
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    records = []
    counts = Counter()
    columns = None
    try:
        while True:
            line = reader.line_num + 1
            fields = next(reader, None)
            if fields is None:
                break
            empty = not any(field.strip() for field in fields)
            keys = () if empty else header(fields)
            is_header = len(keys) == len(HEADER) and set(keys) == set(HEADER)
            if columns is None and not empty:
                if not is_header:
                    raise ReviewError("BAD_HEADER", f"{source.name}:{line} 档头无效")
                columns = keys
                counts["segments"] += 1
                continue
            row = {"id": f"{source.name}:{line}", "source": source.name, "line": line,
                   "end_line": reader.line_num, "raw": fields, "bucket": "candidate", "code": None}
            if empty:
                classify(row, "blank", "BLANK_ROW")
            elif is_header:
                columns = keys
                counts["segments"] += 1
                classify(row, "header", "REPEATED_HEADER")
            elif len(fields) != len(columns):
                classify(row, "isolated", "COLUMN_COUNT")
            else:
                row["fields"] = dict(zip(columns, fields))
            records.append(row)
            counts[row["bucket"]] += 1
    except csv.Error as exc:
        raise ReviewError("BROKEN_CSV", f"{source.name}:{reader.line_num} CSV 记录损坏") from exc

    if columns is None:
        raise ReviewError("BLANK_FILE", f"{source.name} 只有空记录")
    data_count = len(records) - counts["header"] - counts["blank"]
    if data_count != source.records:
        raise ReviewError("RECORD_COUNT_MISMATCH", f"{source.name} 声明 {source.records} 行，实收 {data_count} 行")
    if data_count == 0:
        raise ReviewError("HEADER_ONLY", f"{source.name} 只有档头")
    return records, {"name": source.name, "encoding": encoding, "data_count": data_count,
                     "physical_lines": reader.line_num, "segments": counts["segments"], "counts": dict(counts)}


def ingest(package):
    rows, files = [], []
    for source in package.spec.sources:
        records, stats = read_source(source, package.files[source.name])
        rows.extend(records)
        files.append(stats)
    return rows, files
