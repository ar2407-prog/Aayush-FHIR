import json
import logging
from typing import Optional, Any
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Form, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.dependencies import get_optional_user
from app.services import intake as intake_service

router = APIRouter(prefix="/patient-portal", tags=["patient-portal"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)


@router.get("", response_class=HTMLResponse)
async def patient_portal_home(
    request: Request, user=Depends(get_optional_user)
) -> HTMLResponse:
    """Renders the dedicated Patient Intake Portal where patients chat with Dr. Ayurveda and submit clinical reports."""
    return templates.TemplateResponse(
        request,
        "patient_portal.html",
        {
            "user": user,
            "page_title": "Patient Portal — AI Clinical Intake",
            "page_description": "Consult with Dr. Ayurveda and send your health report directly to your doctor",
        },
    )


@router.post("/chat")
async def patient_portal_chat(
    request: Request,
    payload: dict[str, Any] = Body(...),
    user=Depends(get_optional_user),
) -> JSONResponse:
    """
    Handles conversation exchanges between patient and AI doctor.
    Expects payload: { user_message: str, chat_history: list, mobile_number: str, abha_id: str }
    """
    user_message = (payload.get("user_message") or "").strip()
    if not user_message:
        return JSONResponse({"error": "Empty message"}, status_code=400)

    chat_history = payload.get("chat_history") or []
    mobile_number = payload.get("mobile_number")
    abha_id = payload.get("abha_id")

    # Add user message to history
    chat_history.append({"role": "user", "text": user_message})

    # Fetch past intake context if patient has provided mobile or ABHA ID
    past_intakes = []
    if mobile_number or abha_id:
        past_intakes = intake_service.get_past_intakes_for_patient(
            mobile_number, abha_id
        )
    medical_context = format_medical_history(past_intakes)

    # Emergency keyword detection in user message
    user_emergency = detect_emergency(user_message)

    try:
        ai_response, is_emergency = await get_ai_response(
            user_message, chat_history, medical_context
        )
        is_emergency = is_emergency or user_emergency
    except Exception as exc:
        logger.exception("AI doctor consultation error: %s", exc)
        return JSONResponse(
            {
                "error": "Failed to connect to Dr. Ayurveda. Please try again.",
                "is_emergency": user_emergency,
            },
            status_code=500,
        )

    # Append assistant reply to history
    chat_history.append({"role": "assistant", "text": ai_response})

    return JSONResponse(
        {
            "ai_response": ai_response,
            "is_emergency": is_emergency,
            "chat_history": chat_history,
        }
    )


@router.post("/submit")
async def patient_portal_submit(
    request: Request,
    payload: dict[str, Any] = Body(...),
    user=Depends(get_optional_user),
) -> JSONResponse:
    """
    Finalizes the patient consultation:
    1. Generates the structured clinical report JSON from the chat.
    2. Saves the intake record into `patient_intakes`.
    3. Returns the intake ID & report confirmation for the patient.
    """
    full_name = (payload.get("full_name") or "Patient").strip()
    mobile_number = (payload.get("mobile_number") or "").strip()
    abha_id = (payload.get("abha_id") or "").strip() or None
    symptoms = payload.get("symptoms") or []
    if isinstance(symptoms, str):
        symptoms = [s.strip() for s in symptoms.split(",") if s.strip()]

    symptom_notes = (payload.get("symptom_notes") or "").strip()
    chat_history = payload.get("chat_history") or []

    if not chat_history:
        return JSONResponse(
            {"error": "Please complete an AI consultation before submitting."},
            status_code=400,
        )

    # Detect emergencies in conversation history
    all_user_text = " ".join(
        msg.get("text", "") for msg in chat_history if msg.get("role") == "user"
    )
    detected_red_flags = [
        kw for kw in EMERGENCY_KEYWORDS if kw in all_user_text.lower()
    ]
    is_emergency = len(detected_red_flags) > 0 or payload.get("is_emergency", False)
    triage_priority = "high" if is_emergency else "routine"

    # Build structured clinical intake report JSON
    report_json = build_prescription_json(
        patient_name=full_name,
        symptoms=symptoms,
        conversation=chat_history,
        is_emergency=is_emergency,
        triage_priority=triage_priority,
        red_flags=detected_red_flags,
    )

    # Extract user transcript for doctor quick review
    voice_transcript = "\n".join(
        f"Patient: {msg.get('text', '')}"
        for msg in chat_history
        if msg.get("role") == "user"
    )

    # Insert intake into database
    intake_data = {
        "full_name": full_name,
        "mobile_number": mobile_number,
        "abha_id": abha_id,
        "symptoms": symptoms,
        "symptom_pills": symptoms,
        "symptom_notes": symptom_notes,
        "ai_chat_history": chat_history,
        "prescription_json": report_json,
        "triage_priority": triage_priority,
        "red_flags": detected_red_flags,
        "voice_transcript": voice_transcript,
        "extracted_medical_summary": report_json.get("ai_assessment", {}).get(
            "narrative", ""
        ),
    }

    try:
        intake_row = intake_service.insert_intake(intake_data)
        intake_id = intake_row.get("id")
    except Exception as exc:
        logger.exception("Failed to save patient intake: %s", exc)
        return JSONResponse(
            {"error": "Failed to submit intake. Please try again."},
            status_code=500,
        )

    return JSONResponse(
        {
            "success": True,
            "intake_id": intake_id,
            "report": report_json,
            "triage_priority": triage_priority,
            "is_emergency": is_emergency,
            "red_flags": detected_red_flags,
            "message": "Your health intake report has been successfully transmitted to the doctor.",
        }
    )
