"""Subdivide preview chunks without losing text or crossing page boundaries."""

import re
from collections import defaultdict
from collections.abc import Callable, Iterator
from dataclasses import replace
from hashlib import sha256

from netops_ai.domain.documents import DocumentChunk, ExtractedDocument

TOKEN_PIPELINE_VERSION = "pdf-token-v1"
SENTENCE_PIPELINE_VERSION = "pdf-token-v2"


def sentence_chunks(
    document: ExtractedDocument,
    count_tokens: Callable[[str], int],
    *,
    limit: int = 128,
    overlap_tokens: int = 32,
) -> list[DocumentChunk]:
    """Pack whole sentences per page; repeat the last unit only when both budgets allow.

    Sentence detection is heuristic, not linguistic parsing. Oversized sentences use
    the lossless character fallback. Never pre-cut pages into character windows.
    """
    if limit < 3 or not 0 <= overlap_tokens < limit:
        raise ValueError("Use limit >= 3 e 0 <= overlap_tokens < limit.")
    result = []
    for page in document.pages:
        units = [
            part
            for sentence in re.split(r"(?<=[.!?])\s+", page.text.strip())
            if sentence
            for part in _fit(sentence, count_tokens, limit)
        ]
        packed = []
        current = []
        for unit in units:
            candidate = " ".join([*current, unit])
            if current and count_tokens(candidate) > limit:
                packed.append(" ".join(current))
                tail = current[-1]
                current = (
                    [tail]
                    if (
                        count_tokens(tail) <= overlap_tokens
                        and count_tokens(tail + " " + unit) <= limit
                    )
                    else []
                )
            current.append(unit)
        if current:
            packed.append(" ".join(current))
        for index, text in enumerate(packed):
            identity = (
                f"{SENTENCE_PIPELINE_VERSION}:{document.document_id}:{page.number}:"
                f"{index}:{limit}:{overlap_tokens}:{text}"
            )
            result.append(
                DocumentChunk(
                    sha256(identity.encode()).hexdigest(),
                    document.document_id,
                    document.filename,
                    page.number,
                    index,
                    text,
                )
            )
    return result


def _fit(text: str, count_tokens: Callable[[str], int], limit: int) -> Iterator[str]:
    if count_tokens(text) <= limit:
        yield text
        return
    if len(text) < 2:
        raise ValueError("O limite de tokens não comporta um caractere do documento.")
    middle = len(text) // 2
    boundary = text.rfind(" ", len(text) // 4, middle + 1)
    split = boundary + 1 if boundary >= 0 else middle
    for part in (text[:split].strip(), text[split:].strip()):
        if part:
            yield from _fit(part, count_tokens, limit)


def fit_chunks(
    chunks: list[DocumentChunk],
    count_tokens: Callable[[str], int],
    *,
    limit: int,
) -> list[DocumentChunk]:
    if limit < 3:
        raise ValueError("O limite deve comportar texto e tokens especiais.")
    result = []
    indices: dict[int, int] = defaultdict(int)
    for chunk in chunks:
        for part, text in enumerate(_fit(chunk.text, count_tokens, limit)):
            identity = f"{TOKEN_PIPELINE_VERSION}:{chunk.chunk_id}:{limit}:{part}:{text}"
            result.append(
                replace(
                    chunk,
                    chunk_id=sha256(identity.encode()).hexdigest(),
                    index=indices[chunk.page],
                    text=text,
                )
            )
            indices[chunk.page] += 1
    return result
