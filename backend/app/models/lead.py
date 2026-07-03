import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LeadState(str, enum.Enum):
    PENDING = "PENDING"
    REACHED_OUT = "REACHED_OUT"


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Stored lowercase; unique so one prospect (by email) has exactly one lead.
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)

    # Storage key of the uploaded resume; never exposed directly — files are streamed
    # through the authenticated download endpoint.
    resume_path: Mapped[str] = mapped_column(String(512), nullable=False)
    resume_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    resume_content_type: Mapped[str] = mapped_column(String(255), nullable=False)

    state: Mapped[LeadState] = mapped_column(
        Enum(LeadState, name="lead_state"), nullable=False, default=LeadState.PENDING
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    reached_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
