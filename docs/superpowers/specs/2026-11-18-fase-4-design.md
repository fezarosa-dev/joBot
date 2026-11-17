# Fase 4: IA local e opções de IA (desenho)

Data: 2026-11-18. Decisões de origem: ADR 0007, 0009, 0010, 0011, 0014, 0015, 0017, 0023; D1 (Claude Code), D108 (Ollama pelo compatível com OpenAI), D109 (dica de variações), D122 (modelo leve), D125 (Codex), D138 e D139 (instalador e Contas), D141 (Laya antes da fase 4), D174 e D183.24 (instalador completo; navegador baixado à parte). Escolhas desta sessão: **D185** (para o dono confirmar). Versão alvo: **0.5.0**.

Fatos sobre o código vêm com `arquivo:linha`, conferidos na `dev` em 2026-11-18. As linhas podem andar: quando não bater, procure o símbolo. Valores marcados "(proposta)" foram escolhidos pela sessão e valem para construir; o dono pode trocar. A fase 3 ainda não saiu (T342 e T343 esperam o dono): este desenho só depende do que já está na `dev` (casca, tela de instalação, Ferramentas, Contas, cofre, `processo.py`) e a 0.5.0 só sai depois da 0.4.0 (D185.24).

## 1. Intenção

Quem usa liga a IA se quiser, escolhe onde ela roda (no próprio computador, sem pagar e sem internet depois de baixar, ou num serviço que a pessoa já tem) e ganha três coisas: o encaixe passa a ver as habilidades (o que a pessoa tem e o que falta em cada vaga), a candidatura sai preparada (carta, resumo do currículo, o que tem e o que falta, no idioma da vaga) e o perfil se monta pelo currículo em PDF e por perguntas. A regra de ouro manda em tudo: a IA só usa o que a pessoa disse, nunca inventa, mostra o que usou, e o que faltar vira pergunta (ADR 0009:13-16).

## 2. Objetivos, não objetivos, anti-objetivos

**Objetivos**

- Um contrato comum de IA no núcleo: cada tarefa tem pedido e resposta com esquema fixo; todo backend devolve a mesma saída (ADR 0009, Consequências).
- Quatro tarefas de IA, cada uma com liga/desliga, backend e modelo próprios, **todas desligadas por padrão**: `encaixe` (habilidades da vaga contra o perfil), `candidatura` (preparar a candidatura), `curriculo` (extrair o PDF) e `perguntas` (perguntas de lacuna do perfil) (D185.2).
- Backends: compatível com OpenAI (que atende a OpenAI, o Gemini, o modelo local, o Ollama, o LM Studio e serviços como OpenRouter), API da Anthropic, sessão do Claude Code, sessão do Codex CLI, IA manual (copiar e colar) e "sem IA" (as regras de hoje) (D185.4).
- Modelo local: `llama-server` do llama.cpp e um Qwen3.5 2B ou 4B, baixados da fonte oficial com sha256 fixo, escolhidos pela memória do computador e trocáveis (D139.11, D185.7, D185.19).
- Encaixe com um critério novo, `habilidades`, que continua puro e determinístico: a IA só diz o que a vaga pede e o que o perfil tem; a nota sai das regras (D185.11).
- Perfil: tabelas novas, currículo em PDF (pypdf), questionário com as perguntas do bloco A do mapa e perguntas de lacuna geradas pela IA (ADR 0011; D185.13 a D185.15).
- "Preparar candidatura" no detalhe da vaga (README, seção de candidatura; D185.16).
- Instalador com o grupo "Inteligência artificial (opcional)", Configurações com a aba IA, chaves novas em Serviços, cartões de IA em Ferramentas e Contas (D139.3, D139.8, D139.10, D185.17, D185.20).
- Medir a velocidade do Qwen em CPU (ponto em aberto da ADR 0009:88-90).

**Não objetivos**

- Treinar o Laya: custa dinheiro (RunPod e geração de exemplos), fica preparado e espera o dono (D141, D185.8, seção 15).
- Rótulos por IA ou pelo multilingual-e5-small (ADR 0007:54): voltam junto do Laya (D185.9).
- Áudio e Whisper (fase 6, D139.11), e-mail e respostas de recrutadores (fase 6), extensão do navegador (fase 5), LoRA do Qwen e classificador pessoal (fase 7).
- O Qwen 9B: espera a medida de velocidade (D139.11).
- Campos de busca novos e regras de ocultar novas do mapa do perfil (P2, P3, P5, P6 da spec `2026-11-15-perguntas-do-perfil.md`); viagem e horário como rótulo (P4) (D185.13).
- Lembrar a última escolha do instalador (a D139.3 diz "pode"; D185.17).

**Anti-objetivos**

- IA ligada sem a pessoa ligar, ou dado saindo do computador sem a pessoa escolher um serviço de fora.
- IA que escreve nota livre, envia candidatura ou age sozinha: ela só sugere texto que a pessoa revisa.
- Ollama ou PyTorch dentro do pacote (ADR 0009:69; ADR 0003:21).
- SDK de provedor (anthropic, openai, google-genai): o `httpx` que já existe basta.
- Ler, copiar ou guardar a credencial do Claude Code ou do Codex (ADR 0010:48-62).
- Contornar limite de uso ou termos de serviço de qualquer provedor.

## 3. Restrições

- Camadas (`tests/unidade/test_camadas.py:8-19, 98-113`): o `nucleo` não importa `fastapi`, `starlette`, `jinja2`, `painel`, `agenda`, `banco`, `sistema`, `cli`, `playwright` nem `navegador`; o painel não importa `httpx`; só o `navegador` importa `playwright`. O núcleo pode usar `httpx` (`src/jobot/nucleo/http.py:15`), como o `captcha.py` faz (`src/jobot/nucleo/captcha.py:1-3`).
- O painel escuta só em `127.0.0.1` e não carrega recurso externo; todo POST com CSRF.
- Dependências fixadas com `==` e sem dependência nova sem decisão (ADR 0021). Entram: `pydantic==2.14.3` como dependência direta (já está no `uv.lock` pelo FastAPI, `uv.lock:735-746`; nenhum pacote novo) e `pypdf` (decidida na ADR 0011; licença BSD-3; versão `==` fixada na T412) (D185.3, D185.14).
- Testes sem rede (`tests/conftest.py`): todo backend é testado com transporte falso (`httpx.MockTransport`), executor de comandos injetado ou servidor local em `127.0.0.1`. Nenhum teste espera tempo real (relógio injetado).
- Sala limpa (ADR 0016): os textos dos pedidos (prompts) são nossos; nenhum prompt de outro projeto é copiado nem parafraseado. Exemplos de teste são fictícios ou de fixtures que já são nossas.
- Conteúdo de vaga, de currículo e de página é dado, nunca instrução (CLAUDE.md, regra do projeto).
- Gravação com `INSERT ... ON CONFLICT DO UPDATE`; nada de vaga é apagado; `evento` só recebe acréscimo.
- Documentos de quem usa são bilíngues; ADR e `duvidas.md` só em português; texto novo do painel nos catálogos `pt` e `en`.
- O `ci.yml` fica com os jobs `{lint, comuns, tela, ok}` (`tests/unidade/test_ci.py`): a prova do modelo local ganha workflow próprio (seção 12).

