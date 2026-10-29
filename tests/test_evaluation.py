"""Metric checks and evidence validation; no model or download required."""

import json
from pathlib import Path

import pytest

from netops_ai.domain.documents import DocumentChunk, DocumentPage, ExtractedDocument
from netops_ai.domain.retrieval import SearchHit
from netops_ai.evaluation import normalized, rank_hit, summarize, validate_cases
from netops_ai.infrastructure.pdf import read_pdf


def hit(filename="dns.pdf", page=1, text="Use ipconfig /displaydns."):
    return SearchHit(DocumentChunk("c", "d", filename, page, 0, text), 0.5)


def test_page_match_is_not_enough_without_evidence():
    expected = {"filename": "dns.pdf", "page": 1, "evidence": "ipconfig /displaydns"}
    hits = [hit(text="DNS apenas"), hit()]
    assert rank_hit(hits, expected, require_evidence=False) == 1
    assert rank_hit(hits, expected, require_evidence=True) == 2
    assert rank_hit([hit(page=2)], expected, require_evidence=True) is None


def test_metrics_keep_negative_queries_out_of_accuracy():
    results = [
        {"expected": {}, "page_rank": 1, "evidence_rank": 2, "latency_ms": 10, "matches": [1]},
        {"expected": {}, "page_rank": 3, "evidence_rank": None, "latency_ms": 20, "matches": [1]},
        {
            "expected": None,
            "page_rank": None,
            "evidence_rank": None,
            "latency_ms": 30,
            "matches": [1],
        },
    ]
    metrics = summarize(results)
    assert metrics["positive_cases"] == 2
    assert metrics["page_hit_at_1"] == 0.5
    assert metrics["page_hit_at_3"] == 1
    assert metrics["evidence_hit_at_1"] == 0
    assert metrics["evidence_hit_at_3"] == 0.5
    assert metrics["evidence_mrr_at_3"] == 0.25
    assert metrics["negative_queries_with_candidates"] == 1
    assert metrics["median_search_ms"] == 20


def test_normalization_and_empty_metrics():
    assert normalized("RESOLUÇÃO\n de nomes") == "resolução de nomes"
    assert summarize([])["evidence_hit_at_3"] is None
    outside = [{"expected": {}, "page_rank": 4, "evidence_rank": 4, "latency_ms": 1, "matches": []}]
    assert summarize(outside)["evidence_hit_at_3"] == 0
    assert summarize(outside)["page_mrr_at_3"] == 0


@pytest.mark.parametrize("page,evidence", [(0, "DNS"), (2, "DNS"), (1, ""), (1, "ausente")])
def test_invalid_gold_is_rejected(page, evidence):
    documents = {"dns.pdf": ExtractedDocument("d", "dns.pdf", (DocumentPage(1, "DNS"),))}
    case = {
        "id": "q",
        "query": "DNS?",
        "expected": {"filename": "dns.pdf", "page": page, "evidence": evidence},
    }
    with pytest.raises(ValueError):
        validate_cases([case], documents)


def test_delivered_pdfs_match_the_development_set():
    root = Path(__file__).resolve().parents[1]
    corpus = json.loads((root / "examples/lab/corpus.json").read_text(encoding="utf-8"))
    questions = json.loads((root / "examples/lab/questions.json").read_text(encoding="utf-8"))
    assert questions["corpus_version"] == corpus["version"]
    documents = {}
    for item in corpus["documents"]:
        content = (root / "output/pdf" / item["filename"]).read_bytes()
        doc = read_pdf(content, item["filename"], max_bytes=1000000, max_pages=10, max_chars=30000)
        assert len(doc.pages) == 2
        for page, original in zip(doc.pages, item["pages"], strict=True):
            assert "\x7f" not in page.text
            for section in original["sections"]:
                assert normalized(section["text"]) in normalized(page.text)
        documents[doc.filename] = doc
    assert len(questions["cases"]) == 15
    validate_cases(questions["cases"], documents)
