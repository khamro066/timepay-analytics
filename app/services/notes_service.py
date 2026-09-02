from datetime import datetime

from app.core.database import SessionLocal
from app.models.employee_note import EmployeeNote


def get_notes(period_key: str) -> list[dict]:
    """Notes scoped to a fixed calendar period key (e.g. "2026-09-02",
    "2026-W36", "2026-09") — the same key always finds the same notes,
    regardless of which day it's queried from."""
    db = SessionLocal()
    try:
        notes = db.query(EmployeeNote).filter(EmployeeNote.period_key == period_key).all()
        return [
            {
                "employee_id": n.employee_id,
                "note": n.note,
                "created_by": n.created_by,
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "updated_at": n.updated_at.isoformat() if n.updated_at else None,
            }
            for n in notes
        ]
    finally:
        db.close()


def upsert_note(employee_id: int, period_key: str, note_text: str, created_by: str) -> dict:
    db = SessionLocal()
    try:
        existing = db.query(EmployeeNote).filter_by(employee_id=employee_id, period_key=period_key).one_or_none()

        if note_text.strip() == "":
            if existing is not None:
                db.delete(existing)
                db.commit()
            return {"employee_id": employee_id, "note": "", "created_by": None, "created_at": None, "updated_at": None}

        if existing is None:
            existing = EmployeeNote(
                employee_id=employee_id,
                period_key=period_key,
                note=note_text,
                created_by=created_by,
            )
            db.add(existing)
        else:
            existing.note = note_text
            existing.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(existing)

        return {
            "employee_id": existing.employee_id,
            "note": existing.note,
            "created_by": existing.created_by,
            "created_at": existing.created_at.isoformat() if existing.created_at else None,
            "updated_at": existing.updated_at.isoformat() if existing.updated_at else None,
        }
    finally:
        db.close()
