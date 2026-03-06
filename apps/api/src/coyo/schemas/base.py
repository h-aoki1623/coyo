"""Shared base schema for camelCase JSON serialization."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base schema that serializes fields to camelCase for API responses.

    All response schemas should inherit from this instead of BaseModel
    to ensure consistent camelCase JSON keys for the mobile client.

    With ``populate_by_name=True``, fields can be set using either
    their Python snake_case name or the generated camelCase alias.
    """

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )
