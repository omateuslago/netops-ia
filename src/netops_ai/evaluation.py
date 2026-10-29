"""Offline development-set evaluation; never opens the application's live catalog."""

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter
from unicodedata import normalize

from netops_ai.application.knowledge import KnowledgeService
from netops_ai.core.settings import Settings
from netops_ai.domain.retrieval import SearchHit
from netops_ai.infrastructure.embeddings import LocalEmbeddings
from netops_ai.infrastructure.pdf import read_pdf


def normalized(text: str) -> str:
    return " ".join(normalize("NFKC", text).casefold().split())


def rank_hit(hits: list[SearchHit], expected: dict, *, require_evidence: bool) -> int | None:
    for rank, hit in enumerate(hits, 1):
        chunk = hit.chunk
        same_page = chunk.filename == expected["filename"] and chunk.page == expected["page"]
        if same_page and (
            not require_evidence or normalized(expected["evidence"]) in normalized(chunk.text)
        ):
            return rank
    return None


def summarize(results: list[dict]) -> dict:
    positives = [result for result in results if result["expected"] is not None]
    negatives = [result for result in results if result["expected"] is None]
    count = len(positives)
    metrics = {"positive_cases": count, "negative_cases": len(negatives)}
    for kind in ("page", "evidence"):
        ranks = [result[f"{kind}_rank"] for result in positives]
        metrics[f"{kind}_hit_at_1"] = sum(rank == 1 for rank in ranks) / count if count else None
        metrics[f"{kind}_hit_at_3"] = (
            sum(rank is not None and 1 <= rank <= 3 for rank in ranks) / count if count else None
        )
        metrics[f"{kind}_mrr_at_3"] = (
            sum(1 / rank for rank in ranks if rank is not None and 1 <= rank <= 3) / count
            if count
            else None
        )
    metrics["negative_queries_with_candidates"] = sum(
        bool(result["matches"]) for result in negatives
    )
    metrics["median_search_ms"] = (
        median(result["latency_ms"] for result in results) if results else None
    )
    return metrics


def validate_cases(cases: list[dict], documents: dict) -> None:
    ids = [case["id"] for case in cases]
    if not cases or len(ids) != len(set(ids)):
        raise ValueError("O conjunto deve ter perguntas e IDs únicos.")
    for case in cases:
        if not isinstance(case["query"], str) or not case["query"].strip():
            raise ValueError(f"Pergunta vazia: {case['id']}")
        expected = case["expected"]
        if expected is None:
            continue
        document = documents.get(expected["filename"])
        page = expected["page"]
        if document is None or not isinstance(page, int) or not 1 <= page <= len(document.pages):
            raise ValueError(f"Fonte/página inexistente: {case['id']}")
        evidence = normalized(expected["evidence"])
        if not evidence or evidence not in normalized(document.pages[page - 1].text):
            raise ValueError(f"Evidência não encontrada no PDF: {case['id']}")


def evaluate(
    pdf_dir: Path, question_path: Path, cache_dir: Path, token_pipeline: str = "pdf-token-v1"
) -> dict:
    question_bytes = question_path.read_bytes()
    dataset = json.loads(question_bytes)
    # Only the three known public lab PDFs; do not scan personal knowledge folders.
    names = ("netops-lab-dhcp.pdf", "netops-lab-dns.pdf", "netops-lab-conectividade.pdf")
    contents = {name: (pdf_dir / name).read_bytes() for name in names}
    documents = {
        name: read_pdf(content, name, max_bytes=10 * 1024 * 1024, max_pages=100, max_chars=250000)
        for name, content in contents.items()
    }
    validate_cases(dataset["cases"], documents)
    model = LocalEmbeddings(cache_dir.resolve(), local_files_only=True)
    results = []
    with TemporaryDirectory(prefix="netops-lab-eval-") as temporary:
        settings = Settings(
            environment="test",
            data_dir=Path(temporary) / "data",
            knowledge_dir=Path(temporary) / "knowledge",
            _env_file=None,
            chunk_size=900,
            chunk_overlap=150,
            embedding_batch_size=8,
            max_index_chunks=2000,
            token_pipeline=token_pipeline,
        )
        service = KnowledgeService(settings, model)
        try:
            start = perf_counter()
            records = [service.index(documents[name], contents[name])[0] for name in names]
            indexing_seconds = perf_counter() - start
            for case in dataset["cases"]:
                start = perf_counter()
                hits = service.search(case["query"], top_k=3)
                elapsed_ms = (perf_counter() - start) * 1000
                expected = case["expected"]
                results.append(
                    {
                        **case,
                        "page_rank": rank_hit(hits, expected, require_evidence=False)
                        if expected
                        else None,
                        "evidence_rank": rank_hit(hits, expected, require_evidence=True)
                        if expected
                        else None,
                        "latency_ms": round(elapsed_ms, 2),
                        "matches": [{**asdict(hit.chunk), "score": hit.score} for hit in hits],
                    }
                )
        finally:
            service.close()
    return {
        "corpus_version": dataset["corpus_version"],
        "evaluated_at": datetime.now(UTC).isoformat(),
        "model": model.identity,
        "parameters": {
            "chunk_size": 900,
            "chunk_overlap": 150,
            "max_tokens": 128,
            "top_k": 3,
            "token_pipeline": token_pipeline,
        },
        "question_file_sha256": sha256(question_bytes).hexdigest(),
        "documents": [{**asdict(record), "sha256": record.document_id} for record in records],
        "indexing_seconds": round(indexing_seconds, 3),
        "metrics": summarize(results),
        "limitations": [
            "Development set, not a held-out benchmark; no comparison to another model.",
            "Negative queries measure candidate exposure, not hallucinations or refusal accuracy.",
            "Latency measures direct service calls on a tiny isolated corpus, "
            "not HTTP or production load.",
        ],
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-dir", type=Path, default=Path("output/pdf"))
    parser.add_argument("--questions", type=Path, default=Path("examples/lab/questions.json"))
    parser.add_argument("--cache-dir", type=Path, default=Path("data/models"))
    parser.add_argument("--report", type=Path, default=Path("data/evaluation/lab-v1.json"))
    parser.add_argument(
        "--token-pipeline", choices=["pdf-token-v1", "pdf-token-v2"], default="pdf-token-v1"
    )
    args = parser.parse_args()
    # Preserve previous runs; ask for a new report path instead of silently overwriting it.
    if args.report.exists():
        parser.error("Relatório já existe; informe outro caminho com --report.")
    report = evaluate(args.pdf_dir, args.questions, args.cache_dir, args.token_pipeline)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
    print(json.dumps(report["metrics"], ensure_ascii=True, indent=2))
    print(f"Report: {args.report.resolve()}")


if __name__ == "__main__":
    main()
