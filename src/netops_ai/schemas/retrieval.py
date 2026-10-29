"""HTTP contracts for indexing and retrieval, not generated answers."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from netops_ai.schemas.documents import ChunkPreview


class DocumentRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    filename: str
    page_count: int
    chunk_count: int
    status: Literal["pending", "indexed", "failed"]
    created_at: str


class IndexResult(DocumentRecord):
    mode: Literal["index"] = "index"
    persisted: Literal[True] = True
    duplicate: bool
    embedding_model: str


class DocumentList(BaseModel):
    documents: list[DocumentRecord]


class SearchRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{"query": "Para que serve este documento?", "top_k": 3}]},
    )

    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    top_k: int = Field(default=3, ge=1, le=10)
    document_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class SearchMatch(ChunkPreview):
    score: float


class SearchResponse(BaseModel):
    query: str
    answer_generated: Literal[False] = False
    score_kind: Literal["cosine_similarity"] = "cosine_similarity"
    note: str = "Similaridade não é confiança factual. Os trechos ainda precisam ser avaliados."
    matches: list[SearchMatch]
