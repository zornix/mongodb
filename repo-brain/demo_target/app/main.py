from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException

from app.routes import health, widgets

app = FastAPI(title="demo-target")
app.include_router(health.router)
app.include_router(widgets.router)


@app.exception_handler(HTTPException)
async def envelope_handler(_, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if not (isinstance(detail, dict) and "error" in detail):
        detail = {"error": {"code": "INTERNAL", "message": str(detail)}}
    return JSONResponse(status_code=exc.status_code, content=detail)
