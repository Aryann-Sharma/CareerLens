from fastapi import FastAPI

from backend.app.api.routes.analysis import router as analysis_router
from backend.app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Compare a job description with a candidate's skills.",
)

app.include_router(analysis_router)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "healthy"}
