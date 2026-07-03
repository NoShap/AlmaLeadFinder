"""Lead persistence and the lead state machine."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.lead import Lead, LeadState

# The only transition attorneys can make today. Kept as data so new states
# (e.g. CLOSED) are an entry here, not new branching logic.
ALLOWED_TRANSITIONS: dict[LeadState, set[LeadState]] = {
    LeadState.PENDING: {LeadState.REACHED_OUT},
    LeadState.REACHED_OUT: set(),
}


class InvalidStateTransition(Exception):
    def __init__(self, current: LeadState, requested: LeadState) -> None:
        super().__init__(f"Cannot transition lead from {current.value} to {requested.value}")
        self.current = current
        self.requested = requested


def create_lead(
    db: Session,
    *,
    first_name: str,
    last_name: str,
    email: str,
    resume_path: str,
    resume_filename: str,
    resume_content_type: str,
) -> Lead:
    lead = Lead(
        first_name=first_name,
        last_name=last_name,
        email=email,
        resume_path=resume_path,
        resume_filename=resume_filename,
        resume_content_type=resume_content_type,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def get_lead(db: Session, lead_id: uuid.UUID) -> Lead | None:
    return db.get(Lead, lead_id)


def list_leads(db: Session, *, limit: int = 50, offset: int = 0) -> tuple[list[Lead], int]:
    total = db.scalar(select(func.count()).select_from(Lead)) or 0
    leads = list(
        db.scalars(
            select(Lead).order_by(Lead.created_at.desc(), Lead.id).limit(limit).offset(offset)
        )
    )
    return leads, total


def transition_lead(db: Session, lead: Lead, new_state: LeadState) -> Lead:
    if new_state not in ALLOWED_TRANSITIONS[lead.state]:
        raise InvalidStateTransition(lead.state, new_state)
    lead.state = new_state
    if new_state == LeadState.REACHED_OUT:
        lead.reached_out_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(lead)
    return lead
