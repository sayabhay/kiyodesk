"""System endpoint response schemas."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health state exposed to users and monitoring systems."""

    status: str
    version: str
    database: str
    providers: list[str]
