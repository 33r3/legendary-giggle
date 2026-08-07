"""Retries parsing for every stored event that failed to parse the first
time. Run this after fixing app/schemas.py to match a real payload shape
— nothing was ever lost, so previously-unparseable deliveries become
usable retroactively.
"""

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.ingest import apply_parsed_payload
from app.models import IngestEvent
from app.schemas import IngestPayload


def reparse_failed_events(db: Session) -> tuple[int, int]:
    """Returns (fixed, still_failing)."""
    failed = db.execute(select(IngestEvent).where(IngestEvent.parse_error.is_not(None))).scalars().all()

    fixed = 0
    still_failing = 0
    for event in failed:
        try:
            payload = IngestPayload.model_validate_json(event.raw_payload)
        except ValidationError as exc:
            event.parse_error = str(exc)
            db.commit()
            still_failing += 1
            continue

        apply_parsed_payload(db, event, payload)
        fixed += 1

    return fixed, still_failing


def main() -> None:
    db = SessionLocal()
    try:
        fixed, still_failing = reparse_failed_events(db)
        print(f"reparsed {fixed} event(s), {still_failing} still failing")
    finally:
        db.close()


if __name__ == "__main__":
    main()
