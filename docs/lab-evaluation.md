# Base de laboratório v1 e avaliação de recuperação

## Entrega de 29/10/2026

Três PDFs autorais de estudo, com duas páginas cada, estão em `output/pdf/`. Os textos tratam de DHCP, DNS e triagem de conectividade IPv4 no Windows 11. Cada página contém referências oficiais; os cenários e exercícios são propostas didáticas nossas, não transcrições de documentação nem procedimentos aprovados de uma empresa.

Foram usadas as referências [DHCP Server](https://learn.microsoft.com/en-us/windows-server/networking/technologies/dhcp/dhcp-top), [visão geral de DNS](https://learn.microsoft.com/en-us/windows-server/networking/dns/dns-overview), [ipconfig](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/ipconfig), [nslookup](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/nslookup) e [ping](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/ping), consultadas em 29/10/2026. Os exemplos usam consulta/observação; consultas de rede geram tráfego e só devem mirar destinos autorizados. Nenhum comando de rede foi executado durante a criação ou avaliação.

Conteúdo editável: `examples/lab/corpus.json`. Perguntas e evidências: `examples/lab/questions.json`. Gerador: `scripts/build_lab_pdfs.py`. PDFs públicos de exemplo podem ser versionados em Git; documentos privados continuam fora do repositório. A licença do projeto ainda precisa ser definida antes da publicação.

## Como experimentar no Swagger

1. Com a API em execução, abra `/docs`.
2. Use `POST /api/v1/documents` para enviar cada um dos três PDFs. Não use `/preview` se quiser pesquisar depois.
3. Confira `status: indexed`. A página física corresponde à página impressa nestes guias, que não têm capa separada.
4. Em `POST /api/v1/search`, envie `{"query": "Como inspecionar as entradas DNS guardadas no computador sem apagá-las?", "top_k": 3}`.
5. Procure a página 2 do guia DNS e um trecho contendo `ipconfig /displaydns`.
6. Experimente a pergunta “A interface cabeada não mostra link. O que observar na conexão física?”. Compare os trechos com a página 1 do guia de conectividade: este é um caso conhecido de perda de contexto na divisão.
7. Faça uma pergunta não coberta, como configuração de VPN IPsec. Observe que receber candidatos **não significa** ter encontrado uma resposta documentada.

Não indexamos automaticamente esses PDFs na sua base. Se você os adicionar junto ao `teste.pdf` ou a outros documentos, o conjunto de candidatos será diferente do usado na avaliação e os resultados podem mudar. Não apague sua base para reproduzir números: use o avaliador isolado abaixo.

## Avaliação reproduzível e isolada

Na raiz do projeto, com o modelo já em cache:

```powershell
.\.venv\Scripts\python.exe -m netops_ai.evaluation --report data/evaluation/minha-avaliacao.json
```

O avaliador usa somente os três PDFs de laboratório, um catálogo e uma base Qdrant temporários. Não abre `data/qdrant` nem altera os PDFs em `knowledge/`. Fecha e remove a base temporária ao terminar. Não baixa o modelo; se o cache estiver ausente, a execução falha. O caminho do relatório precisa ser novo para preservar medições anteriores.

O JSON registra revisão do modelo, parâmetros, SHA-256 dos PDFs e das perguntas, fontes esperadas, os três candidatos completos e latências. A medição final desta entrega está em `data/evaluation/lab-v1-final.json` (ignorada pelo Git). A execução anterior, antes de ajustar um separador do cabeçalho para melhorar sua extração textual, foi preservada em `data/evaluation/lab-v1.json`.

Para regenerar apenas os três PDFs de exemplo, após revisar alterações no corpus:

```powershell
.\.venv\Scripts\python.exe -m pip install -c constraints-windows-py312.txt -e ".[lab]"
.\.venv\Scripts\python.exe scripts/build_lab_pdfs.py --overwrite
```

Sem `--overwrite`, o gerador se recusa a substituir arquivos. A entrega foi gerada com ReportLab 4.4.9 do runtime disponível, renderizada com Poppler e conferida visualmente nas seis páginas. Alterar os PDFs pode mudar hashes, chunks e rankings; avalie de novo e não compare versões diferentes como se fossem o mesmo experimento.

## Critérios e resultados observados

Conjunto de desenvolvimento: 12 perguntas positivas e três sem resposta nesta base. Não é um conjunto independente de teste, nem representa demandas reais em produção. As perguntas não foram usadas para treinar o modelo. O pipeline atual produziu **23 trechos**: oito de DHCP, oito de DNS e sete de conectividade.

Uma fonte esperada é uma combinação de arquivo, página e pequena passagem literal. Antes de avaliar, verificamos que essa passagem existe na página do PDF. A comparação ignora diferenças de maiúsculas, normalização Unicode e espaços/quebras de linha.

| Critério nas 12 perguntas positivas | Resultado |
| --- | --- |
| Arquivo e página esperados no primeiro resultado | 11/12 |
| Arquivo e página esperados entre os três resultados | 12/12 |
| Passagem de evidência completa no primeiro trecho | 10/12 |
| Passagem de evidência completa em algum dos três trechos | 11/12 |
| MRR da evidência, limitado aos três resultados | 0,875 |

MRR é a média do inverso da posição da evidência: primeiro lugar vale 1, segundo vale 1/2, terceiro vale 1/3, ausência vale 0. Um acerto de página não é prova de que o trecho contém a evidência. Por outro lado, uma passagem literal é uma medida restritiva e pode não capturar todas as formas de informação útil; não mede correção de uma resposta gerada.

`dhcp-01` encontrou a página/evidência esperada em segundo lugar. `rede-01` acertou a página em primeiro lugar, mas não trouxe a passagem completa. A subdivisão separou “confira o encaixe” de “do cabo”; a continuação apareceu sem o início. Isso fornece um caso concreto para avaliar chunking com preservação de frases e sobreposição por tokens no próximo incremento. **O algoritmo de produção não foi alterado nesta entrega.**

Nas três perguntas negativas, o buscador retornou candidatos em todos os casos. Isso não é alucinação medida (nenhuma resposta é gerada), mas evidencia ausência de um mecanismo de abstenção. Não se pode considerar a busca fundamentada apenas por retornar resultados ou adotar um limiar arbitrário de score a partir dessas três perguntas.

Indexação dos três PDFs, incluindo carregamento do modelo em cache: **2,386 s**. Mediana de busca nas 15 perguntas: **8,46 ms**. São chamadas diretas ao serviço, sem HTTP, com modelo carregado e uma base minúscula. Não são SLA, pico de memória, teste de carga ou prova de melhoria em relação à avaliação anterior, cujo corpus e caminho de execução eram diferentes.

Os testes de engenharia verificam métricas, páginas e preservação do texto; a nota semântica é registrada separadamente. Não exigimos artificialmente 100% de acertos para declarar que a medição executou corretamente. Os casos negativos não entram no denominador dos acertos positivos.

## Próximo passo proposto

Primeiro, reproduzir o caso `rede-01` no Swagger. Depois, testar uma alteração pequena de chunking em uma base separada e comparar **as mesmas perguntas e PDFs** com este registro. Manter casos de regressão e adicionar perguntas novas não utilizadas para ajustar a solução. Só então avançar para geração com controle de evidência e recusa explícita.
