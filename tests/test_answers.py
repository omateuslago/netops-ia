import pytest

from netops_ai.application.answers import REFUSAL, Selection, compose_answer, select_evidence
from netops_ai.domain.documents import DocumentChunk
from netops_ai.domain.retrieval import RetrievalError, SearchHit


def test_refusal_and_exact_source():
    hit = SearchHit(DocumentChunk("c", "d", "dns.pdf", 2, 0, "Use displaydns."), 0.6)
    assert compose_answer("q", [hit], Selection(evidence=[]))["answer"] == REFUSAL
    selection = Selection(evidence=[{"chunk_id": "c", "quote": "Use displaydns."}])
    result = compose_answer("q", [hit], selection)
    assert result["sources"][0]["page"] == 2
    assert result["answer"] == "Use displaydns."


@pytest.mark.parametrize("chunk_id,quote", [("unknown", "DNS"), ("c", "inventado")])
def test_fabricated_source_or_quote_is_an_error(chunk_id, quote):
    hit = SearchHit(DocumentChunk("c", "d", "dns.pdf", 1, 0, "DNS"), 0.9)
    with pytest.raises(RetrievalError, match="inválida"):
        compose_answer("q", [hit], Selection(evidence=[{"chunk_id": chunk_id, "quote": quote}]))


def test_missing_model_is_not_a_document_refusal():
    with pytest.raises(RetrievalError) as error:
        select_evidence("q", [], "")
    assert error.value.code == "evaluator_not_configured"
