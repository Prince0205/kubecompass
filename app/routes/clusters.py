from fastapi import APIRouter, Request, UploadFile, File, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from app.auth.rbac import require_role
from app.db import clusters
import os

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

KUBECONFIG_DIR = "kubeconfigs"
os.makedirs(KUBECONFIG_DIR, exist_ok=True)


@router.get("/clusters")
def clusters_page(
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"]))
):
    data = list(clusters.find())
    return templates.TemplateResponse(
        "clusters.html",
        {"request": request, "user": user, "clusters": data}
    )


@router.post("/clusters/upload")
def upload_cluster(
    name: str = Form(...),
    provider: str = Form(...),
    kubeconfig: UploadFile = File(...),
    user=Depends(require_role(["admin"]))
):
    path = os.path.join(KUBECONFIG_DIR, kubeconfig.filename)

    with open(path, "wb") as f:
        f.write(kubeconfig.file.read())

    clusters.insert_one({
        "name": name,
        "provider": provider,
        "kubeconfig_path": path
    })

    return {"status": "cluster added"}

@router.get("/clusters/select/{cluster_id}")
def select_cluster(
    cluster_id: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"]))
):
    request.session["active_cluster"] = cluster_id
    return RedirectResponse("/namespaces", status_code=302)