"""Serialize local indexing and retrieval; publish only complete documents."""

import json
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from uuid import UUID

from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, models

from netops_ai.application.chunking import PIPELINE_VERSION, chunk_document
from netops_ai.application.token_chunks import fit_chunks, sentence_chunks
from netops_ai.core.settings import Settings
from netops_ai.domain.documents import DocumentChunk, ExtractedDocument
from netops_ai.domain.retrieval import IndexedDocument, RetrievalError, SearchHit
from netops_ai.infrastructure.embeddings import LocalEmbeddings, TokenEmbeddings
from netops_ai.infrastructure.registry import DocumentRegistry

COLLECTION = "netops_chunks_v1"


class KnowledgeService:
    def __init__(self, settings: Settings, embeddings: TokenEmbeddings | None = None) -> None:
        self.settings = settings
        self.lock = RLock()
        self.embeddings = (
            embeddings
            if embeddings is not None
            else LocalEmbeddings(
                settings.model_cache_dir,
                threads=settings.embedding_threads,
                batch_size=settings.embedding_batch_size,
                local_files_only=settings.model_local_files_only,
            )
        )
        fingerprint = json.dumps(
            {
                "model": self.embeddings.identity,
                "dimension": self.embeddings.dimension,
                "max_tokens": self.embeddings.max_tokens,
                "distance": "Cosine",
                "pipeline": [PIPELINE_VERSION, settings.token_pipeline],
                "chunk_size": settings.chunk_size,
                "chunk_overlap": settings.chunk_overlap,
            },
            sort_keys=True,
        )
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.client = QdrantClient(path=str(settings.data_dir / "qdrant"))
        try:
            self.registry = DocumentRegistry(settings.data_dir / "catalog.sqlite3", fingerprint)
            if not self.client.collection_exists(COLLECTION):
                if any(d.status == "indexed" for d in self.registry.list_documents()):
                    raise RetrievalError(
                        "inconsistent_index",
                        "O catálogo existe, mas a coleção vetorial não. "
                        "Restaure os dados juntos a partir de um backup.",
                        409,
                    )
                self.client.create_collection(
                    COLLECTION,
                    vectors_config=models.VectorParams(
                        size=self.embeddings.dimension,
                        distance=models.Distance.COSINE,
                    ),
                )
            # Validate the schema without embedding a dummy query or downloading the model.
            config = self.client.get_collection(COLLECTION).config.params.vectors
            if not isinstance(config, models.VectorParams) or (
                config.size != self.embeddings.dimension
                or config.distance != models.Distance.COSINE
            ):
                raise RetrievalError(
                    "incompatible_index", "Configuração vetorial incompatível.", 409
                )
            self.store = QdrantVectorStore(
                client=self.client,
                collection_name=COLLECTION,
                embedding=self.embeddings,
                validate_collection_config=False,
            )
        except Exception:
            self.client.close()
            raise

    @staticmethod
    def _filter(document_ids: list[str]) -> models.Filter:
        return models.Filter(
            must=[
                models.FieldCondition(
                    key="metadata.document_id",
                    match=models.MatchAny(any=document_ids),
                )
            ]
        )

    def _save_pdf(self, document_id: str, content: bytes) -> None:
        directory = self.settings.knowledge_dir
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{document_id}.pdf"
        if target.exists():
            if sha256(target.read_bytes()).hexdigest() != document_id:
                raise RetrievalError("stored_file_conflict", "O PDF salvo está inconsistente.", 409)
            return
        with NamedTemporaryFile(dir=directory, suffix=".part", delete=False) as temporary:
            temporary.write(content)
            temporary_path = Path(temporary.name)
        try:
            temporary_path.replace(target)
        finally:
            temporary_path.unlink(missing_ok=True)

    def index(self, document: ExtractedDocument, content: bytes) -> tuple[IndexedDocument, bool]:
        with self.lock:
            previous = self.registry.get(document.document_id)
            if previous is not None and previous.status == "indexed":
                return previous, True
            if self.settings.token_pipeline == "pdf-token-v2":
                chunks = sentence_chunks(
                    document, self.embeddings.count_tokens, limit=self.embeddings.max_tokens
                )
            else:
                preview_chunks = chunk_document(
                    document,
                    chunk_size=self.settings.chunk_size,
                    chunk_overlap=self.settings.chunk_overlap,
                )
                chunks = fit_chunks(
                    preview_chunks, self.embeddings.count_tokens, limit=self.embeddings.max_tokens
                )
            if len(chunks) > self.settings.max_index_chunks:
                raise RetrievalError(
                    "too_many_chunks", "O PDF gerou trechos demais para a base.", 413
                )
            self.registry.start(
                document.document_id,
                document.filename,
                len(document.pages),
                len(chunks),
            )
            try:
                self._save_pdf(document.document_id, content)
                # Retry after interruption: remove only this incomplete document's points.
                self.client.delete(COLLECTION, self._filter([document.document_id]), wait=True)
                self.store.add_texts(
                    texts=[chunk.text for chunk in chunks],
                    metadatas=[
                        {key: value for key, value in asdict(chunk).items() if key != "text"}
                        for chunk in chunks
                    ],
                    ids=[str(UUID(chunk.chunk_id[:32])) for chunk in chunks],
                    batch_size=self.settings.embedding_batch_size,
                    wait=True,
                )
                self.registry.set_status(document.document_id, "indexed")
            except Exception:
                # Failed/pending entries are excluded by a search filter, even after a crash.
                self.registry.set_status(document.document_id, "failed")
                raise
            record = self.registry.get(document.document_id)
            assert record is not None
            return record, False

    def list_documents(self) -> list[IndexedDocument]:
        with self.lock:
            return self.registry.list_documents()

    def search(self, query: str, top_k: int, document_id: str | None = None) -> list[SearchHit]:
        with self.lock:
            ids = [
                doc.document_id
                for doc in self.registry.list_documents()
                if doc.status == "indexed"
                and (document_id is None or doc.document_id == document_id)
            ]
            if not ids:
                return []
            if self.embeddings.count_tokens(query) > self.embeddings.max_tokens:
                raise RetrievalError(
                    "query_too_long",
                    "Resuma a pergunta: o modelo aceita até 128 tokens.",
                    422,
                )
            results = self.store.similarity_search_with_score(
                query,
                k=top_k,
                filter=self._filter(ids),
            )
            hits = []
            for document, score in results:
                metadata = document.metadata
                hits.append(
                    SearchHit(
                        chunk=DocumentChunk(
                            chunk_id=metadata["chunk_id"],
                            document_id=metadata["document_id"],
                            filename=metadata["filename"],
                            page=metadata["page"],
                            index=metadata["index"],
                            text=document.page_content,
                        ),
                        score=float(score),
                    )
                )
            return hits

    def close(self) -> None:
        with self.lock:
            self.client.close()
