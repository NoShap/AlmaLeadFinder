import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import Response
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import require_admin
from app.db.session import get_db
from app.schemas.lead import LeadList, LeadRead, LeadStateUpdate
from app.services import leads as lead_service
from app.services.leads import DuplicateLeadEmail, InvalidStateTransition
from app.services.notifications import send_lead_submission_emails
from app.services.storage import get_storage

router = APIRouter()

_email_adapter = TypeAdapter(EmailStr)

ALLOWED_RESUME_TYPES = {
    "application/pdf": {".pdf"},
    "application/msword": {".doc"},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {".docx"},
}


def _field_error(field: str, message: str) -> HTTPException:
    """Match FastAPI's native validation error shape so the form renders all errors alike."""
    return HTTPException(
        status_code=422,
        detail=[{"loc": ["body", field], "msg": message, "type": "value_error"}],
    )


async def _validate_resume(resume: UploadFile) -> bytes:
    if not resume.filename:
        raise _field_error("resume", "A resume file is required")
    if resume.content_type not in ALLOWED_RESUME_TYPES:
        raise _field_error("resume", "Resume must be a PDF or Word document")
    content = await resume.read(settings.max_resume_bytes + 1)
    if len(content) > settings.max_resume_bytes:
        max_mb = settings.max_resume_bytes // (1024 * 1024)
        raise _field_error("resume", f"Resume must be smaller than {max_mb} MB")
    if not content:
        raise _field_error("resume", "The uploaded resume is empty")
    return content


@router.post("", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
async def create_lead(
    background_tasks: BackgroundTasks,
    first_name: str = Form(..., min_length=1, max_length=255),
    last_name: str = Form(..., min_length=1, max_length=255),
    email: str = Form(...),
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> LeadRead:
    """Public endpoint backing the prospect-facing lead form."""
    try:
        validated_email = _email_adapter.validate_python(email)
    except ValidationError:
        raise _field_error("email", "Enter a valid email address")
    normalized_email = validated_email.lower()

    duplicate_detail = (
        "It looks like we already have your information — "
        "our team will reach out to you soon."
    )
    # Friendly pre-check before accepting the upload; the unique index below is
    # what actually guarantees one lead per email under concurrency.
    if lead_service.get_lead_by_email(db, normalized_email) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=duplicate_detail)

    content = await _validate_resume(resume)
    resume_key = get_storage().save(
        resume.filename or "resume", content, resume.content_type or "application/octet-stream"
    )

    try:
        lead = lead_service.create_lead(
            db,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            email=normalized_email,
            resume_path=resume_key,
            resume_filename=resume.filename or "resume",
            resume_content_type=resume.content_type or "application/octet-stream",
        )
    except DuplicateLeadEmail:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=duplicate_detail)

    # Queued only after the commit above succeeds; runs after the response is sent.
    background_tasks.add_task(
        send_lead_submission_emails,
        first_name=lead.first_name,
        last_name=lead.last_name,
        prospect_email=lead.email,
    )
    return lead


@router.get("", response_model=LeadList, dependencies=[Depends(require_admin)])
def list_leads(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> LeadList:
    leads, total = lead_service.list_leads(db, limit=limit, offset=offset)
    return LeadList(items=leads, total=total)


@router.get("/{lead_id}", response_model=LeadRead, dependencies=[Depends(require_admin)])
def get_lead(lead_id: uuid.UUID, db: Session = Depends(get_db)) -> LeadRead:
    lead = lead_service.get_lead(db, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


@router.patch("/{lead_id}", response_model=LeadRead, dependencies=[Depends(require_admin)])
def update_lead_state(
    lead_id: uuid.UUID, body: LeadStateUpdate, db: Session = Depends(get_db)
) -> LeadRead:
    lead = lead_service.get_lead(db, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    try:
        return lead_service.transition_lead(db, lead, body.state)
    except InvalidStateTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get("/{lead_id}/resume", dependencies=[Depends(require_admin)])
def download_resume(lead_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    lead = lead_service.get_lead(db, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    try:
        content = get_storage().load(lead.resume_path)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    safe_filename = lead.resume_filename.replace('"', "")
    return Response(
        content=content,
        media_type=lead.resume_content_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )
