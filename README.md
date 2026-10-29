# NetOps AI

O NetOps AI será um assistente local de consulta e troubleshooting para redes corporativas. A aplicação usará RAG (Retrieval-Augmented Generation) para responder com base em documentação indexada, apresentar fontes verificáveis e recusar respostas sem evidência suficiente.

## Estado atual

Fase 1 entregue. Fase 2 com prévia, indexação e busca semântica local (incrementos 2A e 2B). A versão atual oferece:

- API FastAPI com versionamento em `/api/v1`;
- configuração validada por variáveis de ambiente;
- endpoints de apresentação e saúde;
- estrutura `src/` instalável;
- testes automatizados e lint;
- diretórios reservados para a base documental e dados locais.
- envio de PDF pela documentação interativa da API;
- extração por página, hash SHA-256 e trechos com fonte preservada;
- validação de arquivo e limites configuráveis de processamento;
- embeddings multilíngues locais em CPU, com limite de tokens verificado;
- Qdrant local persistente e catálogo de documentos em SQLite;
- detecção de duplicatas por conteúdo e retomada de indexações incompletas;
- busca de trechos com arquivo, página e pontuação de similaridade.

A prévia continua sem persistência. O novo endpoint de indexação salva PDFs e vetores. Geração de respostas com LLM, recusa por falta de evidência, histórico, remoção/reindexação administrativa e interface Streamlit ainda serão implementados. A busca atual pode retornar trechos irrelevantes: similaridade não é confiança factual.

## Requisitos

- Python 3.12 recomendado (versão testada no Windows x64; outras versões permitidas pelo pacote ainda não foram validadas);
- Git;
- Internet para instalar dependências e baixar o modelo público no primeiro uso; depois é possível operar com o cache local;
- Ollama será usado na etapa de geração. Docker poderá ser adotado para o servidor Qdrant posteriormente; nenhum deles é exigido nesta etapa.

## Instalação no Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -c constraints-windows-py312.txt -e ".[dev]"
Copy-Item .env.example .env
```

Não sobrescreva um `.env` já configurado; acrescente apenas as opções que precisar. O arquivo de constraints registra versões instaladas no Windows/Python 3.12, sem hashes de distribuição; não é um lock multiplataforma. Em outros ambientes, a resolução e os testes precisam ser validados.

## Executar a API

```powershell
python -m uvicorn netops_ai.main:app --host 127.0.0.1 --reload
```

Abra:

- API: <http://127.0.0.1:8000/>
- Saúde: <http://127.0.0.1:8000/api/v1/health>
- Documentação interativa: <http://127.0.0.1:8000/docs>

Sem ativar o ambiente virtual, o comando equivalente é:

```powershell
.\.venv\Scripts\python.exe -m uvicorn netops_ai.main:app --host 127.0.0.1 --reload
```

## Primeiro teste com um PDF

1. Abra `/docs` e expanda `POST /api/v1/documents/preview` na seção `documents`.
2. Clique em **Try it out** e escolha um PDF com texto selecionável.
3. Clique em **Execute**. O código HTTP esperado é `200`.
4. Confira `page_count`, `chunk_count` e a lista `chunks`. Cada trecho inclui `filename`, `page` e `text`.
5. Compare o trecho com a página física do PDF. Uma página de capa também conta na numeração.

Os padrões são 10 MiB por arquivo, 100 páginas, 250.000 caracteres extraídos, trechos de até 900 caracteres e sobreposição de até 150 caracteres. A configuração está em `.env.example`. PDFs protegidos ou sem texto extraível retornam uma explicação em `detail.message`.

O resultado indica `mode: "preview"` e `persisted: false`: o arquivo ainda não entrou na base de conhecimento. O framework pode usar armazenamento temporário durante o upload, que é fechado ao terminar a requisição.

Veja [docs/ingestion-preview.md](docs/ingestion-preview.md) para entender os módulos, os limites e um exercício prático.

## Indexar e pesquisar

Para iniciar com a base do laboratório v2, dê dois cliques em `iniciar.cmd` ou execute `./iniciar.cmd` no terminal da pasta do projeto. O atalho configura as pastas v2 apenas para esse processo e inicia o servidor. Encerre o servidor anterior antes de usá-lo. Abra `http://127.0.0.1:8000/app`; Ctrl+C encerra a aplicação.

