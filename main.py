from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

from app.routes import router

app = FastAPI()
app.include_router(router)

templates = Jinja2Templates(directory="templates")


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"active_page": "scan"})


@app.get("/dashboard")
async def dashboard(request: Request):
    return templates.TemplateResponse(
        request, "dashboard.html", {"active_page": "dashboard"}
    )


@app.get("/items")
async def items(request: Request):
    return templates.TemplateResponse(request, "items.html", {"active_page": "items"})


@app.get("/receipts")
async def receipts(request: Request):
    return templates.TemplateResponse(
        request, "receipts.html", {"active_page": "receipts"}
    )