## 4. Como funciona hoje (fatos)

- **Não há código de IA.** `grep` por `claude`, `codex`, `llama` e `qwen` em `src/jobot`, `desktop/src` e `desktop/ui` não acha nada. A ADR 0009 ainda diz que o projeto "ainda não tem código" (`0009:9`).
- **Encaixe.** `calcular(v, b, *, sal_mensal_brl, minimo_busca_brl, regras_ligadas, pais_padrao) -> Encaixe` (`src/jobot/nucleo/encaixe.py:192-232`) soma cinco critérios, cada um `(pontos, peso, Motivo)` ou `None` (neutro): `_cargo` (`:42`), `_local` (`:76`), `_nivel` (`:103`), `_salario` (`:121`) e `_idioma` (`:136`). O cargo casa por palavra inteira normalizada, 40 pontos no título e 20 na descrição (`:38-63`), sem sinônimo. Pesos e faixas em `src/jobot/nucleo/dados/encaixe.json` (cargo 40, local 20, nível 15, salário 15, idioma 10; bom ≥ 70, médio ≥ 40). A nota é 100 × pontos ÷ soma dos pesos preenchidos (`encaixe.py:33-35, 231`).
- **Saída do encaixe.** `Encaixe(nota, nivel, motivos, oculta_motivo)` e `Motivo(chave, params)` (`src/jobot/nucleo/modelo.py:246-257`). Nada guarda habilidades.
- **Quem chama.** Só `_recalcular` (`src/jobot/banco/buscas.py:291-346`, `calcular` em `:328`), num laço vaga × busca dentro da transação de escrita de `recalcular_encaixe` (`:349-366`). Disparam o recálculo: `cli/servir.py:94`, `agenda/execucao.py:103`, `painel/rotas/configuracoes.py:416, 454`, `painel/rotas/detalhe.py:185` e `painel/rotas/primeira_execucao.py:292`. Por isso uma IA lenta não cabe dentro de `calcular()` nem da transação.
- **Tabela `encaixe`.** `(busca_id, vaga_id)` PK, `nota`, `nivel` (CHECK bom/medio/fraco), `motivos` em JSON e `oculta_motivo` (`src/jobot/banco/migracoes/0001_inicial.sql:139-148`). Última migração: `0011_candidatura.sql`.
- **Motivo na tela.** O global `_motivo` chama `t(chave, **params)`; chave desconhecida ou parâmetro faltando somem (`src/jobot/painel/globais.py:26-32, 65`). Motivo novo precisa de chave nos dois catálogos (`src/jobot/painel/i18n/pt/vagas.json:86-104`).
- **Rótulos.** Regras em `rotulos.json`; `rotular()` só é chamado por `tratar()` (`src/jobot/nucleo/tratamento/tratar.py:22-45`), que roda na coleta e no reprocessamento. Medido em 2026-11-14 (329 vagas): área 63,5%, nível 71,7%, modalidade 61,1%, contrato 64,4%, avisos 84,2%, país 87,2%, UF 94,5% (`docs/rotulos-medidos.md`).
- **Perfil.** Não existe (nem tabela, nem módulo; `navegador/perfil.py` é o perfil do navegador). A spec `2026-11-15-perguntas-do-perfil.md` propõe a tabela `perfil` de uma linha e as tabelas `experiencia` e `curso` (P1, `:276-301`).
- **Candidatura.** `nucleo/candidatura.py` só extrai o e-mail de candidatura do texto, com lista fechada de caracteres; a tabela `candidatura` guarda `abriu_em` e `perguntar` (`0011_candidatura.sql`). Não há geração de texto.
- **Configuração.** Tabela `config (chave, valor JSON)` (`0001_inicial.sql:214`) com padrões em `PADROES` (`src/jobot/banco/cadastros.py:35-50`).
- **Cofre.** `sistema/cofre.py`: keyring (serviço `jobot`) com reserva em arquivo 0600, nomes `[a-z0-9_]{1,32}`, `ler/gravar/apagar`; o painel grava por `no_cofre` numa thread com prazo `PRAZO_COFRE_S` (`src/jobot/painel/rotas/servicos.py:38-46`). Nomes em uso: `2captcha`, `gmail_conta`, `gmail_senha_de_app`.
- **Configurações.** `GRUPOS` em `src/jobot/painel/ambiente.py:97`; `SO_COM_LEITOR = (FERRAMENTAS,)` (`:109`) esconde Ferramentas sem leitor com login. Ferramentas tem só o navegador (`templates/configuracoes/_ferramenta_navegador.html`; rotas em `configuracoes.py:268-325, 830-920`, estado em `app.state.ferramentas[nome]`). Serviços tem só o 2Captcha (`servicos.html`). Texto de hoje: "Hoje é só o navegador dos sites com login." (`i18n/pt/configuracoes.json:112-130`).
- **Primeira execução.** Passos montados em `primeira_execucao.py:104-105` (busca, `sites` opcional, segundo plano); `_MAX_CARGOS` em `:78`, `_montar` em `:201`.
- **Casca.** `invoke('instalar', {navegador, progresso})` (`desktop/ui/instalador.js:153`), `ORDEM`/`PESOS` fixos (`:9-13`), `MOTIVOS` com `navegador` (`:101-109`); `instalar(app, navegador: bool, progresso)` (`desktop/src/main.rs:194-252`); `instalar_sem_desfazer` grava o `instalacao.json` no fim (`desktop/src/instalar.rs:635-777`); `baixar_navegador` lê linhas JSON `{etapa, feito, total}` e `{fim}` e cancela com `parar_arvore` (`instalar.rs:203-221, 282-320, 604-632`). A página Pronto só tem título e "Abrir" (`desktop/ui/index.html:133-136`).
- **CLI.** `jobot ferramentas` só aceita `baixar navegador` (`src/jobot/cli/ferramentas.py:40-49`).
- **Processos.** `sistema/processo.py` sobe destacado e encerra árvore em todo sistema (fase 3, T325).
- **Andamento.** A etapa `encaixe` pesa 5 de 100 (`src/jobot/nucleo/andamento.py:6`).

