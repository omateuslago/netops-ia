# Incremento 2B — Indexação e busca semântica local

## O que está pronto

O upload de indexação lê o PDF, preserva páginas, divide o texto, gera embeddings e salva os trechos no Qdrant. Um catálogo SQLite registra o documento. A busca compara o vetor da pergunta com os vetores salvos e devolve até `top_k` trechos com suas fontes. Não há LLM, histórico, resposta técnica automática ou mecanismo de recusa por falta de evidência nesta etapa.

## Decisão do modelo

Baseline: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, versão ONNX quantizada publicada pelo Qdrant, 384 dimensões e orçamento de 128 tokens, incluindo tokens especiais. É multilíngue, inclui português e tem licença Apache-2.0. A integração FastEmbed informa cerca de 0,22 GB para o modelo; arquivos auxiliares e o cache do Windows ocupam espaço adicional. Referências: [modelo original](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) e [registro oficial do FastEmbed](https://github.com/qdrant/fastembed/blob/main/fastembed/text/pooled_embedding.py).

O adaptador fixa o repositório `Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q` na revisão `faf4aa4225822f3bc6376869cb1164e8e3feedd0`, sem executar código remoto. O download carrega arquivos JSON e o modelo ONNX; PDFs e perguntas não são enviados para inferência remota. Não habilitamos rastreamento LangSmith.

Hardware observado durante o desenvolvimento: Intel Core i5-14500T, 20 processadores lógicos, 15,7 GiB de RAM total e aproximadamente 2,5 GiB livres naquele momento; vídeo integrado Intel UHD 770. Por isso usamos CPU, duas threads e lotes de oito trechos. Não comparamos outros modelos nem afirmamos que esta seja a melhor opção. A RAM livre varia e ainda não medimos o pico de memória.

O cache fica em `NETOPS_MODEL_CACHE_DIR` (padrão `data/models`). `NETOPS_MODEL_LOCAL_FILES_ONLY=true` impede acesso ao Hub após preparar o cache. Com o valor `false`, carregar o modelo pode consultar o Hub mesmo quando alguns arquivos já estão em cache. Avisos sobre symlinks no Windows não exigem executar a aplicação como administrador.

## Módulos e sequência

1. `api/routes/retrieval.py`: valida upload/pergunta, inicializa o serviço sob demanda e traduz falhas para HTTP sem expor texto privado nos erros.
2. `application/knowledge.py`: coordena o fluxo e serializa operações desta instância local. Usa o `QdrantVectorStore` do LangChain.
3. `application/token_chunks.py`: subdivide os trechos da prévia até caberem no orçamento real de tokens. Mantém documento, página e texto; os IDs e índices são próprios do pipeline de indexação.
4. `infrastructure/embeddings.py`: conta tokens sem truncamento e executa o modelo local. Perguntas acima de 128 tokens são rejeitadas, não cortadas silenciosamente.
5. `infrastructure/registry.py`: registra documentos, estados e configuração em SQLite. Vetores e texto dos trechos permanecem no Qdrant.

A subdivisão usa cortes próximos a espaços, sem cruzar páginas. Ela conserva o conteúdo, mas não garante preservar frases, tabelas ou a sobreposição de 150 caracteres em cada subtrecho. Isso continua sendo uma baseline a avaliar.

## Endpoints

| Método e rota | Efeito |
| --- | --- |
| `POST /api/v1/documents/preview` | Inspeciona texto e chunks por caracteres; não salva nem carrega o modelo. |
| `POST /api/v1/documents` | Salva o PDF autorizado e indexa. Sucesso: `status: indexed`, `persisted: true`. |
| `GET /api/v1/documents` | Lista registros, inclusive `pending` e `failed`; inicializa armazenamento, mas não o modelo. |
| `POST /api/v1/search` | Recebe `query`, `top_k` (1–10, padrão 3) e `document_id` opcional. Devolve fontes e similaridade cosseno. |

O catálogo detecta duplicatas pelo SHA-256 dos bytes. Renomear o mesmo arquivo não cria outro documento; o primeiro nome é preservado. Alterar os bytes cria outro documento, mesmo se a aparência/texto for idêntica. Um PDF incompleto pode ser reenviado para tentar novamente.

Arquivos completos ficam em `knowledge/<sha256>.pdf`. Catálogo: `data/catalog.sqlite3`. Vetores: `data/qdrant/`. Essas pastas são ignoradas pelo Git, mas **não são criptografadas**. Não envie documentos empresariais confidenciais sem autorização. PDFs já existentes em `knowledge/` não são indexados automaticamente.

## Consistência e limites

- Somente documentos com estado `indexed` participam da busca. Uma falha após inserir alguns vetores deixa o documento `failed` (ou `pending` se o processo for interrompido abruptamente); a busca filtra esses registros.
- Reenviar um documento incompleto remove apenas seus pontos e refaz sua indexação. Seu PDF pode permanecer no disco após uma falha. Não há limpeza administrativa automática nem transação atômica envolvendo SQLite, Qdrant e arquivos.
- Um hash de configuração não é usado: o catálogo guarda uma representação JSON canônica da configuração e a compara integralmente. Modelo/revisão, dimensão, distância, limite de tokens, versão do pipeline, tamanho e overlap precisam coincidir. Mudanças incompatíveis retornam `409`; nenhum índice é apagado ou migrado automaticamente.
- Para experimentar outra configuração, pare o servidor e escolha outro `NETOPS_DATA_DIR`; preserve a base anterior. Reenvie os PDFs à nova base. Não apague pastas como procedimento de correção.
- Um processo/worker por diretório Qdrant local. Requisições de busca aguardam uma indexação em andamento. Não é a arquitetura para alto volume ou múltiplos usuários.
- `max_index_chunks` limita a quantidade de trechos por PDF, não o tamanho total do acervo. A listagem ainda não tem paginação. A validação de quantidade acontece após extração/divisão e não é uma barreira rígida de CPU/RAM.
- Continuam válidas as limitações de upload/PDF descritas em [ingestion-preview.md](ingestion-preview.md): sem OCR e sem sandbox de processamento de arquivos hostis.
- Não há limiar calibrado de relevância. Mesmo uma pergunta sem relação pode receber trechos. `score` não é probabilidade nem porcentagem de certeza; `answer_generated` é sempre `false`.
- Texto recuperado é dado não confiável. Não há LLM nesta etapa, e ainda não foi validada resistência a prompt injection na futura geração.
- Use somente `127.0.0.1`. Ainda não há autenticação, política de acesso, rate limiting, auditoria de segurança ou prontidão para produção.

## Avaliação executada em 27/10/2026

Comando: `python -m pytest --run-semantic -s`. Resultado observado: **74 testes aprovados**, em 10,58 s. As verificações comuns usam embeddings falsos determinísticos com Qdrant/SQLite reais para testar fluxo, não qualidade semântica. O teste opcional usa o modelo real em cache e PDFs sintéticos originais, em diretórios temporários.

Corpus inicial: três PDFs, quatro páginas com conteúdo e seis perguntas em português. A fonte esperada ficou em primeiro lugar em **5/6** casos e entre os três resultados em **6/6**. Como são apenas quatro candidatos, estar entre os três é uma exigência fraca: isso não comprova qualidade geral nem supera uma baseline comparativa.

| Pergunta resumida | Fonte esperada | Posição entre os três | Latência observada |
| --- | --- | --- | --- |
| Quem fornece endereço automaticamente? | dhcp.pdf, p. 1 | 1 | 25,9 ms |
| Acabaram os endereços disponíveis? | dhcp.pdf, p. 2 | 1 | 27,0 ms |
| Qual serviço traduz domínio para IP? | dns.pdf, p. 1 | 3 | 21,7 ms |
| Como consultar nomes de servidores? | dns.pdf, p. 1 | 1 | 22,3 ms |
| Porta sem link e ligação física? | cabeamento.pdf, p. 1 | 1 | 27,4 ms |
| Conector solto ou cabo desconectado? | cabeamento.pdf, p. 1 | 1 | 27,5 ms |

Na terceira pergunta, DHCP ficou em primeiro lugar com similaridade 0,7027. É um contraexemplo concreto à ideia de que uma pontuação relativamente alta garante uma fonte correta. O teste inicial que exigia primeiro lugar em todas falhou; a avaliação passou a registrar essa métrica e verificar a presença da fonte no `top_k=3`, que é o contrato deste incremento. A pergunta e os textos não foram alterados para esconder a falha.

Carregamento a partir do cache e indexação dos três PDFs: 3,09 s. Latências incluem o caminho HTTP em memória do TestClient, com modelo já carregado; não incluem download nem tráfego TCP real. São observações de uma execução, não SLAs ou prova de otimização. Também foi indexado um texto longo para verificar que todos os trechos respeitam 128 tokens e que seu marcador final não é descartado.

## Seu exercício no Swagger

1. Reinicie a API se necessário e atualize `/docs`.
2. Envie o `teste.pdf` que você usou antes em `POST /api/v1/documents`, sem `/preview`.
3. Confirme `persisted: true` e `status: indexed`. Repita o envio e confira `duplicate: true`.
4. Em `/search`, envie `{"query": "Para que serve este documento?", "top_k": 3}`. Compare o texto retornado e a página com o PDF.
5. Reinicie a API, liste documentos e repita a busca para conferir persistência.
6. Para avaliar semântica de verdade, adicione um PDF próprio de DHCP/DNS, faça perguntas com palavras diferentes das do texto e registre quando a fonte correta não aparece. Um único PDF genérico valida apenas o encadeamento.

Próxima decisão conjunta: ampliar a pequena base de testes antes de conectar um LLM. A geração precisará de tratamento explícito para evidência insuficiente e para o erro de ranking observado.
