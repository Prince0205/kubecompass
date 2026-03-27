from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from app.auth.rbac import require_role

templates = Jinja2Templates(directory="app/templates")

router = APIRouter()

@router.get("/cluster-overview", response_class=HTMLResponse)
def cluster_overview_page(
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"]))
):
    return templates.TemplateResponse(
        "cluster_overview.html",
        {
            "request": request,
            "user": user
        }
    )
