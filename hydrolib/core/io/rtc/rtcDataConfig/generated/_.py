# generated by datamodel-codegen:
#   filename:  rtcDataConfig.json
#   timestamp: 2022-09-27T13:10:33+00:00

from __future__ import annotations

from pydantic import BaseModel

from . import RtcDataConfigComplexType


class RtcDataConfig(BaseModel):
    class Config:
        allow_population_by_field_name = True

    __root__: RtcDataConfigComplexType