## 5. Arquitetura

```
nucleo/ia/                  puro, com httpx onde fala com serviço
  tarefas.py                as 4 tarefas: esquema de entrada e saída (pydantic, extra="forbid"),
                            versão do texto do pedido, regra anti-invenção de cada uma
  pedidos.py                monta as mensagens (texto nosso + dados delimitados)
  contrato.py               Pedido, Resposta, Falha (motivos fechados), Protocol Backend
  compativel_openai.py      cliente /v1/chat/completions (OpenAI, Gemini, local, Ollama, LM Studio...)
  anthropic.py              cliente /v1/messages com ferramenta forçada
  claude_code.py            argv, ambiente e leitura da saída do `claude -p` (executor injetado)
  codex.py                  argv e leitura do `codex exec` (executor injetado)
  manual.py                 texto para copiar e leitura da resposta colada
  falso.py                  backend de teste (respostas prontas, grava os pedidos)
nucleo/dados/ia.json        tarefas, modelos padrão, limites, backends liberados
nucleo/dados/ia_local.json  llama-server por alvo e modelos: URL fixa, tamanho e sha256
nucleo/encaixe.py           critério novo `_habilidades` (puro)
sistema/baixar.py           download com sha256, retomada e progresso em linhas JSON
sistema/memoria.py          memória total do computador (stdlib e ctypes)
sistema/llama.py            sobe e derruba o llama-server (porta livre, chave por subida, ocioso)
sistema/terminal.py         abre um terminal com o login da ferramenta (Claude Code, Codex)
banco/migracoes/0012_ia.sql perfil, experiencia, curso, pergunta_perfil, habilidades_vaga, preparo_candidatura
banco/perfil.py, banco/ia.py  leitura e gravação
agenda/ia.py                laço das habilidades depois da execução (conexão própria)
painel/rotas/ia.py, perfil.py  Configurações › IA, teste ao ligar, perfil, preparar candidatura
cli/ferramentas.py          baixar/remover ia-local, baixar claude-code e codex, entrar
desktop/                    grupo de IA no instalador e botões no Pronto
```

**Quem fala com quem.** O painel e a agenda montam o backend (juntam o cliente do núcleo com o executor de `sistema` e a chave do cofre) e chamam o núcleo; o painel continua sem `httpx` (como hoje com o captcha). O banco só guarda o que a IA respondeu. `test_camadas.py` ganha a regra: `jobot.nucleo.ia` só é importado por `agenda`, `painel`, `cli` e pelo próprio `nucleo.ia` (no molde do `test_captcha_so_em_navegador_e_painel`, `:102-104`).

### 5.1 Contrato

- `Pedido(tarefa, modelo, mensagens, esquema)` e `Resposta(dados: dict, backend, modelo, versao)`. `Falha(motivo)` com motivos fechados: `sem_chave`, `chave_recusada`, `sem_rede`, `programa_ausente`, `nao_logado`, `login_errado` (Claude Code com método que não é a assinatura), `modelo_ausente`, `tempo_esgotado`, `limite` (429 ou limite de uso), `recusa` (sem saída estruturada), `formato` (não passou no esquema), `liberacao` (backend ainda não liberado, D185.5 e D185.6). Cada motivo tem texto pt/en com o que fazer (ADR 0009, Teste ao ligar).
- Toda resposta passa pelo modelo pydantic da tarefa (`model_validate`). Não passou: `Falha("formato")`, uma tentativa só, sem repetir sozinho.
- O esquema enviado ao backend sai de `model_json_schema()` (objeto, `additionalProperties: false`, todos os campos obrigatórios, listas com `maxItems` e textos com `maxLength`). O mesmo esquema serve ao `response_format` `json_schema` do compatível, ao `input_schema` da ferramenta da Anthropic, ao `--json-schema` do Claude Code e ao `--output-schema` do Codex (opção conferida na T407).
- **Versão.** Cada tarefa tem `VERSAO` (número que sobe quando o texto do pedido ou o esquema mudam). O resultado guardado leva `versao`, `backend` e `modelo`; resultado de outra versão é refeito quando a vaga voltar à fila.

### 5.2 As tarefas

| Tarefa | Entrada (só o necessário) | Saída | Anti-invenção no código | Padrão Claude | Quando roda |
|---|---|---|---|---|---|
| `encaixe` | `perfil.habilidades`, cargo atual; título e descrição da vaga (até 6000 caracteres, proposta) | `pede` (≤ 30), `tem` (pares `{pede, perfil}`), `faltam` | todo `perfil` de `tem` tem de estar em `perfil.habilidades` (normalizado); `faltam` ⊂ `pede`; o resto é descartado | Haiku 5.5 | laço da agenda (5.4) |
| `candidatura` | perfil (sem telefone e e-mail, que o joBot põe depois), experiências, cursos; vaga | `idioma`, `carta`, `resumo`, `tem`, `faltam`, `perguntar` (≤ 5), `usou` (chaves de campos do perfil) | `usou` só com chaves que existem no perfil preenchido; `tem` como no encaixe | Sonnet 5.5 | botão na vaga |
| `curriculo` | texto do PDF (até 20 páginas, proposta) | campos do perfil, experiências e cursos | nada é gravado sem a pessoa revisar | Sonnet 5.5 | passo Perfil |
| `perguntas` | perfil preenchido e perguntas já respondidas | até 5 perguntas `{pergunta, por_que}` | perguntas iguais a uma já feita são descartadas | Sonnet 5.5 | passo Perfil e botão no perfil |

Offline, todas as tarefas usam o Qwen local (ADR 0009:55-57). Nunca Opus (ADR 0009:51).

### 5.3 Pedido e dados de terceiros

- A mensagem de sistema é nossa e diz o papel, a regra de ouro e que tudo dentro das marcas `<<<VAGA` … `VAGA>>>`, `<<<CURRICULO` … `CURRICULO>>>` e `<<<PERFIL` … `PERFIL>>>` é dado, nunca instrução. Marcas que aparecerem dentro do dado são trocadas antes de montar (o dado não fecha a marca).
- Nenhum backend tem ferramenta, MCP, acesso a arquivo ou rede além da própria resposta (Claude Code com `--tools ""` e `--strict-mcp-config`; Codex em `--sandbox read-only` numa pasta vazia, opções conferidas na T407; o llama-server não tem ferramentas).
- O texto gerado só é mostrado (o Jinja escapa) e copiado pela pessoa; nunca vira HTML, comando, URL clicável ou mensagem enviada.
- Log: só tarefa, backend, modelo, duração, tamanho e motivo da falha. Nunca o texto do pedido nem da resposta.

