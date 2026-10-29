"""Small original Portuguese corpus: smoke evidence, not production accuracy."""

import json
from pathlib import Path
from time import perf_counter

import pytest
from fastapi.testclient import TestClient

from netops_ai.application.token_chunks import sentence_chunks
from netops_ai.core.settings import Settings
from netops_ai.infrastructure.embeddings import LocalEmbeddings
from netops_ai.infrastructure.pdf import read_pdf
from netops_ai.main import create_app

pytestmark = pytest.mark.semantic


def test_real_sentence_chunks_preserve_cable_instruction():
    model = LocalEmbeddings(Path("data/models").resolve(), local_files_only=True)
    content = Path("output/pdf/netops-lab-conectividade.pdf").read_bytes()
    document = read_pdf(content, "rede.pdf", max_bytes=1000000, max_pages=10, max_chars=30000)
    chunks = sentence_chunks(document, model.count_tokens)
    assert any("confira o encaixe do cabo" in " ".join(c.text.split()) for c in chunks)
    assert all(model.count_tokens(c.text) <= 128 for c in chunks)


def test_real_portuguese_retrieval_and_token_safety(tmp_path, make_pdf):
    model = LocalEmbeddings(Path("data/models").resolve(), local_files_only=True)
    config = Settings(
        data_dir=tmp_path / "data",
        knowledge_dir=tmp_path / "knowledge",
        _env_file=None,
    )
    corpus = {
        "dhcp.pdf": [
            "Laboratório fictício de DHCP. O serviço entrega endereços IP automaticamente "
            "aos computadores. O cliente solicita uma concessão de endereço na rede.",
            "Falha de distribuição automática de IP: examinar a disponibilidade de endereços "
            "no escopo DHCP. Um escopo esgotado não possui endereços livres para novos clientes.",
        ],
        "dns.pdf": [
            "Laboratório fictício de DNS. A resolução de nomes permite encontrar o endereço "
            "IP associado a um nome de domínio. O resolvedor consulta registros no servidor DNS.",
        ],
        "cabeamento.pdf": [
            "Laboratório fictício de cabeamento. Uma porta Ethernet sem sinal de link pode "
            "indicar um cabo desconectado. Inspecionar os conectores e a conexão física.",
        ],
    }
    cases = [
        ("Quem fornece o endereço automaticamente ao computador?", "dhcp.pdf", 1),
        ("O que ocorre quando acabam os endereços disponíveis para novos clientes?", "dhcp.pdf", 2),
        ("Qual serviço traduz um domínio para seu endereço IP?", "dns.pdf", 1),
        ("Como são consultados os nomes dos servidores?", "dns.pdf", 1),
        ("A porta de rede está sem link. Onde verifico a ligação física?", "cabeamento.pdf", 1),
        ("Pode ser um conector solto ou um fio de rede desconectado?", "cabeamento.pdf", 1),
    ]
    measurements = []
    startup = perf_counter()
    with TestClient(create_app(config, embeddings=model)) as client:
        for filename, pages in corpus.items():
            response = client.post("/api/v1/documents", files={"file": (filename, make_pdf(pages))})
            assert response.status_code == 200, response.text
        indexing_seconds = perf_counter() - startup
        for query, filename, page in cases:
            started = perf_counter()
            result = client.post("/api/v1/search", json={"query": query, "top_k": 3})
            assert result.status_code == 200, result.text
            matches = result.json()["matches"]
            hit = matches[0]
            expected_rank = next(
                (
                    rank
                    for rank, match in enumerate(matches, 1)
                    if (match["filename"], match["page"]) == (filename, page)
                ),
                None,
            )
            measurements.append(
                {
                    "query": query,
                    "expected": [filename, page],
                    "found": [hit["filename"], hit["page"]],
                    "score": round(hit["score"], 4),
                    "latency_ms": round((perf_counter() - started) * 1000, 1),
                    "expected_rank_in_top3": expected_rank,
                }
            )
        # Long source must be split, including the information at the end of the page.
        long_text = (
            "Documentação de laboratório de redes e procedimentos. " * 60 + " MARCADOR_FINAL_XYZ"
        )
        long_result = client.post(
            "/api/v1/documents", files={"file": ("longo.pdf", make_pdf([long_text]))}
        )
        assert long_result.status_code == 200, long_result.text
        service = client.app.state.knowledge
        points, _ = service.client.scroll("netops_chunks_v1", limit=1000, with_payload=True)
        texts = [point.payload["page_content"] for point in points]
        assert all(model.count_tokens(text) <= model.max_tokens for text in texts)
        assert any("MARCADOR_FINAL_XYZ" in text for text in texts)
        assert model.count_tokens("palavra " * 200) > model.max_tokens
    print(
        json.dumps(
            {"indexing_seconds": round(indexing_seconds, 2), "cases": measurements},
            ensure_ascii=False,
        )
    )
    # Contract under test is top_k=3, not a claim that the first hit is always correct.
    assert all(case["expected_rank_in_top3"] is not None for case in measurements)
