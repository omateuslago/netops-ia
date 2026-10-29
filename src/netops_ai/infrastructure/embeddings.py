"""A lazy, CPU-only embedding adapter; no remote inference or LLM calls."""

from abc import abstractmethod
from pathlib import Path

from langchain_core.embeddings import Embeddings

from netops_ai.domain.retrieval import RetrievalError

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_REPO = "Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q"
MODEL_REVISION = "faf4aa4225822f3bc6376869cb1164e8e3feedd0"


class TokenEmbeddings(Embeddings):
    """The adapter also exposes full token counts to prevent silent truncation."""

    identity: str
    dimension: int
    max_tokens: int

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count all tokens, including special tokens, without truncation."""


class LocalEmbeddings(TokenEmbeddings):
    identity = f"{MODEL_REPO}@{MODEL_REVISION}"
    dimension = 384
    max_tokens = 128

    def __init__(
        self,
        cache_dir: Path,
        *,
        threads: int = 2,
        batch_size: int = 8,
        local_files_only: bool = False,
    ) -> None:
        self.cache_dir = cache_dir
        self.threads = threads
        self.batch_size = batch_size
        self.local_files_only = local_files_only
        self._model = None
        self._tokenizer = None

    def _load(self) -> None:
        if self._model is not None:
            return
        from fastembed import TextEmbedding
        from huggingface_hub import snapshot_download
        from tokenizers import Tokenizer

        try:
            path = snapshot_download(
                repo_id=MODEL_REPO,
                revision=MODEL_REVISION,
                cache_dir=str(self.cache_dir),
                local_files_only=self.local_files_only,
                allow_patterns=["*.json", "model_optimized.onnx"],
            )
            # Independent tokenizer: token_count() in FastEmbed respects truncation.
            tokenizer = Tokenizer.from_file(str(Path(path) / "tokenizer.json"))
            tokenizer.no_truncation()
            tokenizer.no_padding()
            model = TextEmbedding(
                model_name=MODEL_NAME,
                specific_model_path=path,
                threads=self.threads,
                providers=["CPUExecutionProvider"],
                local_files_only=True,
            )
        except Exception as exc:
            raise RetrievalError(
                "model_unavailable",
                "Não foi possível carregar o modelo local. Verifique a conexão no primeiro "
                "download, o cache em data/models e a memória disponível.",
            ) from exc
        self._tokenizer = tokenizer
        self._model = model

    def count_tokens(self, text: str) -> int:
        self._load()
        return len(self._tokenizer.encode(text).ids)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if any(self.count_tokens(text) > self.max_tokens for text in texts):
            raise RetrievalError("text_too_long", "Texto excede 128 tokens do modelo.", 422)
        return [
            vector.tolist()
            for vector in self._model.embed(
                texts,
                batch_size=self.batch_size,
                parallel=None,
            )
        ]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]