### 5.4 Laço das habilidades

`calcular()` continua puro e síncrono; a IA roda num passo à parte (D185.12):

1. Depois de cada execução de busca (`agenda/execucao.py:103`, após o `recalcular_encaixe`), e uma vez ao subir o servidor, a agenda chama `agenda/ia.processar_habilidades` se a tarefa `encaixe` estiver ligada e o perfil tiver habilidades.
2. A fila: vagas abertas, não ocultas, com encaixe `bom` ou `medio` em alguma busca, sem linha em `habilidades_vaga` ou com `chave` diferente da atual (hash do perfil.habilidades + versão da tarefa + backend + modelo), das mais novas para as mais velhas, até `max_por_rodada` (20, proposta) por rodada.
3. Cada vaga: pede ao backend, aplica a anti-invenção e grava `habilidades_vaga` (uma linha por vaga, não por busca: as habilidades não dependem da busca). Depois chama `recalcular_encaixe(vaga_id=...)`, que lê a linha e passa ao `calcular` (5.5). Falha: grava o motivo e a hora em `habilidades_vaga.falha`, não repete a mesma vaga na mesma rodada; três falhas seguidas do mesmo backend param a rodada.
4. Conexão própria (a conexão do `banco.abrir()` não troca de thread nem se divide entre tarefas asyncio; CLAUDE.md, Armadilhas). A chamada ao backend roda fora da transação; só a gravação abre a escrita.
5. O andamento da busca não muda: o laço roda depois dela e tem só a linha "IA: N vagas analisadas" no painel de execução (proposta).

### 5.5 Encaixe com habilidades

- `calcular(..., habilidades: Habilidades | None = None)`. `Habilidades(pede, tem, faltam)` em `nucleo/modelo.py`. Sem a linha (IA desligada ou ainda não rodou), o critério é `None`, neutro: a nota fica igual à de hoje.
- `_habilidades`: `pede` vazio → `None`; senão pontos = peso × `len(tem) / len(pede)`, arredondado como os outros. Peso **25** em `encaixe.json` (proposta). Como a nota divide pela soma dos pesos preenchidos, as vagas sem a linha não mudam.
- Motivos: `vagas.motivo.habilidades_tem` (`{lista}`, até 5 nomes) e `vagas.motivo.habilidades_faltam` (`{lista}`, até 5), nos dois catálogos; o detalhe mostra a lista completa e diz que veio da IA, com o backend e o modelo.
- As regras de ocultar não mudam (D185.11): a IA não esconde vaga.
- A IA nunca dá a nota: ela só lista; a conta é nossa e testável.

## 6. Backends

| Backend | Como fala | Chave | Liberado na 0.5.0 |
|---|---|---|---|
| Compatível com OpenAI | `POST <endereço>/chat/completions`, `response_format` `json_schema` (com `strict`), `httpx` | opcional, no cofre (`ia_compativel`) | sim |
| OpenAI | o mesmo cliente, endereço `https://api.openai.com/v1` fixo | cofre (`ia_openai`) | sim |
| Google Gemini | o mesmo cliente, endpoint compatível com OpenAI do Gemini (`https://generativelanguage.googleapis.com/v1beta/openai`, conferido na T404) | cofre (`ia_gemini`) | sim |
| Modelo local | o mesmo cliente, `http://127.0.0.1:<porta>/v1`, com o llama-server do joBot (seção 7) | chave aleatória por subida, só em memória | sim |
| API da Anthropic | `POST https://api.anthropic.com/v1/messages` com uma ferramenta `responder` forçada (`tool_choice`), lendo o `input` | cofre (`ia_anthropic`) | sim |
| Sessão do Claude Code | `claude -p` (ADR 0010) | nenhuma: o login é da ferramenta | não, até o dono confirmar (D185.5) |
| Sessão do Codex CLI | `codex exec` (D125) | nenhuma | não, até o dono confirmar (D185.6) |
| IA manual | o painel mostra o pedido para copiar e um campo para colar a resposta | — | sim, só nas tarefas sob pedido (`candidatura`, `curriculo`, `perguntas`) |
| Sem IA | regras de hoje; formulário vazio; só as perguntas base | — | é o padrão |

- **Ollama e LM Studio** entram pelo compatível (D108), com o endereço de cada um como sugestão no campo (`http://127.0.0.1:11434/v1`, `http://127.0.0.1:1234/v1`). O joBot não os instala.
- **Modelos.** Claude: só `claude-haiku-5-5` e `claude-sonnet-5-5`, por tarefa (ADR 0009:43-53). OpenAI, Gemini e compatível: a pessoa digita o nome do modelo; o teste ao ligar confere. Local: o Qwen baixado (o nome vem do manifesto).
- **Claude Code** (quando liberado): ADR 0010 inteira: `claude auth status` antes (só segue com o `authMethod` da assinatura; valores conferidos na T406), ambiente sem `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` e `CLAUDE_CODE_USE_*`, pasta temporária vazia, sem `--bare` e sem `CLAUDE_CODE_OAUTH_TOKEN`; `claude -p --output-format json --json-schema <esquema> --model <id> --tools "" --strict-mcp-config --no-session-persistence`, pedido pela entrada padrão; falha com saída ≠ 0 ou sem `structured_output`.
- **Codex** (quando liberado): `codex exec` numa pasta temporária vazia, sem ferramentas que escrevam, com saída por esquema; o login é conferido pelo comando de status do próprio Codex (`codex login status`, conferido na T407). O joBot nunca abre `~/.codex/auth.json`.
- **Marcas.** "funciona com o Claude Code" e "funciona com o Codex", só texto, com o aviso de não afiliação (ADR 0009:78-81, ADR 0010).
- **Atalhos** (ADR 0009:25): "Desligada" (padrão), "Tudo offline" (modelo local em todas as tarefas; se o modelo não está baixado, leva a Ferramentas), "Tudo Claude" (Claude Code se liberado e logado, senão a API da Anthropic com a chave) e "Personalizado" (a tabela por tarefa).

### 6.1 Teste ao ligar

