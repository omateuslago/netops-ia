"""Token budgeting uses an injected counter, independent of any model download."""

import pytest

from netops_ai.application.token_chunks import fit_chunks, sentence_chunks
from netops_ai.domain.documents import DocumentChunk, DocumentPage, ExtractedDocument


def test_sentence_packing_overlap_and_budget():
    text = "Uma frase. Outra frase. Confira o encaixe do cabo. Última frase."
    doc = ExtractedDocument("doc", "rede.pdf", (DocumentPage(1, text), DocumentPage(2, "")))
    counter = lambda value: len(value) + 2  # noqa: E731
    result = sentence_chunks(doc, counter, limit=48, overlap_tokens=16)
    assert all(counter(c.text) <= 48 and c.page == 1 for c in result)
    assert any("Confira o encaixe do cabo." in c.text for c in result)
    for sentence in ("Uma frase.", "Outra frase.", "Confira o encaixe do cabo.", "Última frase."):
        assert any(sentence in c.text for c in result)
    assert sum("Outra frase." in c.text for c in result) == 2
    assert result == sentence_chunks(doc, counter, limit=48, overlap_tokens=16)


def test_long_sentence_fallback_preserves_every_character():
    text = "abc123" * 100
    doc = ExtractedDocument("doc", "rede.pdf", (DocumentPage(3, text),))
    result = sentence_chunks(doc, len, limit=50, overlap_tokens=0)
    assert "".join(c.text for c in result) == text
    assert all(len(c.text) <= 50 and c.page == 3 for c in result)


@pytest.mark.parametrize("limit,overlap", [(2, 0), (128, 128), (128, -1)])
def test_sentence_invalid_budgets(limit, overlap):
    with pytest.raises(ValueError):
        sentence_chunks(
            ExtractedDocument("d", "r.pdf", ()), len, limit=limit, overlap_tokens=overlap
        )


def chunk(text: str, page: int = 1) -> DocumentChunk:
    return DocumentChunk("chunk-original", "doc", "manual.pdf", page, 0, text)


@pytest.mark.parametrize("text", ["abc" * 200, "DNS DHCP conexão " * 40, "VLAN\n192.0.2.1\n" * 40])
def test_splitting_preserves_content_and_budget(text: str) -> None:
    counter = lambda text: len(text) + 2  # noqa: E731
    result = fit_chunks([chunk(text)], counter, limit=100)
    assert len(result) > 1
    assert all(counter(c.text) <= 100 for c in result)
    assert "".join("".join(c.text.split()) for c in result) == "".join(text.split())
    assert [c.index for c in result] == list(range(len(result)))
    assert len({c.chunk_id for c in result}) == len(result)
    assert all(
        c.filename == "manual.pdf" and c.document_id == "doc" and c.page == 1 for c in result
    )


def test_ids_are_deterministic_and_pages_stay_separate() -> None:
    inputs = [chunk("DHCP", 1), chunk("DNS", 3)]
    result = fit_chunks(inputs, len, limit=100)
    assert result == fit_chunks(inputs, len, limit=100)
    assert [c.page for c in result] == [1, 3]
    assert [c.index for c in result] == [0, 0]
    assert result[0].chunk_id != fit_chunks(inputs, len, limit=80)[0].chunk_id


def test_invalid_token_budget() -> None:
    with pytest.raises(ValueError):
        fit_chunks([chunk("x")], len, limit=2)
