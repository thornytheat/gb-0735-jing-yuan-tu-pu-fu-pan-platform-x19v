from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

TEXT = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,30}$")]
FILE = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_-]{1,40}\.csv$")]
SHIFT = Annotated[int, Field(ge=-1_000_000, le=1_000_000)]


class Source(BaseModel):
    name: FILE
    notch: Literal["N", "E", "S", "W"]
    origin_x: SHIFT = 0
    origin_y: SHIFT = 0
    x_left: bool = False
    y_down: bool = False
    mirror: bool = False
    records: int = Field(ge=0, le=12000)


class Geometry(BaseModel):
    wafer: TEXT
    radius: int = Field(ge=3, le=30)
    edge: int = Field(ge=0, le=8)
    notch_depth: int = Field(ge=0, le=8)
    notch_half_width: int = Field(ge=0, le=6)

    @model_validator(mode="after")
    def usable_radius(self):
        if self.edge >= self.radius or self.notch_depth >= self.radius:
            raise ValueError("边缘带与缺口深度必须小于半径")
        return self


class Ledger(BaseModel):
    wafer: TEXT
    valid: int = Field(ge=0, le=4000)
    passed: int = Field(ge=0, le=4000)
    failed: int = Field(ge=0, le=4000)
    pending: int = Field(ge=0, le=4000)
    conflict: int = Field(ge=0, le=4000)


class Sample(BaseModel):
    sample: TEXT
    label: str
    lot: TEXT
    sources: list[Source] = Field(min_length=1, max_length=8)
    wafers: list[Geometry] = Field(min_length=1, max_length=8)
    ledger: list[Ledger] = Field(max_length=8)

    @model_validator(mode="after")
    def unique_keys(self):
        for values in ([s.name for s in self.sources], [w.wafer for w in self.wafers],
                       [r.wafer for r in self.ledger]):
            if len(values) != len(set(values)):
                raise ValueError("批次契约含重复键")
        return self


@dataclass(frozen=True)
class InputPackage:
    spec: Sample
    files: dict[str, bytes]
