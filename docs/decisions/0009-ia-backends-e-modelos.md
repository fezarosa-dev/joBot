# 0009. Inteligência artificial: opções, modelos e pacote offline

- **Status:** aceita
- **Data:** 2026-11-13

## Contexto

Algumas pessoas têm assinatura do Claude, outras têm chave de API (uma senha que dá acesso a um serviço pago), outras não querem pagar nem mandar dados para fora do computador. Em todos os casos, a IA não pode inventar experiência. O projeto está em desenvolvimento e ainda não tem código: tudo abaixo é plano.

## Decisão

### Regra de ouro

- A IA só usa dados do perfil da pessoa. Nunca inventa experiência, curso ou habilidade, e mostra quais dados usou.
- Se faltar informação, isso vira uma pergunta que fica salva no perfil.

### Opções de IA (backends)

- Cada tarefa de IA tem liga/desliga, backend e modelo próprios.
- Backends: sessão do Claude Code (ver [0010](0010-claude-code-da-pessoa.md)), chave da API da Anthropic, modelo local, palavras-chave (sem IA) e IA manual. Na IA manual, o joBot monta o pedido, a pessoa cola numa IA de chat e cola a resposta de volta.
- Atalhos de configuração: "Tudo Claude", "Tudo offline" e "Personalizado".

### Modelos padrão com Claude

- Currículo: Sonnet 5.5.
- Nota de encaixe: Haiku 5.5.
- Candidatura: Sonnet 5.5.
- Extensão do navegador: Sonnet 5.5.
- Perguntas extras do questionário: Sonnet 5.5.
- E-mails de alerta: Haiku 5.5.
- Respostas de recrutadores: palavras-chave + Haiku 5.5.
- IDs dos modelos: `claude-haiku-5-5` e `claude-sonnet-5-5`.
- Nunca Opus no app, por causa do custo e do limite de uso.

### Padrão offline

- Em todas as tarefas, o padrão offline é o Qwen (um modelo de IA aberto) rodando no próprio computador.

### Pacote offline

O instalador pergunta uma vez se a pessoa quer o pacote offline. Ele inclui:

- O `llama-server` do llama.cpp (programa que roda modelos de IA no computador), em versão fixa (b12366), conferido por sha256 (uma impressão digital do arquivo). Tamanho: cerca de 23 MB no Linux, 25 MB no Windows e 17 MB no macOS com chip Apple. Licença MIT.
- Um modelo GGUF (formato de arquivo de modelo) fixo, conferido por checksum: Qwen3.5-2B-Q4_K_M (1,28 GB) para 8 GB de RAM, ou Qwen3.5-4B-Q4_K_M (2,74 GB) para 12 GB de RAM ou mais. São as versões da Unsloth, com licença Apache-2.0.
- O modelo de transcrição de áudio (ver [0011](0011-perfil-e-primeira-execucao.md)).

### Como o app fala com o modelo local

- O app roda o `llama-server` como subprocesso e conversa com ele por HTTP, no endpoint `/v1/chat/completions`.
- O app pede a resposta em JSON, com `response_format` do tipo `json_schema`.
- Sem Ollama e sem PyTorch.
- A versão do llama.cpp é fixada por uma tag `bNNNN`, porque o "latest" do GitHub aponta para uma tag antiga (v1.0.0).

### Classificação de e-mail

- Opções: palavras-chave, Haiku, Qwen, Laya (experimento da fase 6) ou Jev (chave paga da TypeSafe AI, com aviso de que os dados vão para um terceiro).

### Marcas

- Claude e Claude Code são marcas da Anthropic. O joBot não é afiliado à Anthropic.

## Consequências

- O joBot funciona sem IA nenhuma (palavras-chave e regras) e sem pagar nada (modelo local ou IA manual).
- Cada backend precisa devolver a mesma saída em JSON, para o resto do app não mudar.

## Pontos em aberto

- Medir a velocidade (tokens por segundo) do Qwen em CPU comum, na fase 3.

## Ver também

- [0010. Usar o Claude Code que a pessoa já tem (sem login dentro do joBot)](0010-claude-code-da-pessoa.md)
- [0011. Perfil, currículo, primeira execução e áudio](0011-perfil-e-primeira-execucao.md)
- [0013. Gmail e avisos](0013-gmail-e-avisos.md)
- [0015. Treino de modelos (fase 6)](0015-treino.md)
