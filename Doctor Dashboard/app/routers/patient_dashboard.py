"""Doctor-side patient dashboard.

Shows every patient from the patient app (Supabase) with their latest AI report,
and lets the doctor open a patient to read the full report, report history and
the chat the report was generated from.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.dependencies import get_optional_user
from app.services import patient_reports

router = APIRouter(prefix="/patient-dashboard", tags=["patient-dashboard"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)


def require_doctor(user=Depends(get_optional_user)):
    """Patient data is read with the service-role key, so this guard is essential.

    Not logged in -> redirect to the login page (adjust the path to your app).
    """
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


# NOTE: these are plain `def` routes on purpose. The Supabase client is
# synchronous, and FastAPI runs `def` routes in a thread pool, so they don't
# block the event loop.


@router.get("", response_class=HTMLResponse)
def patient_list(
    request: Request,
    q: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    user=Depends(require_doctor),
) -> HTMLResponse:
    try:
        data = patient_reports.list_patients(q=q, priority=priority)
    except Exception:
        logger.exception("Could not load patients from Supabase")
        raise HTTPException(502, "Could not load patient data. Please try again.")

    return templates.TemplateResponse(
        request,
        "patient_dashboard.html",
        {
            "user": user,
            "step": "list",
            "patients": data["patients"],
            "counts": data["counts"],
            "high_priority_count": data["counts"]["high"],
            "q": q or "",
            "priority_filter": priority or "",
        },
    )


@router.get("/patient/{patient_id}", response_class=HTMLResponse)
def patient_detail(
    request: Request,
    patient_id: str,
    report: Optional[str] = Query(None, description="report id; defaults to the latest"),
    user=Depends(require_doctor),
) -> HTMLResponse:
    try:
        detail = patient_reports.get_patient_detail(patient_id, report)
    except Exception:
        logger.exception("Could not load patient %s from Supabase", patient_id)
        raise HTTPException(502, "Could not load patient data. Please try again.")
    if not detail:
        raise HTTPException(404, "Patient not found")

    return templates.TemplateResponse(
        request,
        "patient_dashboard.html",
        {"user": user, "step": "detail", **detail},
    )