Interface básica: abra `http://127.0.0.1:8000/app` com o servidor rodando. A tela permite enviar PDFs, listar documentos, consultar trechos e selecionar respostas com Ollama. O modo inicial é consulta de trechos e não exige Ollama. O guia da próxima etapa está em [docs/extractive-answer.md](docs/extractive-answer.md).

1. Atualize `/docs` e abra **POST /api/v1/documents** (sem `/preview`). Envie um PDF autorizado com texto selecionável.
2. Confira `status: "indexed"`, `persisted: true` e `duplicate: false`. O primeiro carregamento do modelo demora mais; aguarde a resposta.
3. Em **GET /api/v1/documents**, confira o documento salvo. Reenviar os mesmos bytes retorna `duplicate: true`, mesmo com outro nome; o nome original é mantido.
4. Em **POST /api/v1/search**, clique em **Try it out** e use:

```json
{
  "query": "Para que serve este documento?",
  "top_k": 3
}
```

Confira `matches`: cada resultado inclui `text`, `filename`, `page` e `score`. Não é uma resposta gerada (`answer_generated: false`). Se usar apenas o PDF genérico de teste, você validará o fluxo, não a qualidade da recuperação sobre redes. Depois use um PDF próprio de DHCP/DNS e compare perguntas com suas páginas.

O `document_id` é um filtro opcional: omita-o para pesquisar toda a base. A indexação pode gerar mais trechos que a prévia porque subdivide textos que excedem 128 tokens.

Execute **um único processo/worker** usando a base local. Não abra dois servidores contra o mesmo `data/`. Mantenha `--host 127.0.0.1`: ainda não há autenticação para exposição externa. Os PDFs ficam em `knowledge/<hash>.pdf`; catálogo, vetores e cache ficam em `data/`, ignorados pelo Git. A pasta `knowledge/` não é monitorada automaticamente: use o upload.

Veja [docs/semantic-search.md](docs/semantic-search.md) para decisões, falhas esperadas e resultados medidos.

## Base própria para praticar

Nova etapa experimental: [resposta extrativa com avaliador local](docs/extractive-answer.md), em `POST /api/v1/answer`. Requer Ollama e modelo configurado; a validação semântica com modelo real ainda está pendente.

Experimento novo: [divisão por frases e tokens (v2)](docs/token-chunking-v2.md), com comparação das mesmas perguntas e instruções para testar em outra base. A configuração padrão permanece v1 para não invalidar documentos já indexados.

Há três PDFs autorais em `output/pdf/`, sobre DHCP, DNS e conectividade, com referências oficiais e duas páginas cada. Envie-os manualmente pelo Swagger. Eles não são adicionados automaticamente à sua base.

O [guia da avaliação](docs/lab-evaluation.md) traz 15 perguntas de referência, instruções de uso e limitações observadas. Para avaliar somente esses PDFs, sem alterar sua base atual:

```powershell
.\.venv\Scripts\python.exe -m netops_ai.evaluation --report data/evaluation/minha-avaliacao.json
```

Use um nome de relatório ainda inexistente. O modelo precisa estar no cache local. A avaliação usa Qdrant/SQLite temporários e registra tanto a página recuperada quanto a presença da passagem de evidência no trecho.

## Verificações de qualidade

```powershell
python -m pytest
python -m ruff check src tests
python -m ruff format --check src tests
```

O teste com modelo real é opcional e exige o cache previamente baixado:

```powershell
python -m pytest --run-semantic -s
```

Os testes usam diretórios temporários e não indexam documentos na base de trabalho. A avaliação sintética tem seis perguntas e não representa um benchmark de produção.

## Estrutura

```text
.
├── docs/                  decisões e arquitetura
├── knowledge/             documentos autorizados para indexação
├── src/netops_ai/
│   ├── api/               rotas HTTP
│   ├── application/       chunking, indexação e busca
│   ├── core/              configuração transversal
│   ├── domain/            documentos, páginas, trechos e erros
│   ├── infrastructure/    PDF, embeddings locais e catálogo SQLite
│   └── schemas/           contratos de entrada e saída
├── tests/                 testes automatizados
├── .env.example           configuração segura de exemplo
└── pyproject.toml         pacote e ferramentas Python
```

Leia [docs/architecture.md](docs/architecture.md) para entender a proposta do MVP e [docs/professor-materials-review.md](docs/professor-materials-review.md) para a comparação com o material acadêmico.

## Licença

A licença ainda precisa ser escolhida antes da publicação. Essa decisão deve considerar tanto o objetivo de portfólio quanto as licenças das futuras dependências e dos documentos usados na base de conhecimento.
