# Retomada do NetOps AI

Registro de 2 de novembro de 2026 (America/Sao_Paulo).

## Fontes e ponto de partida

Foram lidos os dois prompts de continuidade, `Aula_RAG.pptx` (18 slides) e `EXERC-Assistente Inteligente de Suporte Técnico Industrial (RAG).pptx` (10 slides). O prompt mestre descreve a visão do produto; o resumo de continuação descreve uma implementação mais recente. O estado efetivo deve ser confirmado no código e por execução.

Repositório encontrado em `/workspace/netops-ia`, no commit `20e8dad`, sem mudanças locais no início da inspeção. O antigo caminho do Windows não é acessível por este ambiente em nuvem.

O ZIP do professor não foi fornecido nesta retomada. As afirmações antigas sobre seu código não foram revalidadas.

## Requisitos obrigatórios e situação observada

| Requisito | Referência no exercício | Situação no código |
| --- | --- | --- |
| Leitura de PDF, chunking, embeddings e banco vetorial | Slides 4–5 | Implementados com pypdf, divisão por tokens, FastEmbed e Qdrant local |
| Busca vetorial e resposta gerativa | Slide 5, nível 1 | Busca implementada; `/answer` seleciona citações, mas não produz resposta gerativa |
| Interface e upload dinâmico de PDFs | Slide 5, nível 2 | Interface HTML em `/app`, upload e listagem disponíveis; fluxo completo em navegador ainda pendente |
| Fontes com arquivo e página | Slides 6–7 e 9 | Metadados preservados e exibidos; confirmar também na futura geração |
| Recusa exata quando faltar informação | Slides 5 e 8 | Frase implementada; qualidade da decisão do modelo ainda não validada |
| Python com LangChain ou LlamaIndex | Slide 9 | Uso real de `langchain_core.embeddings.Embeddings` e `langchain_qdrant.QdrantVectorStore` |
| Pasta `/knowledge` configurada | Slides 3 e 9 | Diretório e configuração existentes; entrada via upload, sem monitoramento automático da pasta |
| Histórico de conversas ativo | Slide 9 | Pendente; SQLite atual cataloga documentos, não conversas |
| Cenário e base industrial | Slides 1–3 | Base própria atual é de redes; usuário confirmou que ainda não consultou o professor sobre a adaptação |

A mensagem obrigatória é exatamente:

> Não encontrei essa informação na documentação disponível.

O slide 3 apresenta cinco PDFs industriais: manual CNC, procedimento de segurança, manual de compressor, política de manutenção e checklist operacional. Eles não foram enviados nesta retomada. Não presumir que a mudança de domínio foi autorizada. Se necessário, a aplicação pode atender a base industrial para a entrega e a base de redes para o portfólio, com bases separadas.

O enunciado exige controle de alucinações. Isso orienta os critérios de aceitação, mas não constitui uma garantia técnica de que um LLM jamais inventará. A seleção literal atual verifica IDs e substrings; ainda pode selecionar uma passagem irrelevante ou incompleta. Similaridade não é probabilidade de uma resposta estar correta.

## Estado recuperado

- Backend FastAPI, catálogo SQLite, Qdrant local, FastEmbed em CPU e interface HTML. Streamlit, Docker e frontend React são propostas, não componentes atuais.
- Modelo de embeddings configurado: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensões e limite de 128 tokens incluindo tokens especiais.
- Pipeline padrão `pdf-token-v1`. O `iniciar.cmd` seleciona `pdf-token-v2` e as pastas de laboratório separadas. Preservar essa separação.
- Três PDFs autorais disponíveis em `output/pdf/`: DHCP, DNS e conectividade.
- `data/` e `knowledge/` continham apenas arquivos de controle ao iniciar esta retomada. Não há evidência de transferência dos índices ou do cache de modelos antigos.
- Ollama não encontrado neste ambiente. O servidor de inferência esperado pelo código é `127.0.0.1:11434`, na mesma máquina da API. Um Ollama no computador do usuário não aparece automaticamente no localhost da nuvem.
- A configuração lê `.env`. Quando o modelo for escolhido e instalado, `NETOPS_OLLAMA_MODEL=<nome exato>` pode ser persistido nesse arquivo, sem versionar configurações privadas.

Os resultados antigos de 88 testes, quatro testes posteriores e 11/12 evidências em primeiro lugar são relatos históricos. Não equivalem à execução atual nem a uma avaliação independente.

## Verificação desta retomada

- Ambiente isolado `.venv` criado com Python 3.12.14 em Linux; instalação editável de `.[dev]` concluída. As constraints específicas de Windows não foram aplicadas neste Linux.
- `python -m pytest`: **90 passaram e 2 foram ignorados**, em 3,08 segundos. Os dois testes ignorados exigem embeddings reais em cache, ausente aqui. A primeira tentativa ficou bloqueada no ambiente sem permissão de rede e foi interrompida; a execução concluída usou a permissão de rede do executor.
- `python -m ruff check src tests`: aprovado.
- `python -m ruff format --check src tests`: aprovado, 38 arquivos já formatados.
- Servidor Uvicorn iniciado temporariamente com pastas de dados isoladas: `/api/v1/health`, `/app` e `/openapi.json` responderam HTTP 200. O HTML recebido tinha o prefixo da API substituído corretamente. Servidor encerrado após a verificação.
- Não foram validados JavaScript em navegador, busca com embeddings reais, geração/seleção com Ollama nem qualidade das recusas com modelo real.
- Nesta etapa foram alterados apenas documentos do projeto; nenhum pipeline ou banco existente foi migrado.

## Próximos incrementos

Atualização após a resposta do usuário: computador Ubuntu 26.04.1 LTS, Ryzen 7 5825U com Radeon integrada, 16 GB de RAM, sem Ollama instalado. Foi preparado o [guia Ubuntu/Ollama](ubuntu-ollama.md) e o launcher `iniciar.sh`. `qwen2.5:3b` é o candidato inicial para teste em CPU; ainda não foi medido nesse hardware. A autorização de mudança do cenário industrial para redes continua pendente.

1. Confirmar ambiente de execução e hardware do computador que rodará Ollama. Escolher o modelo com base nesses dados e consultar documentação oficial antes da instalação.
2. Validar o modo extrativo com modelo real: perguntas respondíveis de DNS/cabeamento e perguntas ausentes de empilhadeira, VLAN, VPN e senha administrativa. Registrar fontes corretas, falsas recusas, seleções indevidas e falhas de infraestrutura separadamente.
3. Implementar geração fundamentada com referências verificáveis e recusa, preservando o modo de consulta de trechos para investigação.
4. Adicionar histórico persistente e contexto de conversa, sem tratar respostas anteriores do próprio modelo como fonte documental.
5. Fechar a demonstração acadêmica, inclusive o domínio autorizado e o fluxo completo de upload, perguntas, fontes e recusa.
6. Evoluir o portfólio com avaliação independente, reprodução do ambiente, documentação e demonstração. Busca híbrida, reranking e diagnóstico guiado entram quando houver uma necessidade medida.

O desenvolvimento continua em etapas pequenas, com explicação do propósito de cada componente e participação do estudante. O assistente orienta procedimentos; não executa alterações em redes ou equipamentos.
