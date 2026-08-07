"""Processes every workout that doesn't yet have roll results. Safe to
rerun — already-processed workouts are left untouched (see
app.rewards.session_execution.process_session).
"""

from app.db import SessionLocal
from app.rewards.session_execution import process_pending_sessions


def main() -> None:
    db = SessionLocal()
    try:
        processed_count, results = process_pending_sessions(db)
        print(f"processed {processed_count} workout(s), {len(results)} roll result(s)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
