from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.models.user import User
from app.services.notes_service import get_notes, upsert_note

router = APIRouter(prefix="/api/notes", tags=["notes"], dependencies=[Depends(get_current_user)])


class NoteUpsertRequest(BaseModel):
    employee_id: int
    period_key: str
    note: str


@router.get("")
def list_notes(period_key: str = Query(...)):
    return get_notes(period_key)


@router.put("")
def save_note(payload: NoteUpsertRequest, current_user: User = Depends(get_current_user)):
    return upsert_note(payload.employee_id, payload.period_key, payload.note, current_user.username)
