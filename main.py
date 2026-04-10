from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routes import router

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(router)


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/dashboard")
async def dashboard():
    return FileResponse("static/dashboard.html")