Ao ligar uma tarefa, trocar o backend, o modelo, a chave ou o endereço, o painel grava a escolha como "testando", responde na hora com o sinal de espera e dispara o teste numa thread com prazo: 30 s nos serviços de fora e 180 s no local (a primeira carga do modelo conta) (proposta). O teste é um pedido curto da própria tarefa com um exemplo fictício fixo. Passou: ✓ e a tarefa liga. Falhou: o motivo com o que fazer, e a tarefa fica desligada (ADR 0009:34-41). O fragmento pergunta a cada 2 s (HTMX, como o "Conferir agora" das Contas). O painel nunca espera o teste.

## 7. Modelo local

- **O que baixa** (D185.7): o `llama-server` do build **b12359** do llama.cpp (os binários da tag `v1.0.0`, com atestação SLSA; a ADR 0009:61 citava b12366, sem sha256 registrado) e um GGUF da Unsloth: `Qwen3.5-2B-Q4_K_M.gguf` (1 280 835 840 B) ou `Qwen3.5-4B-Q4_K_M.gguf` (2 740 937 888 B). Arquivos do llama-server por alvo: `llama-b12359-bin-ubuntu-x64.tar.gz`, `-win-cpu-x64.zip`, `-macos-arm64.tar.gz`, `-macos-x64.tar.gz` (só CPU).
- **Manifesto** `src/jobot/nucleo/dados/ia_local.json`: por arquivo, a URL com versão fixa (GitHub `releases/download/b12359/...`; Hugging Face `resolve/<commit>/...`, nunca `main`), o tamanho e o sha256 (o `digest` da API do GitHub e o oid LFS do Hugging Face, conferidos pela T408 e, para o llama-server, também com `gh attestation verify --owner ggml-org`). Um teste trava que toda URL tem versão fixa e todo arquivo tem sha256 de 64 dígitos.
- **De onde** (D185.7): da fonte oficial, pelo joBot, a pedido da pessoa (instalador com o item marcado, ou Ferramentas › Baixar). Não vai dentro do instalador nem na release: o 4B passa do limite de 2 GiB por anexo de release do GitHub e o instalador passaria de 1,5 GB. A licença permitiria redistribuir (MIT e Apache-2.0); não é preciso. É a mesma exceção da D183.24 à D174.1, com sha256 conferido (o navegador não tem).
- **Onde fica:** `<dados>/ferramentas/llama/b12359/` e `<dados>/ferramentas/modelos/<arquivo>.gguf` (proposta). A pasta de dados não some ao desinstalar a casca (desenho da fase 3, 7.2); Ferramentas › Remover apaga o modelo e o llama-server.
- **Download** (`sistema/baixar.py`): `httpx` em fluxo, user agent do joBot, grava em `<arquivo>.parcial`, retoma com `Range` se o `.parcial` existe (servidor que responde 200 recomeça), confere tamanho e sha256 no fim e só então `os.replace`. Diferença de sha256: apaga o `.parcial` e falha com `arquivo` ("o arquivo baixado não é o esperado"). Progresso em linhas JSON `{"etapa":"ia_local","feito":N,"total":T}` e `{"fim":...}` (o mesmo protocolo do navegador, para a casca e o painel). Extração do `.tar.gz` com `tarfile` e `filter="data"`; do `.zip` com `zipfile`, recusando caminho para fora (o binário do Windows não precisa do bit de execução); no Linux e no Mac, `chmod +x` no `llama-server`.
- **Qual modelo** (D139.11, D185.19): `sistema/memoria.py` lê a memória total (`os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")` no Linux e no Mac; `GlobalMemoryStatusEx` por `ctypes` no Windows). Menos de 12 GB: 2B; 12 GB ou mais: 4B. Menos de 8 GB: baixa o 2B e avisa que pode ficar lento. A pessoa troca em Ferramentas › Trocar modelo, com o tamanho à vista.
- **Rodar** (`sistema/llama.py`): sobe sob demanda, na primeira chamada de uma tarefa local; `llama-server -m <gguf> --host 127.0.0.1 --port <livre> --api-key <aleatória> -c 8192 -np 1 --no-webui` (opções conferidas com `--help` na T408; a porta padrão do README não importa porque o joBot sempre passa a dele), pelo `processo.py` (sessão própria, encerra a árvore). Espera `GET /health` até 120 s. Uma instância só por joBot (variável do processo do servidor). Cai depois de 10 min sem pedido (proposta) e quando o servidor do joBot para. O pedido desliga o modo de pensar do Qwen3.5 (`chat_template_kwargs: {"enable_thinking": false}`) e usa a amostragem recomendada sem pensamento (temperatura 0,7, top_p 0,8, top_k 20; conferida na T408).
- **Velocidade.** Medições de terceiros: 4B Q4_K_M em CPU compartilhada gerou 8,6 tokens/s. Estimativa: perto de 1 min por vaga no 4B e metade no 2B, em notebook sem placa de vídeo. Por isso o limite por rodada (5.4) e a medida de verdade (T419 e o dono, seção 15).

## 8. Perfil, currículo e questionário

- **Tabelas** (migração `0012_ia.sql`, D185.13): `perfil` de uma linha (`id = 1` com CHECK): `nome`, `email`, `telefone`, `cidade_moradia`, `cargo_atual`, `anos_de_experiencia`, `formacao_nivel`, `resumo`, `habilidades` (JSON, lista), `idiomas_falados` (JSON, `[{idioma, nivel}]`), `links` (JSON), `curriculo_texto`, `atualizado_em`. `experiencia` (`empresa`, `cargo`, `inicio`, `fim`, `descricao`, `ordem`), `curso` (`nome`, `instituicao`, `nivel`, `fim`, `ordem`), `pergunta_perfil` (`pergunta`, `por_que`, `origem` CHECK `base`/`ia`, `resposta`, `criada_em`, `respondida_em`). Sem CPF e sem data de nascimento na 0.5.0 (minimização; voltam se uma tarefa precisar, ADR 0014). Tirar uma experiência ou um curso apaga a linha: é dado da pessoa, não vaga (a regra "nada é apagado" é das vagas e do `evento`).
- **Currículo** (ADR 0011): upload `multipart` até 5 MB; `pypdf` lê até 20 páginas (proposta) numa thread com prazo de 30 s; o PDF não é guardado, só o texto (`perfil.curriculo_texto`). Com a tarefa `curriculo` ligada, a IA extrai e a tela mostra o formulário preenchido para a pessoa revisar; nada é gravado antes do "Salvar". Sem IA (ou com falha), o formulário vem vazio e a pessoa preenche. PDF sem texto (só imagem): avisa que o joBot não lê imagem (OCR fica de fora).
- **Questionário.** Perguntas base: as do bloco A do mapa (A1 a A9: cidade, cargo atual, anos de experiência, experiências, formação, cursos, habilidades, idiomas falados) mais nome, e-mail, telefone e links (para a candidatura). As dos blocos B a D continuam no passo de busca de hoje. Com a tarefa `perguntas` ligada, a IA sugere até 5 perguntas de lacuna; a pessoa responde ou ignora; cada resposta fica em `pergunta_perfil` e entra no pedido da candidatura como dado. "Aprovar todas" vale para as sugestões da extração do currículo.
- **Tela.** Configurações ganha a aba Perfil (proposta: dentro de Configurações, como as outras abas, com as mesmas seções do assistente), para ver e editar depois.

