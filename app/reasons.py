REASONS = {
    "BLANK_ROW": "空记录",
    "REPEATED_HEADER": "重复档头",
    "COLUMN_COUNT": "栏数不符",
    "UNKNOWN_WAFER": "晶圆未登记",
    "BAD_COORDINATE": "坐标须为整数",
    "OUT_OF_GRID": "超出阵列",
    "OUTSIDE_DISC": "圆片外",
    "EDGE_EXCLUSION": "边缘保留带",
    "NOTCH_VOID": "缺口空位",
    "BAD_ATTEMPT": "测次无效",
    "NO_RESULT": "空测值",
    "BAD_RESULT": "结果无效",
    "BAD_BIN": "分档不符",
    "SAME_ATTEMPT_CONFLICT": "同次测值矛盾",
    "DUPLICATE_RESULT": "同次同值重复",
}


def classify(row, bucket, code):
    row.update(bucket=bucket, code=code, reason=REASONS[code])
