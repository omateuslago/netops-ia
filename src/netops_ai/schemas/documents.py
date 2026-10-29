"""Public response for inspecting document ingestion before indexing."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChunkPreview(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chunk_id: str
    document_id: str
    filename: str
    page: int = Field(ge=1, description="Posição física da página no PDF, começando em 1.")
    index: int = Field(ge=0, description="Índice do trecho dentro da página, começando em 0.")
    text: str


class DocumentPreview(BaseModel):
    mode: Literal["preview"] = "preview"
    persisted: Literal[False] = False
    document_id: str
    filename: str
    page_count: int
    empty_pages: list[int]
    chunk_count: int
    chunk_size: int
    chunk_overlap: int
    pipeline_version: str
    warnings: list[str]
    chunks: list[ChunkPreview]