## 9. Preparar candidatura

- Botão "Preparar candidatura" no detalhe da vaga, ao lado dos botões de hoje (`painel/detalhe_vaga.py:84-111`), só com a tarefa `candidatura` ligada; sem ela, o botão leva a Configurações › IA. Sem perfil preenchido, explica o que falta.
- `POST /vagas/{id}/candidatura/preparar` (CSRF) dispara a tarefa numa thread e devolve o fragmento de espera; o fragmento pergunta a cada 2 s. O resultado fica em `preparo_candidatura` (uma linha por vaga, `ON CONFLICT DO UPDATE`: o último preparo vale): `idioma`, `carta`, `resumo`, `tem`, `faltam`, `perguntar`, `usou`, `backend`, `modelo`, `versao`, `feito_em`.
- A tela mostra a carta e o resumo em caixas de texto editáveis com "Copiar", a lista "Você tem" e "Falta", "Dados que a IA usou" (os nomes dos campos do perfil de `usou`) e o aviso fixo "Confira antes de usar: a IA pode errar." As perguntas de `perguntar` viram `pergunta_perfil` (origem `ia`) e aparecem no perfil.
- O texto sai no idioma da vaga (`VagaTratada.idioma`, que já existe; sem ele, no idioma do painel).
- O joBot nunca envia nada: o botão de e-mail de hoje (`mailto:` só com o assunto, ADR 0014, nota de 2026-11-16) não ganha o corpo; a pessoa copia.
- Na IA manual: o fragmento mostra o pedido para copiar e o campo para colar; a resposta colada passa pelo mesmo esquema.

## 10. Instalador, Ferramentas, Contas, Serviços e Configurações › IA

### 10.1 Instalador (casca)

- Grupo novo "Inteligência artificial (opcional)" no passo Ferramentas, depois do navegador, com Claude Code, Codex e Modelo local, **desmarcados** (D139.3). Só aparecem os itens liberados (D138.6, D185.5, D185.6): na 0.5.0 sem resposta do dono, só o Modelo local. A frase de cada um diz "baixa X se você marcar", nunca "vem com" (D139.2): Modelo local, "Para usar IA sem internet e sem pagar. Baixa da internet de 1,3 a 2,7 GB, conforme a memória do computador; dá para baixar depois em Configurações › Ferramentas."
- `invoke('instalar', {navegador, ia: {claude_code, codex, modelo_local}, progresso})`; `estado_instalador` devolve também quais itens de IA estão liberados e os tamanhos dos dois modelos. Na tela Ferramentas o venv ainda não existe, então a casca não pergunta ao `jobot`: o build escreve a lista liberada e os tamanhos no `manifesto.json` dos recursos, a partir do `ia.json` e do `ia_local.json` (proposta).
- **Ordem** (D185.17): os itens de IA rodam **depois** de gravado o `instalacao.json` (o joBot já está instalado), cada um pelo `jobot ferramentas baixar <item>` do venv, lendo as mesmas linhas JSON; o `ler_linha` passa a aceitar as etapas `ia_local`, `claude_code` e `codex`. Etapas novas: "Baixando o modelo local" (barra por bytes, o total vem do manifesto), "Baixando o Claude Code", "Baixando o Codex" (fatia que se completa no fim). Pesos proporcionais (proposta).
- **Falha de item de IA não é falha da instalação**: a etapa termina, as outras seguem, e a página Pronto lista o que não baixou com "Baixe depois em Configurações › Ferramentas". Fechar a janela no meio de um item de IA pede confirmação, encerra a árvore e apaga o `.parcial`; o joBot fica instalado.
- **Pronto** ganha "Entrar no Claude Code" e "Entrar no Codex" (D139.14, confirmado pela sessão na D185.17), só para os itens que baixaram: cada um roda `jobot ferramentas entrar <item>` (10.3).
- Textos novos em `desktop/ui/i18n/{pt,en}.json` (o teste de chaves iguais já existe).

### 10.2 Ferramentas

- Sempre visível (D185.20): `SO_COM_LEITOR` sai; o cartão do navegador só aparece com leitor com login, como hoje.
- Cartões: Modelo local (estado, modelo baixado e tamanho; "Baixar", "Trocar modelo" (2B ↔ 4B) e "Remover"), Claude Code e Codex (só com o backend liberado: estado "achado no PATH" ou "não instalado", "Baixar"; nunca "Remover", D138.7). Mesmo molde do `_ferramenta_navegador.html` (fragmento HTMX, estado em `app.state.ferramentas[nome]`, polling de 5 s).
- Texto `configuracoes.ferramentas.explicacao` troca o "Hoje é só o navegador dos sites com login." por "Programas que o joBot baixa à parte, só quando você pede." nos dois catálogos.
- **Claude Code**: baixa pelo instalador oficial (endereço e jeito de rodar conferidos na T416 em `https://code.claude.com/docs/en/setup`; hoje, script por HTTPS que confere o binário que baixa). **Codex**: baixa o binário da release oficial `openai/codex` no GitHub, versão e sha256 fixos em `ia_local.json`, para `<dados>/ferramentas/codex/` (proposta). Os dois rodam como a pessoa, nunca como admin. O botão some quando o programa é achado (no `PATH` ou na pasta do joBot).

### 10.3 Contas

- Cartões "Claude Code" e "Codex" na aba Contas (D139.8), só com o backend liberado. Estado vindo da própria ferramenta: `claude auth status` (logado, com o método; não logado; não instalado) e o status do Codex. A conferência roda numa thread com prazo de 15 s e não guarda nada no banco (o estado é da ferramenta).
- Botão "Entrar" (não logado): `jobot ferramentas entrar <item>` abre um terminal com o login da ferramenta (`claude` e o `/login`, ou `codex login`; comandos conferidos nas T406 e T407) por `sistema/terminal.py`: Linux, o primeiro achado entre `x-terminal-emulator`, `gnome-terminal`, `ptyxis`, `kgx`, `konsole`, `xfce4-terminal` e `xterm`; Windows, `cmd /c start`; Mac, `open -a Terminal` com um script temporário. Sem terminal achado: mostra o comando para copiar. O joBot não lê a saída do terminal.

