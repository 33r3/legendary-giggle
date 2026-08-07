"""The web dashboard: view status, declare a wager, unlock a region,
and trigger a manual refresh. Server-rendered, no JS build — this is a
personal single-user tool, not a product.
"""

import secrets
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Region
from app.rewards.session_execution import process_pending_sessions
from app.rewards.unlocks import InsufficientFragments, unlock_region
from app.rewards.wager import declare_wager, resolve_all_completed_payoffs
from app.status import (
    fragment_balance,
    latest_wager_declaration,
    latest_wager_payoff,
    recent_finds,
    recent_fragment_activity,
    region_statuses,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
security = HTTPBasic()


def require_login(credentials: HTTPBasicCredentials = Depends(security)) -> None:
    settings = get_settings()
    valid_username = secrets.compare_digest(credentials.username, settings.web_ui_username)
    valid_password = secrets.compare_digest(credentials.password, settings.web_ui_password)
    if not (valid_username and valid_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


def _redirect_home(message: str, error: bool = False) -> RedirectResponse:
    param = "error" if error else "message"
    return RedirectResponse(url=f"/?{param}={quote(message)}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/")
def dashboard(
    request: Request,
    message: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_login),
):
    regions = region_statuses(db)
    finds = []
    for result in recent_finds(db):
        region = db.get(Region, result.region_id)
        finds.append({"result": result, "region_name": region.name if region else "unknown region"})

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "balance": fragment_balance(db),
            "recent_activity": recent_fragment_activity(db),
            "regions": regions,
            "finds": finds,
            "wager_declaration": latest_wager_declaration(db),
            "wager_payoff": latest_wager_payoff(db),
            "message": message,
            "error": error,
        },
    )


@router.post("/wager/declare")
def declare_wager_action(tier: str = Form(...), db: Session = Depends(get_db), _=Depends(require_login)):
    try:
        declaration = declare_wager(db, tier)
    except ValueError as exc:
        return _redirect_home(str(exc), error=True)
    return _redirect_home(f"Declared {declaration.tier} for the period starting {declaration.period_start}")


@router.post("/regions/{slug}/unlock")
def unlock_region_action(slug: str, db: Session = Depends(get_db), _=Depends(require_login)):
    region = db.execute(select(Region).where(Region.slug == slug)).scalar_one_or_none()
    if region is None:
        return _redirect_home(f"No region {slug!r}", error=True)
    try:
        unlock_region(db, region)
    except InsufficientFragments as exc:
        return _redirect_home(f"Can't unlock {region.name}: {exc}", error=True)
    return _redirect_home(f"Unlocked {region.name}")


@router.post("/refresh")
def refresh_action(db: Session = Depends(get_db), _=Depends(require_login)):
    processed_count, results = process_pending_sessions(db)
    payoffs = resolve_all_completed_payoffs(db)
    hits = sum(1 for p in payoffs if p.hit_target)
    return _redirect_home(
        f"Processed {processed_count} workout(s), {len(results)} roll(s). "
        f"Resolved {len(payoffs)} wager period(s), {hits} hit target."
    )
