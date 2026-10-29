# Resposta extrativa experimental

POST `/api/v1/answer` recebe o mesmo corpo de `/search`. Recupera candidatos e pede ao Ollama local que selecione citações que respondam à pergunta. O servidor verifica que cada ID pertence aos candidatos e que a citação é uma passagem literal do trecho. A resposta reúne essas passagens e suas fontes. `answer_generated: false` significa que o texto final é extrativo; existe uma chamada ao modelo para selecionar evidência.

Sem evidência selecionada, retorna `insufficient_evidence` e `Não encontrei essa informação na documentação disponível.` Base vazia também retorna esse resultado. Falta de configuração, indisponibilidade, saída inválida e citações inventadas são erros HTTP 503; nunca são apresentados como ausência de informação nos documentos.

O Ollama precisa estar servindo em `127.0.0.1:11434`, com um modelo local instalado. Configure `NETOPS_OLLAMA_MODEL` com o nome exato mostrado por `ollama list`, no mesmo PowerShell que inicia a API, e reinicie o servidor. Não é necessário reenviar os PDFs nem mudar as pastas da base v2.

Esta implementação foi verificada com testes de contrato, sem avaliador real disponível. Não há comprovação de qualidade semântica nem de resistência a instruções maliciosas nos documentos. Citações literais podem continuar irrelevantes ou omitir contexto; a validação de substring não prova que respondem à pergunta. Não há limiar de similaridade aprovado. Antes de liberar geração livre, avaliar as perguntas positivas, as negativas de VPN/VLAN/senha e a pergunta sobre empilhadeira, registrando falsas recusas e seleções indevidas.

A integração usa a [API chat do Ollama](https://docs.ollama.com/api/chat) com [saída estruturada](https://docs.ollama.com/capabilities/structured-outputs), temperatura zero, resposta limitada e timeout de 120 segundos. Pergunta e candidatos são enviados apenas ao endereço local fixado. Nenhum comando de rede é executado.
