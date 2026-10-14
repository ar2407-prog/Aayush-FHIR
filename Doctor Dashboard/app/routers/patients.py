"""
Patient History + EHR intake routes.

Search/filter on the History page and the FHIR bundle on the EHR page are
both computed server-side and rendered directly into HTML — there's no
client-side fetch()/JSON round-trip left. The "Download FHIR JSON" action is
a plain link to /patients/{id}/fhir; the browser handles the download itself
via the Content-Disposition header, no JavaScript required.
"""

import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.dependencies import require_user
from app.services import patients as patients_service
from app.services.fhir import build_fhir_bundle, extract_terminology_mappings

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/history", response_class=HTMLResponse)
async def history_page(
    request: Request, q: str = "", date: str = "", user=Depends(require_user)
):
    patients = patients_service.list_patients(search=q, date=date)
    return templates.TemplateResponse(
        request,
        "history.html",
        {
            "user": user,
            "page_title": "Patient History",
            "page_description": "All patients saved in Supabase — search, review EHRs, and pull FHIR bundles.",
            "patients": patients,
            "q": q,
            "date": date,
        },
    )


@router.get("/ehr", response_class=HTMLResponse)
async def new_patient_page(request: Request, user=Depends(require_user)):
    """The blank intake form for registering a brand-new patient."""
    return templates.TemplateResponse(
        request,
        "ehr.html",
        {
            "user": user,
            "page_title": "EHR Progress Notes Entry",
            "page_description": "Register patients, capture clinical notes, and generate FHIR R4 bundles.",
            "patient": None,
            "encounter": None,
            "prescription": None,
            "mappings": [],
            "fhir_json": json.dumps(
                {"resourceType": "Bundle", "type": "transaction", "entry": []}, indent=2
            ),
        },
    )


@router.get("/ehr/{patient_id}", response_class=HTMLResponse)
async def edit_patient_page(
    request: Request, patient_id: str, user=Depends(require_user)
):
    """The same intake form, pre-filled with a patient's most recent
    encounter/prescription/mappings — the SSR equivalent of the old
    ?patient_id= query param the SPA version used."""
    patient = patients_service.get_patient(patient_id)
    encounter = patients_service.get_latest_encounter(patient_id)
    prescription = patients_service.get_latest_prescription(patient_id)
    mappings = encounter.get("mappings", []) if encounter else []

    bundle = build_fhir_bundle(patient, encounter, prescription, mappings)

    return templates.TemplateResponse(
        request,
        "ehr.html",
        {
            "user": user,
            "page_title": "EHR Progress Notes Entry",
            "page_description": "Register patients, capture clinical notes, and generate FHIR R4 bundles.",
            "patient": patient,
            "encounter": encounter,
            "prescription": prescription,
            "mappings": mappings,
            "fhir_json": json.dumps(bundle, indent=2),
        },
    )


@router.post("/ehr/save")
async def save_ehr(
    request: Request,
    patient_id: str = Form(""),
    full_name: str = Form(...),
    age: str = Form(""),
    gender: str = Form("male"),
    phone: str = Form(""),
    prakriti: str = Form("Vata"),
    chief_complaints: str = Form(""),
    bp: str = Form(""),
    pulse: str = Form(""),
    weight: str = Form(""),
    temp: str = Form(""),
    medical_history: str = Form(""),
    encounter_type: str = Form("ambulatory"),
    speciality: str = Form("kaya_chikitsa"),
    clinical_notes: str = Form(""),
    manual_tags: str = Form(""),
    rx_formulations: str = Form(""),
    rx_pathya: str = Form(""),
    rx_apathya: str = Form(""),
    rx_duration: str = Form(""),
    user=Depends(require_user),
):
    """Handles the single "Save Record & Generate FHIR R4 Bundle" submit:
    upserts the patient, saves the encounter (with its terminology mappings
    persisted), saves the prescription, then redirects to the patient's page
    where the fresh FHIR bundle is rendered."""
    patient_fields = {
        "full_name": full_name.strip(),
        "age": int(age) if age.strip().isdigit() else None,
        "gender": gender,
        "phone": phone.strip(),
        "prakriti": prakriti,
        "chief_complaints": chief_complaints.strip(),
        "vitals": {
            "bp": bp.strip(),
            "pulse": pulse.strip(),
            "weight": weight.strip(),
            "temp": temp.strip(),
        },
        "medical_history": medical_history.strip(),
    }
    patient = patients_service.upsert_patient(
        patient_id or None, user.id, patient_fields
    )

    tags = [tag.strip() for tag in manual_tags.split(",") if tag.strip()]
    mappings = extract_terminology_mappings(clinical_notes)
    patients_service.insert_encounter(
        patient["id"],
        user.id,
        {
            "encounter_type": encounter_type,
            "speciality": speciality,
            "notes": clinical_notes.strip(),
            "manual_tags": tags,
        },
        mappings,
    )

    patients_service.insert_prescription(
        patient["id"],
        user.id,
        {
            "formulations": rx_formulations.strip(),
            "pathya": rx_pathya.strip(),
            "apathya": rx_apathya.strip(),
            "duration": rx_duration.strip(),
        },
    )

    return RedirectResponse(url=f"/ehr/{patient['id']}", status_code=303)


@router.get("/patients/{patient_id}/fhir")
async def download_fhir(patient_id: str, user=Depends(require_user)):
    """Returns the patient's FHIR bundle as a downloadable .json file."""
    patient = patients_service.get_patient(patient_id)
    encounter = patients_service.get_latest_encounter(patient_id)
    prescription = patients_service.get_latest_prescription(patient_id)
    mappings = encounter.get("mappings", []) if encounter else []

    bundle = build_fhir_bundle(patient, encounter, prescription, mappings)
    filename = (
        f"{(patient.get('full_name') or 'patient').replace(' ', '_')}_fhir_bundle.json"
    )

    return JSONResponse(
        content=bundle,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
