# Incremento 2A: prévia de ingestão

O objetivo desta etapa é verificar o material que a busca vai receber. Não faz sentido otimizar embeddings enquanto as páginas e o texto se perdem na leitura.

Este documento descreve especificamente `/documents/preview`. O incremento 2B já adicionou indexação persistente e busca em rotas separadas; veja [semantic-search.md](semantic-search.md).

## O caminho de um arquivo

```text
PDF enviado em /docs
  → API recebe o arquivo e limita a leitura
  → leitor valida e extrai texto de cada página
  → chunking divide cada página separadamente
  → resposta JSON mostra trechos e referências
```

| Módulo | Responsabilidade |
| --- | --- |
| `domain/documents.py` | Representa documento, página e trecho sem depender de HTTP ou bancos. |
| `infrastructure/pdf.py` | Verifica extensão, cabeçalho, tamanho e páginas; extrai o texto com pypdf; calcula SHA-256 dos bytes originais. |
| `application/chunking.py` | Divide páginas em trechos, conserva quebras de linha e gera IDs repetíveis. |
| `schemas/documents.py` | Define a resposta exibida na API e sua documentação. |
| `api/routes/documents.py` | Recebe o upload, coordena a prévia e traduz erros esperados para HTTP. |
| `core/settings.py` | Valida os limites e os parâmetros de chunking. |

A rota usa `def`: FastAPI executa esse trabalho de leitura e processamento em uma thread. Isso evita executar a extração diretamente no loop assíncrono da API, mas não cria isolamento de memória ou CPU.

## O que os campos significam

- `document_id`: SHA-256 dos bytes do PDF. Renomear o mesmo arquivo mantém o ID. Salvar uma nova versão do PDF pode alterá-lo, mesmo que visualmente o texto pareça igual.
- `page_count`: total de páginas físicas, incluindo capas e páginas vazias.
- `empty_pages`: páginas sem texto extraível. Elas não geram chunks, mas a numeração seguinte continua correta.
- `chunks[].page`: posição física no PDF, começando em 1. Pode diferir do número impresso no rodapé.
- `chunks[].index`: posição do trecho dentro da página, começando em 0.
- `chunks[].chunk_id`: hash que inclui o ID do documento, página, índice, parâmetros, texto e versão do pipeline. Não inclui o nome do arquivo.
- `pipeline_version`: versão das regras de extração/chunking. Mudanças nessas regras deverão incrementar a versão e motivar reindexação.
- `persisted`: sempre `false` nesta etapa.

A prévia não consulta o catálogo nem faz deduplicação persistente. Dois PDFs com os mesmos bytes produzirão os mesmos IDs nesta rota. A deduplicação está disponível no upload de indexação do incremento 2B.

## Chunking inicial

O tamanho é medido em caracteres, não em tokens. O padrão é 900 caracteres com sobreposição de até 150. Sempre que possível, o fim de um trecho respeita uma quebra de parágrafo, linha ou espaço próximo ao limite. As quebras de linha internas permanecem disponíveis para comandos e procedimentos.

Um trecho pertence a uma única página. Essa decisão simplifica citações verificáveis, mas pode separar um procedimento que continua na página seguinte. A sobreposição é por caracteres, portanto o início de um trecho pode cair no meio de uma palavra. Esses são limites conhecidos desta base inicial, que serão avaliados com perguntas reais antes de mudar o algoritmo.

Os valores 900/150 são parâmetros iniciais para medir, não números comprovadamente ideais. Não há comparação de qualidade ou latência de recuperação nesta entrega.

## Experimento para fazer no navegador

1. Reinicie a API após instalar dependências ou mudar o `.env`, e atualize `/docs`.
2. Envie um PDF pequeno e local em `POST /api/v1/documents/preview`.
3. Escolha um trecho em `chunks`. Abra o PDF na posição indicada em `page` e confira o texto.
4. Envie novamente os mesmos bytes com outro nome. Compare `document_id`: deve permanecer igual.
5. Opcionalmente, configure `NETOPS_CHUNK_SIZE=500` e `NETOPS_CHUNK_OVERLAP=80` no `.env`.
6. Reinicie a API e repita a prévia. Compare quantidade de trechos e contexto de cada trecho. Um arquivo curto pode continuar produzindo um único trecho por página.

