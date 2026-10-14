from typing import Optional, Any
from fastapi import APIRouter, Request, Depends, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from app.dependencies import require_user
from app.supabase_client import db
from app.services.intake import expand_search_terms

router = APIRouter()

template = Jinja2Templates(directory="app/templates")


@router.get("/namaste", response_class=HTMLResponse)
async def namaste(
    request: Request,
    q: Optional[str] = Query(None, description="Search query string"),
    domain: Optional[str] = Query(None, description="Domain filter"),
    user: Any = Depends(require_user),
) -> HTMLResponse:
    """Renders the Ayurvedic Concept & Code Search page with live Supabase data and English/Ayurvedic search."""

    # Base query for the 'ayurveda_terms' table
    query = db.table("ayurveda_terms").select("*")
    response = query.order("id").execute()
    all_terms = response.data or []

    # Domain filter (Dosha, Vyadhi, Chikitsa, etc.)
    filtered_terms = all_terms
    if domain and domain.lower() != "all":
        d_lower = domain.lower()
        filtered_terms = [
            t for t in filtered_terms
            if d_lower in (t.get("domain") or "").lower()
            or d_lower in (t.get("srotas") or "").lower()
            or d_lower in (t.get("name") or "").lower()
            or d_lower in (t.get("description") or "").lower()
        ]

    # Search filter (matches English symptoms, Sanskrit concepts, Namaste codes, ICD-11 codes, and descriptions)
    if q and q.strip():
        search_lower = q.strip().lower()
        expanded_keywords = expand_search_terms(search_lower)

        matched = []
        for term in filtered_terms:
            searchable_fields = [
                str(term.get("name") or "").lower(),
                str(term.get("namaste_code") or "").lower(),
                str(term.get("icd11_code") or "").lower(),
                str(term.get("description") or "").lower(),
                str(term.get("srotas") or "").lower(),
                str(term.get("domain") or "").lower(),
            ]
            combined = " ".join(searchable_fields)

            # Direct substring match
            if search_lower in combined:
                matched.append(term)
                continue

            # Expanded synonym keyword match
            if any(kw in combined for kw in expanded_keywords if len(kw) >= 2):
                matched.append(term)
                continue

        terms = matched
    else:
        terms = filtered_terms

    return template.TemplateResponse(
        request,
        "namaste.html",
        {
            "user": user,
            "page_title": "Ayurvedic Concept & Code Search",
            "page_description": "Cross-map Classical Ayurvedic concepts (NAMASTE portal) with modern WHO ICD-11 codings.",
            "terms": terms,
            "total_terms_count": len(all_terms),
            "search_query": q or "",
            "active_domain": domain or "all",
        },
    )
