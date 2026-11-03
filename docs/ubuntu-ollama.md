# Primeiro teste com Ollama no Ubuntu

## Ambiente informado

Ubuntu 26.04.1 LTS, Ryzen 7 5825U com Radeon integrada e 16 GB de RAM. Ollama ainda não instalado no computador do usuário. Esses dados foram informados pelo usuário; o ambiente em nuvem é outra máquina.

Candidato inicial: `qwen2.5:3b`, para estabelecer uma referência com um modelo pequeno. Planejar inicialmente para CPU, sem depender de aceleração da Radeon integrada. O desempenho e a qualidade das decisões precisam ser medidos nesse computador; não há benchmark local ainda. Não é necessário escolher o modelo mais recente para validar o primeiro fluxo.

Ollama executa o modelo de linguagem. FastEmbed continua responsável pelos embeddings usados na busca. Instalar Ollama não substitui o modelo de embeddings e não reindexa os PDFs.

## 1. Instalar no computador Ubuntu

Execute no terminal do computador que rodará a API. O [README oficial do Ollama](https://github.com/ollama/ollama#linux), consultado nesta retomada, fornece este instalador para Linux:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

O instalador altera o sistema e pode pedir a senha de administrador. Se `curl` não estiver instalado, instale-o com o gerenciador de pacotes do Ubuntu. A senha é digitada somente no terminal local.

Confira instalação e serviço:

```bash
ollama --version
curl --fail --show-error http://127.0.0.1:11434/api/tags
```

Antes de baixar modelos, a lista pode estar vazia. Se a conexão falhar, confira `systemctl status ollama --no-pager`. Se o serviço instalado estiver parado, inicie com `sudo systemctl start ollama`. Quando a instalação não tiver criado um serviço, `ollama serve` permite executá-lo em um terminal separado; não inicie uma segunda instância se já houver uma ativa.

## 2. Baixar e testar o modelo

```bash
ollama pull qwen2.5:3b
ollama list
ollama run qwen2.5:3b "Responda em português, em uma frase: para que serve o DNS?"
```

Esse teste verifica a execução do modelo e a resposta em português. Não usa os documentos do NetOps AI, portanto não valida RAG. A [página do modelo](https://ollama.com/library/qwen2.5:3b) permite conferir os detalhes do artefato escolhido.

## 3. Preparar a aplicação

Na pasta real do projeto no Ubuntu, verifique `python3 --version`. O pacote declara Python >=3.12 e <3.15; a execução verificada nesta retomada usou 3.12.14. Uma `.venv` copiada do Windows precisa ser substituída por um ambiente criado no Linux; não reaproveite seus executáveis.

Para uma pasta que ainda não tem `.venv`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

Se o comando de criação informar que falta suporte a venv, instale o pacote correspondente ao Python usado. As constraints do repositório são específicas de Windows/Python 3.12; não foram usadas na validação Linux.

Crie `.env` a partir de `.env.example` apenas se ele ainda não existir. Edite ou acrescente a configuração, sem duplicar a chave:

```dotenv
NETOPS_OLLAMA_MODEL=qwen2.5:3b
```

O backend lê `.env` automaticamente. Esse arquivo é ignorado pelo Git. Uma variável `NETOPS_OLLAMA_MODEL` já exportada no terminal tem prioridade sobre o arquivo; se apontar para um modelo antigo, ajuste-a ou remova-a com `unset NETOPS_OLLAMA_MODEL`.

Inicie a aplicação:

```bash
bash iniciar.sh
```

O script usa `.venv/bin/python` e seleciona as mesmas pastas separadas do laboratório v2 usadas pelo atalho Windows. Não modifica nem migra a base v1. Abra <http://127.0.0.1:8000/app>. Execute apenas um servidor por base.

API e Ollama precisam rodar no mesmo computador para a configuração atual, que usa o endereço fixo `127.0.0.1:11434`. Instalar Ollama no Ubuntu pessoal não o torna acessível pelo localhost do ambiente em nuvem.

## 4. Critérios do primeiro teste integrado

Se a base v2 ainda estiver vazia, envie pela interface os três PDFs de `output/pdf/`. O primeiro uso dos embeddings também exige download do modelo. Não altere o pipeline de uma base existente para contornar erros.

Selecione o modo de resposta com Ollama e teste perguntas respondíveis de DNS/cabeamento e perguntas sem resposta na base de laboratório: óleo de empilhadeira, configuração de VLAN/VPN e senha administrativa. Registre pergunta, resposta, fonte/página, tempo, falsa recusa ou seleção indevida. Perguntas negativas dependem do conteúdo da base: se adicionar documentação que as responda, deixam de ser negativas.

Uma resposta HTTP 200 não prova qualidade. Confira se a citação realmente responde à pergunta e preserva ressalvas. Sem evidência documental, a saída exigida é `Não encontrei essa informação na documentação disponível.` Erros de serviço ou modelo são falhas de infraestrutura, não ausência de informação.

Esta etapa ainda é extrativa. Geração fundamentada e histórico de conversas continuam pendentes para a entrega acadêmica.

## Verificação realizada aqui

O launcher passou na verificação de sintaxe Bash e teve a montagem do comando e a seleção de diretórios verificadas com um executável substituto em pasta temporária. Ollama não foi instalado no computador do usuário por esta conversa, e nenhuma inferência real foi validada nesta etapa.
