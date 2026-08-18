from typing import Literal

from pydantic import BaseModel


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    version: str
    database: Literal["up", "down", "unknown"]
