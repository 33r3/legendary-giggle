from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# Export-app timestamps arrive like "2026-08-06 07:00:00 -0500".
_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S %z"


def _parse_timestamp(value: str) -> datetime:
    return datetime.strptime(value, _TIMESTAMP_FORMAT)


class StepMetricEntry(BaseModel):
    date: datetime
    qty: float
    source: str = "unknown"

    @field_validator("date", mode="before")
    @classmethod
    def _parse_date(cls, value: str | datetime) -> datetime:
        return value if isinstance(value, datetime) else _parse_timestamp(value)


class Metric(BaseModel):
    name: str
    units: str = "count"
    data: list[StepMetricEntry] = Field(default_factory=list)


class RoutePoint(BaseModel):
    latitude: float
    longitude: float
    altitude: float | None = None
    timestamp: datetime
    # course, speed, and accuracy fields also arrive here but aren't
    # needed for region attribution — Pydantic drops unrecognized fields
    # by default, so they stay in raw_payload but don't need a home here.

    @field_validator("timestamp", mode="before")
    @classmethod
    def _parse_timestamp_field(cls, value: str | datetime) -> datetime:
        return value if isinstance(value, datetime) else _parse_timestamp(value)


class QtyWithUnit(BaseModel):
    qty: float
    units: str


class WorkoutPayload(BaseModel):
    id: str | None = None
    name: str
    source: str = "unknown"
    start: datetime
    end: datetime
    route: list[RoutePoint] = Field(default_factory=list)
    distance: QtyWithUnit | None = None
    # walkingAndRunningDistance also arrives (a richer per-minute
    # breakdown) but isn't reliably present across workouts — not parsed
    # here, stays in raw_payload. distance is the simpler, more
    # consistently-present whole-workout figure this codebase relies on.

    @field_validator("start", "end", mode="before")
    @classmethod
    def _parse_workout_timestamp(cls, value: str | datetime) -> datetime:
        return value if isinstance(value, datetime) else _parse_timestamp(value)


class IngestData(BaseModel):
    metrics: list[Metric] = Field(default_factory=list)
    workouts: list[WorkoutPayload] = Field(default_factory=list)


class IngestPayload(BaseModel):
    data: IngestData
