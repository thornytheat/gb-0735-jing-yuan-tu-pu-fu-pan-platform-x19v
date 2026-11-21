import unicodedata

from app.modules.coordinates.transform import integer
from app.reasons import classify

MISSING = {"", "-", "N/A", "NULL", "未知"}
RESULTS = {"PASS": "PASS", "P": "PASS", "通过": "PASS", "FAIL": "FAIL", "F": "FAIL", "失败": "FAIL"}


def measure(row):
    fields = row["fields"]
    try:
        attempt = integer(fields["attempt"])
        if not 1 <= attempt <= 999:
            raise ValueError
    except ValueError:
        classify(row, "isolated", "BAD_ATTEMPT")
        return None
    token = unicodedata.normalize("NFKC", fields["result"]).strip().upper()
    if token in MISSING:
        classify(row, "isolated", "NO_RESULT")
        return None
    if token not in RESULTS:
        classify(row, "isolated", "BAD_RESULT")
        return None
    result = RESULTS[token]
    try:
        bin_code = integer(fields["bin"])
        if not (bin_code == 1 if result == "PASS" else 2 <= bin_code <= 999):
            raise ValueError
    except ValueError:
        classify(row, "isolated", "BAD_BIN")
        return None
    row["measurement"] = {"attempt": attempt, "result": result, "bin": bin_code}
    return attempt, result, bin_code
