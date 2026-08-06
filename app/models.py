from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class IngestEvent(Base):
    """One received webhook delivery, stored verbatim. Never updated."""

    __tablename__ = "raw_ingest_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    raw_payload: Mapped[str] = mapped_column(Text)

    step_samples: Mapped[list["StepSample"]] = relationship(back_populates="ingest_event")
    workouts: Mapped[list["Workout"]] = relationship(back_populates="ingest_event")


class StepSample(Base):
    """A step-count interval as reported by the export app. Source-attributed,
    not deduplicated here — dedup happens in the derived reward layer."""

    __tablename__ = "raw_step_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ingest_event_id: Mapped[int] = mapped_column(ForeignKey("raw_ingest_events.id"))
    source: Mapped[str] = mapped_column(String(255))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    quantity: Mapped[float] = mapped_column(Float)
    units: Mapped[str] = mapped_column(String(32))

    ingest_event: Mapped[IngestEvent] = relationship(back_populates="step_samples")


class Workout(Base):
    """A single HKWorkout, e.g. an outdoor walk session."""

    __tablename__ = "raw_workouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ingest_event_id: Mapped[int] = mapped_column(ForeignKey("raw_ingest_events.id"))
    external_id: Mapped[str] = mapped_column(String(255))
    workout_type: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(255))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[float] = mapped_column(Float)

    ingest_event: Mapped[IngestEvent] = relationship(back_populates="workouts")
    route_points: Mapped[list["WorkoutRoutePoint"]] = relationship(
        back_populates="workout", order_by="WorkoutRoutePoint.sequence_index"
    )


class WorkoutRoutePoint(Base):
    """One GPS sample from a workout's HKWorkoutRoute, in original order."""

    __tablename__ = "raw_workout_route_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workout_id: Mapped[int] = mapped_column(ForeignKey("raw_workouts.id"))
    sequence_index: Mapped[int] = mapped_column(Integer)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    altitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    workout: Mapped[Workout] = relationship(back_populates="route_points")


class PassiveTierConfig(Base):
    """A version of the passive-tier reward curve. Never mutated after
    creation — a retune inserts a new row effective from that point, so
    past days always recompute against the curve that was live then."""

    __tablename__ = "passive_tier_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    floor_steps: Mapped[int] = mapped_column(Integer)
    steps_per_fragment: Mapped[int] = mapped_column(Integer)
    daily_cap_fragments: Mapped[int] = mapped_column(Integer)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PassiveFragmentAward(Base):
    """Derived, recomputable: one row per day, dropped and rebuilt whenever
    the passive tier is recomputed from raw step data."""

    __tablename__ = "passive_fragment_awards"
    __table_args__ = (UniqueConstraint("award_date", name="uq_passive_fragment_awards_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    award_date: Mapped[date] = mapped_column(Date)
    steps_counted: Mapped[int] = mapped_column(Integer)
    fragments_awarded: Mapped[int] = mapped_column(Integer)
    config_id: Mapped[int] = mapped_column(ForeignKey("passive_tier_configs.id"))
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
