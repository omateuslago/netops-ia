"""FastAPI application factory."""

from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from netops_ai.api.router import api_router
from netops_ai.core.settings import Settings, get_settings
from netops_ai.infrastructure.embeddings import TokenEmbeddings


def create_app(
    settings: Settings | None = None,
    *,
    embeddings: TokenEmbeddings | None = None,
) -> FastAPI:
    """Create the HTTP application with explicit, testable configuration."""
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            if app.state.knowledge is not None:
                app.state.knowledge.close()
                app.state.knowledge = None

    application = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        description="API do assistente local de suporte a redes corporativas.",
        lifespan=lifespan,
    )
    application.state.settings = app_settings
    application.state.knowledge = None
    application.state.knowledge_lock = Lock()
    application.state.embeddings = embeddings
    application.include_router(api_router, prefix=app_settings.api_v1_prefix)

    @application.get("/app", response_class=HTMLResponse, include_in_schema=False)
    def interface() -> HTMLResponse:
        from html import escape

        page = (Path(__file__).parent / "web" / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(page.replace("__API_PREFIX__", escape(app_settings.api_v1_prefix)))

    @application.get("/", tags=["system"])
    async def root() -> dict[str, str]:
        return {
            "name": app_settings.app_name,
            "docs": "/docs",
            "health": f"{app_settings.api_v1_prefix}/health",
        }

    return application


app = create_app()
