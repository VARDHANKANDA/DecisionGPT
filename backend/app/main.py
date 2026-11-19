from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestIDMiddleware, SecurityHeadersMiddleware
from app.core.security_config import validate_security_config

configure_logging()
settings = get_settings()
validate_security_config(settings)     # raises SecurityConfigError (no secrets in the message) before a single request is served

app = FastAPI(
    title="DecisionGPT API",
    description="AI-powered business decision-support platform for Indian SMEs.",
    version="0.1.0",
    docs_url="/docs" if settings.docs_active else None,
    redoc_url="/redoc" if settings.docs_active else None,
    openapi_url="/openapi.json" if settings.docs_active else None,
)

app.add_middleware(SecurityHeadersMiddleware, hsts=settings.hardened)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=False,   # the API authenticates with an Authorization header, never a cookie, so browsers need not send credentials
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Research-Token"],
)

register_exception_handlers(app)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def root() -> dict:
    return {"service": "DecisionGPT API", "docs": "/docs" if settings.docs_active else None}


@app.on_event("startup")
def on_startup() -> None:
    from app.db.session import engine, Base, SessionLocal
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    try:
        with SessionLocal() as db:
            from app.services.model_registry_service import sync_from_file_registry
            sync_from_file_registry(db)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Startup registry sync skipped or encountered error: %s", exc)

