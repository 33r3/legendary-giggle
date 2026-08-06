from fastapi import Depends, FastAPI, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.ingest import persist_ingest_payload
from app.schemas import IngestPayload

app = FastAPI(title="exercise-rpg ingest")


def verify_webhook_token(authorization: str = Header(...)) -> None:
    settings = get_settings()
    expected = f"Bearer {settings.ingest_webhook_token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="invalid webhook token")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest/healthkit", dependencies=[Depends(verify_webhook_token)])
async def ingest_healthkit(request: Request, db: Session = Depends(get_db)) -> dict[str, int]:
    raw_body = (await request.body()).decode("utf-8")
    payload = IngestPayload.model_validate_json(raw_body)
    event = persist_ingest_payload(db, raw_body, payload)
    return {"ingest_event_id": event.id}
