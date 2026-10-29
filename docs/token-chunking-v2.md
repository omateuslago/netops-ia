# Divisão por frases e tokens: experimento v2

O tokenizador do modelo transforma texto em unidades do vocabulário e IDs numéricos. Não existe uma equivalência fixa entre palavras, caracteres e tokens. No tokenizador local deste projeto, `Confira o encaixe do cabo.` tem 26 caracteres, cinco palavras e dez tokens incluindo os marcadores de início/fim. A representação observada foi `<s>`, `▁Confira`, `▁o`, `▁en`, `ca`, `ixe`, `▁do`, `▁cabo`, `.`, `</s>`. O símbolo `▁` marca uma fronteira de palavra; não é um caractere acrescentado ao PDF. “encaixe” ocupa três unidades. Tokens não são os 384 números do vetor de embedding.

O [modelo MiniLM adotado](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) utiliza sequências de até 128 tokens nesta configuração. Contamos marcadores especiais dentro desse orçamento. Isso não é um limite universal de IA nem exige 128 palavras. Nosso código subdivide fontes maiores e rejeita perguntas grandes para evitar truncamento silencioso.

## O ajuste

`NETOPS_TOKEN_PIPELINE=pdf-token-v2` usa a página completa, sem primeiro cortá-la em janelas de 900 caracteres. Agrupa frases enquanto a contagem real permite. Repete a última unidade no trecho seguinte quando ela ocupa até 32 tokens (incluindo marcadores) e cabe junto da próxima unidade no limite de 128. Não cruza páginas.

É uma heurística de pontuação, não análise linguística completa. Abreviações podem gerar divisões inadequadas; frases maiores que o limite ainda precisam ser subdivididas. A sobreposição é condicional, não garantida. Cabeçalhos, rodapés e referências ainda participam dos trechos. Os parâmetros 900/150 continuam controlando a prévia e a v1, não o agrupamento da v2. Ainda não alteramos modelo, busca, top-k ou controle de abstenção.

## Comparação controlada

Relatório original: `data/evaluation/lab-v1-final.json`. Novo: `data/evaluation/lab-v2-sentences.json`. Os hashes dos três PDFs e do arquivo das 15 perguntas são idênticos entre execuções; revisão do modelo e top-k=3 também foram mantidos. A base temporária não acessou o catálogo de trabalho.

| Medida nas 12 perguntas positivas | v1 | v2 |
| --- | --- | --- |
| Evidência completa em primeiro lugar | 10/12 | 11/12 |
| Evidência completa entre os três | 11/12 | 12/12 |
| MRR da evidência nos três | 0,875 | 0,9583 |
| Quantidade de trechos | 23 | 20 |

Em `rede-01`, a orientação completa sobre o encaixe do cabo passou a aparecer em primeiro lugar. Nenhuma outra pergunta positiva perdeu posição da evidência nesta amostra. `dhcp-01` permanece em segundo lugar. As três perguntas negativas continuam recebendo candidatos: não foi corrigida a ausência de abstenção. Isto é melhoria neste conjunto de desenvolvimento, não prova de qualidade geral; o ajuste foi motivado por uma pergunta conhecida. Não alegamos ganho de velocidade.

Para reproduzir (modelo já em cache; nome novo para o relatório):

```powershell
.\.venv\Scripts\python.exe -m netops_ai.evaluation --token-pipeline pdf-token-v2 --report data/evaluation/minha-v2.json
```

## Testar no Swagger sem migrar a base antiga

O padrão permanece `pdf-token-v1` para preservar o funcionamento da base existente. Não basta reenviar PDFs à mesma base, pois uploads idênticos são deduplicados. O catálogo impede misturar pipelines e retorna 409 se a configuração mudar sem uma base nova.

Pare o servidor com Ctrl+C. Na raiz do projeto, no mesmo PowerShell:

```powershell
$env:NETOPS_TOKEN_PIPELINE="pdf-token-v2"
$env:NETOPS_DATA_DIR="data/token-v2-lab"
$env:NETOPS_KNOWLEDGE_DIR="knowledge/token-v2-lab"
.\.venv\Scripts\python.exe -m uvicorn netops_ai.main:app --host 127.0.0.1 --reload
```

Envie novamente apenas os três PDFs de laboratório por `/documents` e repita a pergunta sobre conexão física em `/search`. A base nova começa vazia. O cache do modelo continua em `data/models`. Os dados antigos não são apagados. Essas variáveis valem só nessa sessão do PowerShell e não editam o `.env`.

Para voltar, pare o servidor, remova as três variáveis desta sessão e inicie a API novamente para usar sua configuração anterior:

```powershell
Remove-Item Env:NETOPS_TOKEN_PIPELINE,Env:NETOPS_DATA_DIR,Env:NETOPS_KNOWLEDGE_DIR -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m uvicorn netops_ai.main:app --host 127.0.0.1 --reload
```

Os testes acrescentados verificam a preservação de frases, a repetição limitada, o respeito ao orçamento, o caso de frases gigantes, a determinização dos IDs e a orientação sobre o cabo com o tokenizador real. A aprovação dos testes de engenharia não significa que todas as perguntas futuras serão respondidas corretamente.
