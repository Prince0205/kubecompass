from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.auth.rbac import require_role

ui_router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@ui_router.get("/resource/{kind}/{name}", response_class=HTMLResponse)
def resource_detail_page(kind: str, name: str, request: Request, user=Depends(require_role(["admin", "edit", "view"]))):
    return templates.TemplateResponse(
        "resource_detail.html",
        {
            "request": request,
            "user": user,
            "kind": kind,
            "name": name
        }
    )
