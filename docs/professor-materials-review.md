# Revisão dos materiais do professor

## Requisitos confirmados

Os slides apresentam o fluxo documento, chunking, embeddings, banco vetorial, recuperação e geração. O exercício exige:

- código Python com LangChain ou LlamaIndex;
- pasta `knowledge/`;
- interface interativa;
- upload dinâmico de PDFs;
- histórico de conversas;
- fontes com documento e página;
- resposta exata para perguntas sem suporte documental.

## O que o exemplo incremental já demonstra

- leitura de PDF, DOCX, PPTX e TXT;
- chunking por quantidade de caracteres;
- embeddings multilíngues com Sentence Transformers;
- persistência local no ChromaDB;
- inclusão incremental de documentos;
- resposta com Ollama em uma interface Streamlit.

## Lacunas do exemplo para o NetOps AI

| Tema | Exemplo do professor | Fundação proposta |
| --- | --- | --- |
| Organização | Cinco módulos diretamente acoplados | API, configuração e camadas evolutivas |
| Fonte por página | A página vira texto e pode se perder no chunking | Página como metadado obrigatório |
| Histórico | Não implementado | SQLite nas próximas fases |
| Upload | Caminho de pasta digitado pelo usuário | Upload validado pela API e pela interface |
| Duplicatas | ID inclui caminho, índice e conteúdo | Hash do arquivo e versão de ingestão |
| Recusa | Instrução flexível no prompt | Mensagem exata mais limiar e validação |
| Testes | Não há testes | Testes desde a Fase 1 |
| Dependências | Sem versões fixadas | Faixas compatíveis e instalação reproduzível |
| Segurança | Sem validação de arquivo ou limites | Validação progressiva e isolamento de conteúdo |

## Decisão

O exemplo serve como material didático, mas seu código não será copiado. Vamos aproveitar a sequência conceitual e implementar componentes próprios, com metadados rastreáveis e contratos que permitam testar o pipeline sem depender de Ollama ou Qdrant ativos.