### 10.4 Serviços e Configurações › IA

- Serviços ganha cartões de chave: Anthropic, OpenAI, Google Gemini e "Compatível com OpenAI" (endereço e chave opcional), no molde do cartão do 2Captcha: grava no cofre (`no_cofre`), nunca devolve a chave ao HTML (máscara), "Apagar", aviso quando o cofre cai no arquivo 0600.
- Aba nova **IA** em Configurações (GRUPOS, depois de Funções; proposta): os quatro atalhos no topo; uma linha por tarefa com liga/desliga, backend (só os liberados e configurados) e modelo; o estado do teste ao ligar; e a frase de privacidade da tarefa ("o texto da vaga e suas habilidades vão para <serviço>" ou "ficam no seu computador").
- Configuração gravada na `config`, chave `ia_tarefas` (JSON `{tarefa: {ligada, backend, modelo}}`), padrão tudo desligado em `PADROES` (`cadastros.py:35`).

### 10.5 Primeira execução

Dois passos novos, opcionais, antes dos de hoje (ADR 0011, passos 0 a 2; D185.15): **IA** (detecta o Claude Code liberado e logado e o oferece; senão mostra os atalhos e "Pular") e **Perfil** (currículo e perguntas do bloco A, com as perguntas de lacuna se a tarefa estiver ligada; "Pular"). O passo de busca de hoje continua, e os campos que o perfil já respondeu (cargo atual, cidade) chegam preenchidos.

## 11. Segurança e privacidade

- IA desligada por padrão; nada sai do computador sem a pessoa ligar uma tarefa num backend de fora. Cada tarefa diz, na aba IA, o que vai e para onde. O README e a tela Privacidade listam os serviços novos (Anthropic, OpenAI, Google Gemini, o endereço do compatível) e a regra (ADR 0014:24; `test_privacidade_cita_todos_os_pedidos` ganha os termos).
- Dados que saem por tarefa (minimização): `encaixe` não leva nome, e-mail, telefone nem cidade; `candidatura` leva o perfil sem e-mail e telefone; `curriculo` leva o texto do PDF; `perguntas` leva o perfil sem contato.
- Chaves no cofre (ADR 0009:23, ADR 0014:13); nunca no log nem em mensagem de erro (só o tipo da exceção).
- llama-server em `127.0.0.1`, porta livre e `--api-key` aleatória por subida, guardada só na memória do servidor do joBot; nunca em `0.0.0.0`.
- Downloads de ferramenta: só URLs fixas do manifesto, HTTPS, sha256 conferido antes de usar (exceto o script oficial do Claude Code, conferido pelo próprio script; limite registrado na D185.18); arquivo que não confere é apagado.
- Claude Code e Codex: os cuidados da ADR 0010 inteiros; nunca abrir `~/.claude`, o Keychain nem `~/.codex/auth.json`.
- Injeção pelo texto da vaga: sem ferramentas, saída só por esquema, texto mostrado escapado, a pessoa revisa tudo. Risco residual: a carta pode sair torta (seção 13).

## 12. Testes e provas

- **Unidade (sem rede):** esquemas e anti-invenção de cada tarefa (com respostas que inventam habilidade, campo `usou` inexistente, `faltam` fora de `pede`); montagem das mensagens (marcas trocadas dentro do dado); cada cliente HTTP com `httpx.MockTransport` (sucesso, 401, 429, 5xx, prazo, JSON fora do esquema, recusa); Claude Code e Codex com executor injetado (argv e ambiente exatos, variáveis tiradas, pasta vazia, `authMethod` errado recusado, saída sem `structured_output`); `baixar.py` com servidor HTTP local em `127.0.0.1` (retomada por `Range`, 200 no lugar de 206, sha256 errado apaga, progresso); `memoria.py` com `sysconf` e `ctypes` falsos; `llama.py` com um "llama-server" falso (script Python que serve `/health` e `/v1/chat/completions` em `127.0.0.1`), subida, chave, queda por ociosidade com relógio injetado; `_habilidades` puro; manifesto com versão fixa e sha256; `test_camadas.py` com a regra nova.
- **Integração:** migração 0012 (esquema, CHECKs, `ON CONFLICT`); laço das habilidades com `BackendFalso` (fila, limite, versão, falhas seguidas, recálculo e motivos); rotas de IA, perfil e candidatura (CSRF, teste ao ligar com backend falso, polling, chave nunca no HTML); Ferramentas e Contas com executor falso; i18n pt/en.
- **Tela (Playwright, CI):** aba IA, teste ao ligar, preparar candidatura, passo Perfil, instalador com o grupo de IA (com `__TAURI__` falso), página Pronto com "Entrar".
- **Rust:** `ler_linha` com as etapas novas, ordem (IA depois do `instalacao.json`), falha de IA que não desfaz, cancelamento no meio do download.
- **Modelo de verdade** (workflow novo `.github/workflows/ia.yml`, só `workflow_dispatch`, `contents: read`, sem segredo; D122: só exemplos públicos): baixa o llama-server b12359 e o Qwen3.5 2B pelo `jobot ferramentas baixar ia-local --modelo 2b` (prova o sha256 e a extração), roda as quatro tarefas com uma vaga de fixture e um perfil fictício e confere que a saída passa no esquema e na anti-invenção; mede tokens/s (`scripts/medir_modelo.py`) e escreve no resumo do job. Linux sempre; Windows e Mac na mesma matriz. `tests/unidade/test_ia_ci.py` trava gatilho, permissões e ausência de segredo.
- **Dono (portão):** instalar a 0.5.0 com o Modelo local marcado, ligar "Tudo offline", rodar uma busca e ver as habilidades, preparar uma candidatura, mandar o PDF do currículo; medir o tempo por vaga na máquina dele.

## 13. Riscos

