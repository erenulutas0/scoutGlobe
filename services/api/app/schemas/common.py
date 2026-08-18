"""Shared response plumbing.

The web app and packages/core speak camelCase, the database speaks snake_case.
Doing the conversion here (once) keeps every router and every zod schema honest.
"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base for every response model: snake_case in Python, camelCase on the wire."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class Problem(BaseModel):
    """RFC 7807 problem+json — the single error shape of this API."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
