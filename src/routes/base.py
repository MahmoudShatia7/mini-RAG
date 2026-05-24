from fastapi import APIRouter, Depends

try:
    from src.helpers.config import get_settings, settings
except ModuleNotFoundError:
    from helpers.config import get_settings, settings

base_router = APIRouter(
    tags=["api_v1"],
    prefix="/api/v1",
)


@base_router.get("/")
async def welcome(app_settings: settings = Depends(get_settings)):
    return {
        "app_name": app_settings.APP_NAME,
        "app_version": app_settings.APP_VERSION,
    }
