import unicodedata
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.modules.intake.contract import SHIFT, TEXT
from app.modules.retest.measurements import RESULTS


class LateRecord(BaseModel):
    """一笔迟到复测，坐标为交接页面使用的标准坐标。"""
    wafer: TEXT
    x: SHIFT
    y: SHIFT
    attempt: Annotated[int, Field(ge=1, le=999)]
    result: str
    bin: Annotated[int, Field(ge=1, le=999)]
    note: Annotated[str, Field(max_length=200)] = ""

    @field_validator("result")
    @classmethod
    def normalize_result(cls, value):
        token = unicodedata.normalize("NFKC", value).strip().upper()
        if token not in RESULTS:
            raise ValueError("判定无效")
        return RESULTS[token]


class CorrectionRequest(BaseModel):
    records: Annotated[list[LateRecord], Field(min_length=1, max_length=64)]
