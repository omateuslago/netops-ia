"""Versioned API router."""

from fastapi import APIRouter

from netops_ai.api.routes.documents import router as documents_router
from netops_ai.api.routes.health import router as health_router
from netops_ai.api.routes.retrieval import router as retrieval_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(documents_router)
api_router.include_router(retrieval_router)
