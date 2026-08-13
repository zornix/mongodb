from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthCheckResponse(BaseModel):
    status: str


@router.get("/health", response_model=HealthCheckResponse)
def handle_health_check() -> HealthCheckResponse:
    return HealthCheckResponse(status="ok")
