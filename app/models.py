from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
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
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
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


class Region(Base):
    """A location-seeded drop-table boundary. Flat for now — hierarchy is
    a later schema decision that needs real region data to make well.

    Geometry and naming come from an operator-supplied data source at
    load time (see scripts/load_regions.py), not from literals in code.
    """

    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    polygon_geojson: Mapped[str] = mapped_column(Text)
    always_unlocked: Mapped[bool] = mapped_column(Boolean, default=False)
    unlock_cost_fragments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SessionTierConfig(Base):
    """A version of the session-tier roll mechanic. Same versioning
    discipline as PassiveTierConfig: never mutated, retunes insert a new
    row effective from that point."""

    __tablename__ = "session_tier_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    roll_interval_minutes: Mapped[int] = mapped_column(Integer)
    max_rolls_per_session: Mapped[int] = mapped_column(Integer)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DropTable(Base):
    """A region's drop table. One per region for now — inheritance across
    a region hierarchy is a later schema decision, same as the hierarchy
    itself."""

    __tablename__ = "drop_tables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), unique=True)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    bands: Mapped[list["DropTableBand"]] = relationship(
        back_populates="drop_table", cascade="all, delete-orphan", order_by="DropTableBand.roll_min"
    )


class DropTableBand(Base):
    """One roll-range band within a table (e.g. common, rare, ...)."""

    __tablename__ = "drop_table_bands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    drop_table_id: Mapped[int] = mapped_column(ForeignKey("drop_tables.id"))
    tier: Mapped[str] = mapped_column(String(32))
    roll_min: Mapped[int] = mapped_column(Integer)
    roll_max: Mapped[int] = mapped_column(Integer)

    drop_table: Mapped[DropTable] = relationship(back_populates="bands")
    items: Mapped[list["DropTableItem"]] = relationship(
        back_populates="band", cascade="all, delete-orphan"
    )


class DropTableItem(Base):
    """One possible result within a band. A roll landing in the band picks
    uniformly among its items."""

    __tablename__ = "drop_table_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    band_id: Mapped[int] = mapped_column(ForeignKey("drop_table_bands.id"))
    name: Mapped[str] = mapped_column(String(255))

    band: Mapped[DropTableBand] = relationship(back_populates="items")


class RegionUnlock(Base):
    """A region's unlock event. Presence of a row means unlocked; absence
    (and not always_unlocked) means locked. Never removed."""

    __tablename__ = "region_unlocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), unique=True)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FragmentLedgerEntry(Base):
    """Append-only Fragment transaction log. Balance is the sum of this
    table plus every PassiveFragmentAward. kind is one of
    'common_conversion' (+) or 'region_unlock' (-)."""

    __tablename__ = "fragment_ledger_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    kind: Mapped[str] = mapped_column(String(32))
    amount: Mapped[int] = mapped_column(Integer)
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)


class WorkoutRollResult(Base):
    """One resolved drop-table roll from a real session. Involves genuine
    randomness at resolution time, so unlike passive Fragments this is
    never recomputed — once rolled, it's permanent, like a raw event in
    its own right."""

    __tablename__ = "workout_roll_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workout_id: Mapped[int] = mapped_column(ForeignKey("raw_workouts.id"))
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))
    tier: Mapped[str] = mapped_column(String(32))
    item_name: Mapped[str] = mapped_column(String(255))
    rolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
