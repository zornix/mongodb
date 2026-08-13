from fastapi import APIRouter
from pydantic import BaseModel

from app.errors import api_error

router = APIRouter()

_WIDGETS: dict[int, dict] = {
    1: {"id": 1, "name": "flux capacitor"},
    2: {"id": 2, "name": "turbo encabulator"},
}


class Widget(BaseModel):
    id: int
    name: str


class WidgetsListResponse(BaseModel):
    widgets: list[Widget]


class WidgetsGetResponse(BaseModel):
    widget: Widget


@router.get("/widgets", response_model=WidgetsListResponse)
def handle_widgets_list() -> WidgetsListResponse:
    return WidgetsListResponse(widgets=[Widget(**w) for w in _WIDGETS.values()])


@router.get("/widgets/{widget_id}", response_model=WidgetsGetResponse)
def handle_widgets_get(widget_id: int) -> WidgetsGetResponse:
    if widget_id not in _WIDGETS:
        raise api_error(404, "WIDGET_NOT_FOUND", f"no widget with id {widget_id}")
    return WidgetsGetResponse(widget=Widget(**_WIDGETS[widget_id]))
