from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from app.dependencies import require_user
from app.supabase_client import db

router = APIRouter()
template = Jinja2Templates(directory="app/templates")


@router.get("/diet", response_class=HTMLResponse)
async def diet_get(
    request: Request,
    user: Any = Depends(require_user),
) -> HTMLResponse:
    disease_response = db.table("diseases").select("*").order("id").execute()
    food_response = db.table("foods").select("*").order("id").execute()

    return template.TemplateResponse(
        request,
        "diet.html",
        {
            "user": user,
            "page_title": "Food Nutrition & Safety Checker",
            "page_description": "Analyze nutritional composition and check food safety against specific clinical conditions and Ayurvedic Prakriti.",
            "foods": food_response.data or [],
            "diseases": disease_response.data or [],
            "selected_food": None,
            "selected_disease": None,
            "assessment": None,
        },
    )


@router.post("/diet", response_class=HTMLResponse)
async def diet_post(
    request: Request,
    food_id: int = Form(...),
    disease_id: int = Form(...),
    user: Any = Depends(require_user),
) -> HTMLResponse:
    disease_response = db.table("diseases").select("*").order("id").execute()
    food_response = db.table("foods").select("*").order("id").execute()

    foods: List[Dict[str, Any]] = (
        food_response.data if isinstance(food_response.data, list) else []
    )
    diseases: List[Dict[str, Any]] = (
        disease_response.data if isinstance(disease_response.data, list) else []
    )

    # Find selected entities safely with explicit type assertions
    selected_food: Optional[Dict[str, Any]] = next(
        (f for f in foods if isinstance(f, dict) and f.get("id") == food_id), None
    )
    selected_disease: Optional[Dict[str, Any]] = next(
        (d for d in diseases if isinstance(d, dict) and d.get("id") == disease_id), None
    )

    # Query Supabase food_disease_rules table
    rule_response = (
        db.table("food_disease_rules")
        .select("*")
        .eq("food_id", food_id)
        .eq("disease_id", disease_id)
        .execute()
    )

    rule_data = rule_response.data
    assessment: Dict[str, str]

    if (
        isinstance(rule_data, list)
        and len(rule_data) > 0
        and isinstance(rule_data[0], dict)
    ):
        first_rule = rule_data[0]
        assessment = {
            "status": str(first_rule.get("safety_status", "Unknown")),
            "details": str(
                first_rule.get("details", "No detailed rationale provided.")
            ),
        }
    else:
        assessment = {
            "status": "Compatible",
            "details": "No specific clinical contraindications recorded for this combination under standard guidelines.",
        }

    return template.TemplateResponse(
        request,
        "diet.html",
        {
            "user": user,
            "page_title": "Food Nutrition & Safety Checker",
            "page_description": "Analyze nutritional composition and check food safety against specific clinical conditions and Ayurvedic Prakriti.",
            "foods": foods,
            "diseases": diseases,
            "selected_food": selected_food,
            "selected_disease": selected_disease,
            "assessment": assessment,
        },
    )