Se já houver documentos indexados, restaure os parâmetros originais antes de consultar a mesma base: o índice persistente rejeita mudanças incompatíveis. Para experimentar outra configuração de indexação, use uma nova pasta de dados, preservando a anterior.

## Erros esperados

| HTTP | `detail.code` | Motivo |
| --- | --- | --- |
| 415 | `unsupported_file` | Extensão diferente de PDF. |
| 413 | `file_too_large` | Arquivo maior que o limite configurado. |
| 413 | `too_many_pages` | Quantidade de páginas acima do limite. |
| 413 | `too_much_text` | Texto total acima do limite de caracteres. |
| 422 | `invalid_pdf` | Arquivo vazio, cabeçalho inválido ou falha de leitura. |
| 422 | `encrypted_pdf` | PDF protegido. |
| 422 | `no_extractable_text` | Nenhuma página possui texto extraível. Pode ser necessária uma etapa de OCR. |

Se o campo de arquivo estiver ausente, o FastAPI devolve sua resposta padrão de validação HTTP 422, com uma lista em `detail`.

## Limites deste incremento

- Não há OCR, leitura confiável de tabelas complexas ou análise visual de diagramas. Um PDF com imagens e texto só retorna o texto extraível.
- O parser é estrito: alguns PDFs que um visualizador consegue reparar podem ser rejeitados.
- O tamanho do arquivo é validado após o parser multipart receber o upload. Ele pode usar disco temporário antes da rota. Não é um limite de tráfego de rede.
- O limite de caracteres é aplicado após extrair cada página. PDFs compactados podem exigir memória e CPU antes dessa verificação. Os limites não substituem processo isolado, tempo máximo e controle de concorrência em uma futura publicação externa.
- Nome do arquivo serve como rótulo; o sistema descarta caminhos enviados pelo cliente e não grava o PDF em `knowledge/` ou `data/`.
- Conteúdo do documento permanece texto não confiável. Não é executado. O teste com instruções maliciosas verifica somente a preservação de metadados; resistência à manipulação do LLM ainda deverá ser implementada e avaliada na geração.
- A mensagem acadêmica de recusa pertence ao futuro fluxo de perguntas e respostas. Erros de upload usam mensagens próprias para permitir correção do arquivo.

## Verificação realizada

Em 26/10/2026, a suíte local passou em 48 casos: contratos da API, extração, páginas vazias, hashes, limites, erros de entrada, chunking e configurações. Lint passou e a formatação foi aplicada. Os PDFs dos testes são sintéticos, montados em memória; nenhum documento confidencial é necessário.

Dependências adicionadas e instaladas neste incremento: `pypdf 6.21.2` e `python-multipart 0.0.32`. As faixas em `pyproject.toml` permitem atualizações. No incremento 2B foi acrescentado `constraints-windows-py312.txt`, com versões diretas e transitivas observadas no ambiente testado. Ainda não é um lock multiplataforma com hashes.

## Referências de implementação

- [FastAPI: recebimento de arquivos](https://fastapi.tiangolo.com/tutorial/request-files/) documenta `UploadFile`, arquivo temporário e processamento síncrono.
- [pypdf: extração de texto](https://pypdf.readthedocs.io/en/stable/user/extract-text.html) explica leitura por página, limitações de OCR e consumo de memória.
- [pypdf: PdfReader](https://pypdf.readthedocs.io/en/stable/modules/PdfReader.html) descreve modo estrito e identificação de PDFs protegidos.

Continuação implementada: [incremento 2B](semantic-search.md), com embeddings em português, Qdrant e controle de documentos. A consulta mostra trechos recuperados, antes de acrescentarmos um LLM gerador de respostas.