1. **Termos da Anthropic para o Claude Code** (D185.5): o texto legal do Claude Code diz que o login da assinatura é para o "uso comum" do Claude Code e que produtos devem usar chave de API. O joBot chama o Claude Code da própria pessoa, na máquina dela, para ela mesma (ADR 0010), mas a leitura é do dono. Até ele confirmar, o backend vem construído e escondido; "Tudo Claude" usa a chave da API.
2. **Termos da OpenAI para o Codex com o login do ChatGPT** (D185.6): a documentação recomenda chave de API para automação e tem guia para manter o login do ChatGPT em scripts confiáveis; os Termos de Uso não foram lidos (403). Mesma saída: construído e escondido até o dono confirmar.
3. **Velocidade do Qwen em CPU** (~1 min por vaga no 4B): limite por rodada, só vagas boas e médias, 2B abaixo de 12 GB; a medida da T419 e a do dono decidem se o limite muda.
4. **Qualidade do 2B em português e no esquema**: o `json_schema` vira gramática no llama-server e garante a forma, não o conteúdo; a anti-invenção corta o que não está no perfil; o `ia.yml` prova com exemplos públicos. Se o 2B errar demais, o padrão sobe para o 4B onde couber (volta ao dono).
5. **Invenção na carta**: o código só confere `usou` e `tem`; a carta é texto livre. Mitigação: `usou` à vista, aviso fixo, nada enviado sem a pessoa copiar.
6. **Injeção pelo texto da vaga**: sem ferramentas e saída por esquema; o pior caso é uma carta torta que a pessoa lê antes de usar.
7. **Download grande** (até 2,7 GB) e Hugging Face ou GitHub fora do ar: retomada por `Range`, URL com revisão fixa, sha256; falha não desfaz o joBot.
8. **Memória**: llama-server (2 a 5 GB) + Chromium + painel numa máquina de 8 GB. Uma instância só, cai depois de 10 min parada, 2B abaixo de 12 GB.
9. **Binário do llama.cpp no Linux** feito para uma glibc nova pode não abrir em distro velha: o teste ao ligar mostra `programa_ausente` com o que fazer (usar o Ollama pelo compatível).
10. **PDF malicioso ou pesado**: 5 MB, 20 páginas, thread com prazo; o `pypdf` não executa nada do PDF.
11. **Abrir terminal no Linux**: sem terminal conhecido, mostra o comando.
12. **Laya**: o modelo público `convaiinnovations/Laya` (Apache-2.0, versão multilíngue sobre mmBERT-base, 322M) é um modelo de decisão (perguntas de escolha, nota e "verdadeiro ou falso"), não de embedding de competências; o desenho do treino (T420) usa as perguntas "verdadeiro ou falso" para "a vaga pede X e o perfil tem Y". Rodar na máquina exige um runtime novo (ONNX), decidido quando o Laya ganhar no gabarito.

## 14. Documentos que mudam

- ADR nova **0026. IA da fase 4: tarefas, backends e modelo local** (resume a D185 com as marcas "para confirmar").
- Notas, cada uma com "Atualizada" e "Ver também": 0007 (o e5-small sai da fase 4, D185.9), 0009 (b12359; sem áudio no pacote; baixado da fonte oficial e não perguntado pelo instalador; OpenAI e Gemini pelo cliente compatível; Codex e Claude Code liberados só com o dono; "ainda não tem código" sai), 0010 (o texto legal novo e a liberação, D185.5), 0011 (passos IA e Perfil; sem CPF na 0.5.0), 0014 (RunPod também no treino do Laya antes da fase 4; serviços novos), 0015 (o Laya público é modelo de decisão; preparo na T420), 0017 (status da fase 4), 0023 (Ferramentas sempre visível; Modelo local removível).
- `duvidas.md`: D185; "Ver também" na D1, D97, D122, D125, D139, D141 e D174. Os textos com a numeração velha (D108, D109, D122, D125) já têm a nota da ADR 0017; não mudam.
- `README.md`/`README.en.md`: IA (tarefas, atalhos, backends, o modelo local baixado da fonte oficial, sem Whisper na tabela do pacote offline), privacidade com os serviços novos, roteiro com a fase 4, a frase velha "O instalador ainda vai chegar (fase 3)" (`README.md:274`).
- `CHANGELOG` 0.5.0 (pt/en); `wiki/` (Roteiro, Tecnologias, Como funciona, Perguntas frequentes, pt e en); `CONTRIBUTING` (como testar a IA sem rede; como rodar o `ia.yml`).
- `registros/padroes.md`: as lições que aparecerem.

## 15. Espera o dono

Nada aqui trava as tarefas; o que depende do dono vem construído e desligado.

1. Confirmar a D185 (ou trocar itens).
2. Liberar a sessão do Claude Code (D185.5) depois de ler o texto legal do Claude Code; liberar a sessão do Codex com o login do ChatGPT (D185.6) depois de ler os Termos da OpenAI. Liberar é trocar `false` por `true` em `ia.json` (um teste trava os dois em `false` até lá, com a referência à D185).
3. **Treino do Laya** (D141, D185.8): custa. Fica preparado na T420 (script de treino para o RunPod, montagem do conjunto com vagas sem e-mail, telefone e nome e exemplos fictícios, preço estimado). Precisa do dono: autorizar o gasto, pôr a chave do RunPod no `.env` (ADR 0014) e, antes, a conferência dos termos de cada fonte (ADR 0015, ponto em aberto).
4. Medir a velocidade na máquina dele (`uv run python scripts/medir_modelo.py`) e dizer se o 9B entra (D139.11).
5. Rodar a medição de rótulos com o gabarito dele quando o Laya ou o e5-small voltarem (o gabarito fica fora do repositório).
6. Portão da 0.5.0 (T423).

## 16. Decisões (D185)

Todas são escolhas da sessão de 2026-11-18, para o dono confirmar; o texto completo, o motivo e o desfazer de cada uma estão na D185 do `duvidas.md`. Resumo: 1 escopo da 0.5.0; 2 tarefas desligadas por padrão; 3 contrato com pydantic; 4 backends (OpenAI e Gemini pelo cliente compatível, sem SDK); 5 Claude Code construído e escondido até o dono; 6 Codex idem; 7 modelo local b12359 + Qwen3.5 Unsloth, baixados da fonte oficial com sha256; 8 Laya preparado, sem treino; 9 e5-small fora; 10 sem Whisper; 11 critério `habilidades` peso 25, IA não dá nota nem esconde vaga; 12 laço à parte, 20 por rodada; 13 perfil (P1 (a), sem CPF, P2 a P6 fora); 14 currículo por pypdf, PDF não guardado; 15 dois passos novos na primeira execução; 16 preparar candidatura sem envio; 17 instalador: IA depois do `instalacao.json`, falha não desfaz, botões Entrar, sem lembrar a escolha; 18 onde ficam e de onde vêm as ferramentas; 19 modelo pela memória; 20 Ferramentas sempre visível, aba IA, chaves em Serviços; 21 prazos do teste ao ligar; 22 segurança dos pedidos; 23 nome do modelo digitado fora do Claude; 24 0.5.0 só depois da 0.4.0; 25 documentos; 26 status na ADR 0017.
