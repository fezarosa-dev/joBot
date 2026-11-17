# Fase 4: IA local e opções de IA (desenho)

Data: 2026-11-17 (revisto no mesmo dia depois da crítica). Decisões de origem: ADR 0002, 0007, 0009, 0010, 0011, 0014, 0015, 0017, 0023; D1 (Claude Code), D108 (Ollama pelo compatível com OpenAI), D109 (dica de variações), D122 (modelo leve), D125 (Codex), D138 e D139 (instalador e Contas), D141 (Laya antes da fase 4), D174 e D183.24 (instalador completo; navegador baixado à parte). Escolhas desta sessão: **D185** (para o dono confirmar). Versões alvo: **0.5.0** (a fatia de ponta a ponta) e **0.6.0** (o resto da fase 4) (D185.1).

Fatos sobre o código citam o símbolo e o arquivo, conferidos na `dev` em `f23f0ef` (2026-11-17, a 0.4.0 já na `main` pelo PR #16; a tag `v0.4.0` ainda não existe). Quando a linha andar, procure o símbolo. Valores marcados "(proposta)" foram escolhidos pela sessão e valem para construir; o dono pode trocar. **Nenhum lote da fase 4 entra na `dev` antes da tag `v0.4.0`** (T342: faltam o ensaio do `release.yml` e a tag), para nada da fase 4 sair na 0.4.0 (D185.24).

## 1. Intenção

Quem usa liga a IA se quiser, escolhe onde ela roda (no próprio computador, sem pagar e sem internet depois de baixar, ou num serviço que a pessoa já tem) e ganha três coisas: o encaixe passa a ver as habilidades (o que a vaga pede, o que a pessoa tem e o que falta), a candidatura sai preparada (carta, resumo do currículo, o que tem e o que falta, no idioma da vaga) e o perfil se monta pelo currículo em PDF e por perguntas. A regra de ouro manda em tudo: a IA só usa o que a pessoa disse, nunca inventa, mostra o que usou, e o que faltar vira pergunta (ADR 0009, Regra de ouro).

**Duas versões** (D185.1). A **0.5.0** é uma fatia de ponta a ponta, pequena o bastante para medir antes de crescer: contrato, modelo local, clientes de serviço por chave, perfil mínimo (as habilidades), encaixe por habilidade, aba IA, Ferramentas › Modelo local e o item do instalador. A **0.6.0** traz currículo em PDF, questionário, perguntas de lacuna, IA manual, "Preparar candidatura" e os passos novos da primeira execução, já com os números medidos na 0.5.0. As sessões do Claude Code e do Codex não entram em nenhuma das duas sem a resposta do dono (seção 6.2).

## 2. Objetivos, não objetivos, anti-objetivos

**Objetivos (0.5.0)**

- Um contrato comum de IA no núcleo: cada tarefa tem pedido e resposta com esquema fixo; todo backend devolve a mesma saída (ADR 0009, Consequências).
- A tarefa `encaixe`, desligada por padrão, com backend e modelo próprios. Ela só **extrai** o que a vaga pede; o casamento com o perfil é feito no código, puro (D185.11).
- Backends: compatível com OpenAI (OpenAI, Gemini, o modelo local, Ollama, LM Studio, serviços como OpenRouter), API da Anthropic e "sem IA" (as regras de hoje) (D185.4).
- Modelo local: `llama-server` do llama.cpp e um Qwen3.5 2B ou 4B, baixados da fonte oficial com sha256 fixo, escolhidos pela memória e trocáveis (D139.11, D185.7, D185.19).
- Perfil mínimo: as habilidades, editáveis em Configurações › Perfil, com "Apagar perfil".
- Configurações › IA, chaves novas em Serviços, Ferramentas › Modelo local sempre visível, Modelo local no grupo de IA do instalador (D139.3, D185.17, D185.20).
- Medir a velocidade e a qualidade do Qwen no CI antes das telas (ponto em aberto da ADR 0009, Pontos em aberto).

**Objetivos (0.6.0)**

- Tarefas `curriculo`, `perguntas` e `candidatura`, desligadas por padrão; IA manual (copiar e colar) nas três.
- Perfil completo (experiências, cursos, idiomas, contato), currículo em PDF lido num processo filho, questionário (bloco A do mapa) e perguntas de lacuna.
- "Preparar candidatura" no detalhe da vaga, sem envio (D185.16).
- Passos IA e Perfil na primeira execução (ADR 0011; D185.15).

**Não objetivos**

- Sessões do Claude Code e do Codex: esperam o dono (D185.5, D185.6, D185.18; seção 6.2).
- Treinar o Laya: custa dinheiro e a primeira pergunta ao dono é se autoriza ou adia (D141, D185.8).
- Rótulos por IA ou pelo multilingual-e5-small (ADR 0007): voltam junto do Laya (D185.9).
- Áudio e Whisper (fase 6, D139.11), e-mail e respostas de recrutadores (fase 6), extensão do navegador (fase 5), LoRA do Qwen e classificador pessoal (fase 7).
- O Qwen 9B: espera a medida de velocidade (D139.11).
- Campos de busca novos e regras de ocultar novas do mapa do perfil (P2, P3, P5, P6 da spec `2026-11-15-perguntas-do-perfil.md`); viagem e horário como rótulo (P4); projetos no perfil (D185.13).
- Lembrar a última escolha do instalador (a D139.3 diz "pode"; D185.17).
- Sinônimos de habilidade por IA: só se a medida mostrar que a igualdade normalizada perde demais (D185.11).

**Anti-objetivos**

- IA ligada sem a pessoa ligar, ou dado saindo do computador sem a pessoa escolher um serviço de fora.
- IA que escreve nota, esconde vaga, envia candidatura ou age sozinha: ela só lista e sugere texto que a pessoa revisa.
- Ollama ou PyTorch dentro do pacote (ADR 0009; ADR 0003).
- SDK de provedor (anthropic, openai, google-genai): o `httpx` que já existe basta.
- Ler, copiar ou guardar a credencial do Claude Code ou do Codex (ADR 0010).
- Contornar limite de uso ou termos de serviço de qualquer provedor.
- Cobrança que a pessoa não vê: todo serviço pago aparece como "cobrado por uso" e o laço tem teto por dia (seção 5.6).

## 3. Restrições

- Camadas (`tests/unidade/test_camadas.py`): o `nucleo` não importa `fastapi`, `starlette`, `jinja2`, `painel`, `agenda`, `banco`, `sistema`, `cli`, `playwright` nem `navegador`; o painel não importa `httpx`; a `agenda` importa só `nucleo` e `banco` (CLAUDE.md, wiki Arquitetura). O núcleo pode usar `httpx` (`nucleo/http.py`, `nucleo/captcha.py`).
- O painel escuta só em `127.0.0.1` e não carrega recurso externo; todo POST com CSRF.
- Dependências fixadas com `==` e sem dependência nova sem decisão (ADR 0021). Entram: `pydantic==2.14.3` como dependência direta na 0.5.0 (já está no `uv.lock` pelo FastAPI; nenhum pacote novo) e `pypdf` na 0.6.0 (decidida na ADR 0011; BSD-3; `==` fixado na tarefa) (D185.3, D185.14).
- Testes sem rede (`tests/conftest.py`): transporte falso (`httpx.MockTransport`), lançador e executor injetados, servidor em thread em `127.0.0.1`. Nenhum teste espera tempo real. O `llama-server` de verdade só roda no workflow da IA (seção 12).
- Sala limpa (ADR 0016): os textos dos pedidos são nossos; nenhum prompt de outro projeto é copiado nem parafraseado. Exemplos de teste são fictícios, com dados reservados (`example.com`, telefones de exemplo), e nunca o gabarito.
- Conteúdo de vaga, de currículo e de página é dado, nunca instrução.
- Gravação com `INSERT ... ON CONFLICT DO UPDATE`; nada de vaga é apagado; `evento` só recebe acréscimo. Migração que entrou na `dev` não muda: mudança vira migração nova (padrões «Migração nova»).
- Documentos de quem usa são bilíngues; ADR e `duvidas.md` só em português; texto novo do painel nos catálogos `pt` e `en`.
- O `ci.yml` fica com os jobs `{lint, comuns, tela, ok}` (`tests/unidade/test_ci.py`): a prova do modelo de verdade é um workflow reutilizável chamado pelo `casca.yml` (seção 12).

## 4. Como funciona hoje (fatos)

- **Não há código de IA.** `grep` por `claude`, `codex`, `llama` e `qwen` em `src/jobot`, `desktop/src` e `desktop/ui` não acha nada. A ADR 0009 ainda diz que o projeto "ainda não tem código".
- **Encaixe.** `calcular(v, b, *, sal_mensal_brl, minimo_busca_brl, regras_ligadas, pais_padrao) -> Encaixe` (`nucleo/encaixe.py`) soma cinco critérios, cada um `_Parte` ou `None` (neutro): `_cargo`, `_local`, `_nivel`, `_salario` e `_idioma`. O cargo casa por palavra inteira normalizada (40 pontos no título, 20 na descrição), sem sinônimo. Pesos e faixas em `nucleo/dados/encaixe.json` (cargo 40, local 20, nível 15, salário 15, idioma 10; bom ≥ 70, médio ≥ 40). A nota é 100 × pontos ÷ soma dos pesos preenchidos.
- **Saída do encaixe.** `Encaixe(nota, nivel, motivos, oculta_motivo)` e `Motivo(chave, params)` (`nucleo/modelo.py`). Nada guarda habilidades.
- **Quem chama.** Só `_recalcular` (`banco/buscas.py`), num laço vaga × busca dentro da transação de escrita de `recalcular_encaixe`. Disparam o recálculo: `cli/servir.py`, `agenda/execucao.py`, `painel/rotas/configuracoes.py` (duas rotas), `painel/rotas/detalhe.py` e `painel/rotas/primeira_execucao.py`. Por isso uma IA lenta não cabe dentro de `calcular()` nem da transação.
- **Tabela `encaixe`.** `(busca_id, vaga_id)` PK, `nota`, `nivel` (CHECK bom/medio/fraco), `motivos` em JSON e `oculta_motivo` (`0001_inicial.sql`). Última migração: `0011_candidatura.sql`.
- **Motivo na tela.** O global `_motivo` (`painel/globais.py`) chama `t(chave, **params)`; chave desconhecida ou parâmetro faltando somem. Motivo novo precisa de chave nos dois catálogos (`painel/i18n/{pt,en}/vagas.json`).
- **Rótulos.** `rotular()` só é chamado por `tratar()` (`nucleo/tratamento/tratar.py`). Medido em 2026-11-14 (329 vagas): área 63,5%, nível 71,7%, modalidade 61,1%, contrato 64,4%, avisos 84,2%, país 87,2%, UF 94,5% (`docs/rotulos-medidos.md`).
- **Perfil.** Não existe (`navegador/perfil.py` é o perfil do navegador). A spec `2026-11-15-perguntas-do-perfil.md` propõe a tabela `perfil` de uma linha e as tabelas `experiencia` e `curso` (P1).
- **Candidatura.** `nucleo/candidatura.py` só extrai o e-mail de candidatura do texto; a tabela `candidatura` guarda `abriu_em` e `perguntar` (`0011_candidatura.sql`).
- **Configuração.** Tabela `config (chave, valor JSON)` com padrões em `PADROES` (`banco/cadastros.py`); `test_padroes_de_config` (`tests/integracao/test_cadastros.py`) compara o conjunto exato de chaves.
- **Pasta de dados.** `preparar_pasta` (`sistema/pastas.py`), chamada a cada subida do servidor (`cli/servir.py`), fecha em 0700/0600 tudo o que acha, menos o conteúdo de `PASTA_NAVEGADOR` (`navegador`) e `PASTA_DA_CASCA` (`app`). Um executável guardado em outra subpasta perde o `+x` na subida seguinte (o defeito da D183.16).
- **Cofre.** `sistema/cofre.py`: keyring (serviço `jobot`) com reserva em arquivo 0600, nomes `[a-z0-9_]{1,32}`; o painel grava por `no_cofre` (`painel/rotas/servicos.py`) numa thread com prazo `PRAZO_COFRE_S`. Nomes em uso: `2captcha`, `gmail_conta`, `gmail_senha_de_app`.
- **Configurações.** `GRUPOS` em `painel/ambiente.py`; `SO_COM_LEITOR = (FERRAMENTAS,)` esconde Ferramentas sem leitor com login. Ferramentas tem só o navegador (`templates/configuracoes/_ferramenta_navegador.html`; estado em `app.state.ferramentas[nome]`). Texto de hoje: "Hoje é só o navegador dos sites com login." (`configuracoes.ferramentas.explicacao`).
- **Download do navegador.** Prazo total `PRAZO_BAIXAR_S = 1800` (`navegador/limites.py`), pensado para 210 MB.
- **CSRF.** `exigir_csrf` (`painel/seguranca.py`) lê `request.form()` quando o cabeçalho do token não vem: o corpo inteiro é lido (e o Starlette grava upload acima de 1 MB em arquivo temporário) antes de qualquer teto da rota.
- **Primeira execução.** Passos montados em `painel/rotas/primeira_execucao.py` (busca, `sites` opcional, segundo plano); `_MAX_CARGOS`, `_montar`.
- **Casca.** `invoke('instalar', {navegador, progresso})` (`desktop/ui/instalador.js`), `ORDEM`/`PESOS` fixos e `MOTIVOS` (`arquivo`, `espaco`, `prova`, `navegador`, `outro`); `instalar` (`desktop/src/main.rs`); `instalar_sem_desfazer` grava o `instalacao.json` no fim (`desktop/src/instalar.rs`); `baixar_navegador` lê as linhas de `ler_linha` (`{etapa, feito, total}` e `{fim}`) e cancela com `parar_arvore`. A página Pronto só tem título e "Abrir" (`desktop/ui/index.html`).
- **CLI.** `jobot ferramentas` só aceita `baixar navegador` (`cli/ferramentas.py`).
- **Processos.** `sistema/processo.py`: `destacar`, `encerrar_grupo`, `encerrar_arvore` (fase 3, T325).
- **CI.** A `main` tem `ci.yml`, `casca.yml`, `pacotes.yml`, `release.yml`, `vigia.yml` e `wiki.yml`. O `casca.yml` roda em PR, em push de `lote/**` e por `workflow_dispatch`, com a entrada `pacotes` que chama o `pacotes.yml` reutilizável. O GitHub só despacha `workflow_dispatch` de workflow já registrado (D183.2): um workflow novo só por despacho não roda antes de chegar à `main`.
- **Status nos documentos.** `FASE_3_CONCLUIDA` e `FASE_3_EM_OBRAS` (`tests/unidade/test_documentos.py`) prendem o status da fase 3 na 0017, no índice das ADRs, no Roteiro/Roadmap, nos dois READMEs e nos dois CONTRIBUTING. A fase 4 aparece como "Planejada" em todos.
- **Andamento.** A etapa `encaixe` pesa 5 de 100 (`nucleo/andamento.py`).

## 5. Arquitetura

```
nucleo/ia/                  puro, com httpx onde fala com serviço
  contrato.py               Pedido, Resposta, Falha (motivos fechados), Protocol Backend
  esquema.py                esquema_para(backend, modelo pydantic): tira o que o backend não aceita
  tarefas.py                tarefas: esquema de saída (pydantic, extra="forbid"), VERSAO, anti-invenção
  pedidos.py                monta as mensagens (texto nosso + dados delimitados e limpos)
  compativel_openai.py      cliente /chat/completions (OpenAI, Gemini, local, Ollama, LM Studio...)
  anthropic.py              cliente /v1/messages com ferramenta forçada
  falso.py                  backend de teste (respostas prontas, grava os pedidos)
  manual.py                 (0.6.0) texto para copiar e leitura da resposta colada
nucleo/dados/ia.json        tarefas, modelos padrão, limites, prazos, tetos, cortes de memória
nucleo/dados/ia_local.json  llama-server por alvo e modelos: URL fixa, tamanho, sha256, licença, origem
nucleo/encaixe.py           critério novo `_habilidades` e o casamento normalizado (puro)
sistema/baixar.py           download com sha256, retomada, saltos só https e progresso em linhas JSON
sistema/memoria.py          memória total do computador (stdlib e ctypes)
sistema/llama.py            sobe e derruba o llama-server (lançador injetável)
sistema/pastas.py           `PASTA_FERRAMENTAS` fora da varredura de permissões
banco/migracoes/0012_ia.sql (0.5.0) perfil mínimo, habilidades_vaga, encaixe.nivel_base
banco/migracoes/0013_*.sql  (0.6.0) resto do perfil, experiencia, curso, pergunta_perfil, preparo_candidatura
banco/perfil.py, banco/ia.py  leitura e gravação
agenda/ia.py                laço das habilidades (recebe o backend pronto; não monta nada)
cli/servir.py               monta os backends (cofre, llama) e cria a tarefa do laço em `vida`
painel/rotas/ia.py, perfil.py  Configurações › IA, teste ao ligar, perfil (e, na 0.6.0, candidatura)
cli/ferramentas.py          baixar, atualizar e remover ia-local
desktop/                    Modelo local no grupo de IA do instalador
```

**Quem fala com quem.** `cli/servir.py` monta os backends (junta o cliente do núcleo, o `sistema/llama.py` e a chave do cofre) e os injeta: no laço (`agenda/ia.py`, que só recebe um `Backend` do `nucleo`) e no painel (`app.state.ia`, uma fábrica `(backend, modelo) -> Backend`, como o `deps` do login). A `agenda` continua importando só `nucleo` e `banco`; o painel continua sem `httpx`. `test_camadas.py` ganha a regra: em `src/jobot`, `jobot.nucleo.ia` só é importado por `agenda`, `painel`, `cli` e pelo próprio `nucleo.ia` (molde de `test_captcha_so_em_navegador_e_painel`). `scripts/` fica fora dessa regra, como hoje fica fora da do captcha.

**Onde mora o estado.** Na `config`: `ia_tarefas` (`{tarefa: {ligada, backend, modelo}}`, padrão tudo desligado em `PADROES`) e `ia_compativel` (`{endereco}`). No cofre: `ia_anthropic`, `ia_openai`, `ia_gemini`, `ia_compativel`. Em `app.state.ia_testes[(backend, modelo)]`: o teste ao ligar (começa em falha num `try/finally` e vira ✓ só no fim, padrões «Serve»). Em `app.state.ferramentas["ia_local"]`: o download (bytes feitos e total). Na 0.6.0, `app.state.ia_preparos[vaga_id]`: o preparo em curso, no mesmo molde.

### 5.1 Contrato

- `Pedido(tarefa, modelo, mensagens, esquema, max_tokens, prazo_s)` e `Resposta(dados: dict, backend, modelo, versao)`. `Falha(motivo)` com motivos fechados: `sem_chave`, `chave_recusada` (401/403), `sem_rede`, `programa_ausente` (o `llama-server` não abre), `modelo_ausente` (404 de modelo, ou modelo local não baixado), `tempo_esgotado`, `limite` (429), `esquema_recusado` (400: "o serviço não aceita saída por esquema"; tente outro modelo), `servico_fora` (5xx), `recusa` (sem saída estruturada), `formato` (não passou no esquema), `contexto` (o pedido passou do contexto do modelo). Cada motivo tem texto pt/en com o que fazer (ADR 0009, Teste ao ligar), e um teste percorre o `Literal` e exige as duas chaves.
- **Falha do backend e falha da vaga.** `sem_chave`, `chave_recusada`, `sem_rede`, `programa_ausente`, `modelo_ausente`, `tempo_esgotado`, `limite`, `esquema_recusado` e `servico_fora` são do backend; `recusa`, `formato` e `contexto` são do pedido. O laço trata os dois de jeito diferente (5.4).
- Toda resposta passa pelo modelo pydantic da tarefa (`model_validate`). Não passou: `Falha("formato")`, uma tentativa só, sem repetir sozinho.
- **Esquema por backend.** O esquema completo sai de `model_json_schema()`; `esquema_para(backend, modelo)` tira o que cada backend não aceita, e os limites tirados continuam conferidos pelo pydantic na resposta. llama.cpp: repetição acima de 2000 quebra a gramática (`MAX_REPETITION_THRESHOLD` em `src/llama-grammar.cpp` do b12359), então `maxLength` e `maxItems` acima de 2000 saem. OpenAI `strict`: só as palavras-chave da lista da documentação (conferida na T405 em 2026-11-17: sem `maxLength`, e todo campo em `required`). Gemini compatível e compatível genérico: a da OpenAI sem `pattern`, `multipleOf` e os `exclusive*`, que o Gemini não cita (D191.1). Anthropic (`input_schema`): o esquema inteiro. Teste por backend: toda palavra-chave do esquema enviado está na lista permitida daquele backend.
- **Prazo, tamanho e gasto por chamada.** `prazo_s` (60 s fora, 180 s local; proposta, revistos pela medida da T410) vira o `timeout` do `httpx`, que fecha a conexão (o `llama-server` cancela o pedido quando a conexão fecha). `max_tokens` por tarefa em `ia.json` (a API da Anthropic exige; nos outros limita o gasto). Resposta com teto de 1 MB, lida em fluxo.
- **Cliente HTTP da IA.** `httpx.Client` próprio da IA (não o `ClienteEducado`, que é da coleta): `follow_redirects=False` (chave e dado nunca são reenviados a outro host, padrões «HTTP»), e `trust_env=False` no modelo local (um proxy do ambiente não leva para fora o pedido ao `127.0.0.1`).
- **Endereço do compatível.** `http` só para `127.0.0.1`, `localhost` e `::1`; fora disso, só `https`. Recusa `usuario:senha@`, query, fragmento e espaço ou caractere invisível no meio; espaço nas pontas sai (D191.13).
- **Versão.** Cada tarefa tem `VERSAO` (sobe quando o texto do pedido ou o esquema mudam). O resultado guardado leva `versao`, `backend` e `modelo`.

### 5.2 As tarefas

| Tarefa | Versão | Entrada (lista permitida) | Saída do modelo | Conferência no código | Padrão Claude |
|---|---|---|---|---|---|
| `encaixe` | 0.5.0 | título e descrição da vaga, cortados (abaixo) | `pede` (≤ 30 itens de ≤ 60 caracteres) | cada item de `pede` aparece, normalizado, no texto enviado; repetidos saem. `tem` e `faltam` são do código (5.5) | Haiku 5.5 |
| `curriculo` | 0.6.0 | texto do PDF, sem e-mail, telefone e CPF (tirados por regex antes) | campos da lista permitida do perfil, experiências e cursos | valor que não aparece, normalizado, no texto do PDF vem marcado "não achei no currículo" | Sonnet 5.5 |
| `perguntas` | 0.6.0 | campos da lista permitida do perfil e as perguntas já feitas | até 5 `{pergunta, por_que}` | repetida sai; pergunta com mais de uma linha, mais de 200 caracteres ou URL sai | Sonnet 5.5 |
| `candidatura` | 0.6.0 | campos da lista permitida do perfil, experiências, cursos, respostas; título e descrição da vaga | `idioma`, `carta`, `resumo`, `perguntar` (≤ 5), `usou` | `usou` só com chaves preenchidas; `tem`/`faltam` do código (5.5); aviso quando a carta ou o resumo citam item de `faltam` | Sonnet 5.5 |

- **Lista permitida, não lista proibida** (D185.22). Cada tarefa declara os campos que entram; o resto nunca entra. Nome, e-mail, telefone e cidade nunca entram em nenhuma. Todo texto livre que entra (resumo, descrição de experiência, resposta de pergunta) passa pela mesma limpeza de e-mail, telefone e CPF. O teste serializa o pedido de um perfil com o e-mail escondido no resumo e numa resposta e exige que o e-mail não apareça.
- **Corte do texto.** Teto de caracteres por tarefa e backend em `ia.json`, tirado do contexto do modelo (local: `-c 8192`). Vaga: 6000 caracteres (proposta), guardando os 4000 primeiros e os 2000 últimos (requisitos costumam ficar no fim); currículo: 12000 no local e 40000 fora (proposta). Cortou: a tela diz "a IA leu só parte do texto". Mesmo assim o pedido passa do contexto: `Falha("contexto")`.
- **Determinismo.** `encaixe` e `curriculo` vão com temperatura 0 e `seed` fixo no corpo do pedido (onde o backend aceita), para a mesma vaga dar o mesmo `pede`. A OpenAI não leva `temperature` (os modelos de raciocínio só aceitam o padrão) e leva `max_completion_tokens` no lugar de `max_tokens` (D191.12).
- Offline, todas as tarefas usam o Qwen local. Nunca Opus (ADR 0009).

### 5.3 Pedido e dados de terceiros

- A mensagem de sistema é nossa e diz o papel, a regra de ouro e que tudo dentro das marcas `<<<VAGA` … `VAGA>>>`, `<<<CURRICULO` … `CURRICULO>>>` e `<<<PERFIL` … `PERFIL>>>` é dado, nunca instrução. Marcas que aparecerem dentro do dado são trocadas antes de montar.
- Nenhum backend tem ferramenta, MCP, acesso a arquivo ou rede além da própria resposta (o `llama-server` não tem ferramentas).
- **Injeção.** No `encaixe`, a vaga não vê o perfil: ela não consegue mirar no que a pessoa tem, e o que ela pede só vale se estiver escrito nela. Na `candidatura`, a vaga e o perfil vão juntos: o pior caso é uma carta torta, que a pessoa lê antes de copiar, e o aviso de `faltam` citado.
- O texto gerado só é mostrado (o Jinja escapa) e copiado pela pessoa; nunca vira HTML, comando, URL clicável ou mensagem enviada.
- Log: só tarefa, backend, modelo, duração, tamanho e motivo da falha. Nunca o texto do pedido nem da resposta, nunca a chave.

### 5.4 Laço das habilidades

`calcular()` continua puro e síncrono; a extração roda num passo à parte (D185.12):

1. **Onde.** Uma tarefa asyncio própria, criada em `vida` (`cli/servir.py`), com conexão própria, fora de `executar_busca` e da trava da busca; cancelada no `finally` (padrões «Serve»). A chamada ao backend roda em `asyncio.to_thread`; o painel não espera nada. Ao encerrar com pedido em curso, o cancelamento fecha a conexão (o `llama-server` para).
2. **Quando.** Acorda por um `asyncio.Event` que a execução da busca marca no fim (a `agenda` só marca o evento, não chama a IA) e quando a pessoa liga a tarefa. Não roda ao subir o servidor. Uma rodada por vez: pedidos durante uma rodada viram uma rodada só depois dela.
3. **A fila.** Vagas abertas, não ocultas, com `encaixe.nivel_base` (o nível **sem** o critério de habilidades) `bom` ou `medio` em alguma busca, sem linha em `habilidades_vaga` ou com `chave` diferente da atual, das mais novas para as mais velhas, até `max_por_rodada` (20, proposta). A `chave` é o hash do texto enviado (título e descrição cortados) + `VERSAO` + backend + modelo. Ela **não** leva o perfil: mudar as habilidades não reenvia nada (5.5).
4. **Cada vaga.** Pede ao backend, confere e grava `pede` em `habilidades_vaga` (uma linha por vaga). Depois chama `recalcular_encaixe(vaga_id=...)`. A chamada roda fora da transação; só a gravação abre a escrita.
5. **Falhas.** Falha do backend (5.1) para a rodada e não marca a vaga. Falha da vaga grava `falha`, `falha_em`, `falha_chave` e soma `tentativas`; a vaga só volta com `chave` nova, até `max_tentativas` (2, proposta) por chave. Falha nunca apaga um `pede` anterior.
6. **Pedido da pessoa primeiro.** Enquanto há teste ao ligar ou (0.6.0) preparo em curso, o laço espera entre uma vaga e outra (com `-np 1`, os dois brigariam pelo mesmo slot).
7. **Teto por dia.** Num backend de fora, no máximo `max_por_dia_fora` (200, proposta) chamadas do laço por dia local, contadas pelas linhas de `habilidades_vaga` com `feito_em` ou `falha_em` de hoje naquele backend; a aba IA mostra "N de 200 hoje". O local não tem teto.
8. O andamento da busca não muda. Nenhuma linha nova no painel de execução: o detalhe da vaga mostra o resultado e a aba IA mostra a contagem.

### 5.5 Encaixe com habilidades

- O perfil mínimo da 0.5.0 é `perfil.habilidades` (lista). `calcular(..., habilidades_vaga: list[str] | None = None, habilidades_perfil: list[str] = ())`.
- **Casamento no código, puro.** `tem` = itens de `pede` cuja forma normalizada (caixa, acento, espaços, pontuação das pontas) é igual à de alguma habilidade do perfil; `faltam` = `pede` menos `tem`; sem repetidos. A razão `len(tem) / len(pede)` fica entre 0 e 1 por construção e o código ainda limita a 1. A nota muda na hora quando a pessoa edita as habilidades, sem chamada nova.
- `_habilidades`: sem linha ou `pede` vazio → `None`, neutro (a nota fica igual à de hoje). Senão pontos = peso × razão, arredondado como os outros. Peso **25** em `encaixe.json` (proposta).
- `Encaixe` ganha `nivel_base` (o nível sem o critério), gravado em `encaixe.nivel_base` para a fila (5.4). As regras de ocultar não mudam (D185.11).
- Motivos: `vagas.motivo.habilidades_tem` e `vagas.motivo.habilidades_faltam` (`{lista}`, até 5 nomes), nos dois catálogos; o detalhe mostra a lista inteira, diz que a lista veio da IA (backend e modelo) e avisa quando o texto foi cortado.
- Sinônimos ("Postgres" e "PostgreSQL") ficam de fora na 0.5.0. Se a medida mostrar perda grande, uma tarefa curta e opcional só de sinônimos, com duas listas pequenas, sem o resto do perfil (D185.11).

### 5.6 Custo para quem usa

- Todo serviço pago aparece na aba IA como "cobrado por uso", com o nome do serviço. O atalho "Tudo Claude" diz "API da Anthropic, cobrada por uso"; não há troca automática entre assinatura e API.
- Ligar o `encaixe` num serviço pago mostra um aviso de custo (até `max_por_dia_fora` chamadas por dia) antes de gravar.
- `max_tokens` por tarefa; o teste ao ligar é um pedido curto, com `max_tokens` pequeno, e só roda quando o par (backend, modelo), a chave ou o endereço mudam.
- Fora do Claude a pessoa digita o modelo (D185.23); a aba IA não sugere modelo caro.

## 6. Backends

| Backend | Como fala | Chave | Versão |
|---|---|---|---|
| Compatível com OpenAI | `POST <endereço>/chat/completions`, `response_format` `json_schema` | opcional, cofre (`ia_compativel`) | 0.5.0 |
| OpenAI | o mesmo cliente, `https://api.openai.com/v1` fixo | cofre (`ia_openai`) | 0.5.0 |
| Google Gemini | o mesmo cliente, endpoint compatível do Gemini (`https://generativelanguage.googleapis.com/v1beta/openai`, conferido na T405) | cofre (`ia_gemini`) | 0.5.0 |
| Modelo local | o mesmo cliente, `http://127.0.0.1:<porta>/v1`, com o `llama-server` do joBot (seção 7) | aleatória por subida, só em memória | 0.5.0 |
| API da Anthropic | `POST https://api.anthropic.com/v1/messages` com uma ferramenta `responder` forçada (`tool_choice`), lendo o `input` | cofre (`ia_anthropic`) | 0.5.0 |
| IA manual | o painel mostra o pedido para copiar e um campo para colar a resposta | — | 0.6.0, só nas tarefas sob pedido |
| Sem IA | regras de hoje | — | padrão |
| Sessão do Claude Code | `claude -p` (ADR 0010) | login da ferramenta | espera o dono (6.2) |
| Sessão do Codex CLI | `codex exec` (D125) | login da ferramenta | espera o dono (6.2) |

- **Ollama e LM Studio** entram pelo compatível (D108), com o endereço de cada um como sugestão (`http://127.0.0.1:11434/v1`, `http://127.0.0.1:1234/v1`). O joBot não os instala.
- **Modelos.** Claude: só `claude-haiku-5-5` e `claude-sonnet-5-5`, por tarefa (ADR 0009). OpenAI, Gemini e compatível: a pessoa digita o nome; o teste ao ligar confere. Local: o Qwen baixado (o nome vem do manifesto).
- **Ainda não provados.** OpenAI, Gemini e a API da Anthropic só são testados com transporte falso: o CI não tem segredo. Até alguém rodar `scripts/provar_ia.py --backend <serviço>` com a própria chave e anotar na D185 (pergunta ao dono, seção 15), a aba IA e o README os marcam "experimental, ainda não provado".
- **Atalhos** (ADR 0009): "Desligada" (padrão), "Tudo offline" (modelo local; sem o modelo baixado, leva a Ferramentas), "Tudo Claude" (API da Anthropic, cobrada por uso, com a chave) e "Personalizado" (a tabela por tarefa).

### 6.1 Teste ao ligar

Ao ligar uma tarefa ou trocar backend, modelo, chave ou endereço, o painel grava a escolha, responde na hora com o sinal de espera e põe o teste do par (backend, modelo) numa fila: um teste por par, em ordem, com o prazo contado do começo de cada um (30 s fora, 180 s local, contando a primeira carga do modelo; proposta). Assim o "Tudo offline" faz um teste só, não quatro na mesma fila do `llama-server`. O teste é um pedido curto da tarefa com um exemplo fictício fixo. Passou: ✓ e a tarefa liga. Falhou: o motivo com o que fazer, e a tarefa fica desligada (ADR 0009, Teste ao ligar). O fragmento pergunta a cada 2 s (HTMX). O teste é por par (backend, modelo), não por tarefa: duas tarefas no mesmo par usam o mesmo resultado (D185.21).

### 6.2 Sessões do Claude Code e do Codex (esperam o dono)

Não entram na 0.5.0 nem na 0.6.0. Perguntas ao dono (D185.5, D185.6, D185.18): ele leu o texto legal do Claude Code e os Termos da OpenAI e libera o login de assinatura para o uso do joBot? Aceita o instalador do Claude Code por script remoto sem sha256 fixado (a D183.20 diz que baixar e rodar sem sha256 só o dono aceita)? Com as respostas, um lote próprio constrói e prova na máquina dele, com estas condições já escritas:

- Pedido sempre pela entrada padrão. Opções que deixam de fora as instruções do usuário (`~/.claude/CLAUDE.md`, hooks, plugins; `~/.codex`): `--setting-sources`, `--system-prompt` e o equivalente do Codex, conferidos no `--help` da versão da época.
- ADR 0010 inteira (ambiente sem `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_USE_*`, `CLAUDE_CODE_OAUTH_TOKEN`; sem `--bare`; pasta temporária vazia; `claude auth status` antes). Nunca abrir `~/.claude`, o Keychain nem `~/.codex/auth.json`. Processo com prazo e `encerrar_arvore`.
- Login por `claude auth login` e `codex login` lançados destacados, com o comando para copiar como reserva; nenhum terminal aberto pelo joBot (ADR 0023).
- O Codex, se baixado pelo joBot, segue o manifesto com versão, sha256 e licença, e "Atualizar" quando o manifesto muda.
- Testes de recusa: com o backend não liberado, rota, CLI e casca recusam.
- Botões "Entrar" no Pronto do instalador (D139.14): só nesse lote, depois do dono.

## 7. Modelo local

- **O que baixa** (D185.7): o `llama-server` do build **b12359** (os binários da tag `v1.0.0`, a release estável, com atestação SLSA e `digest` sha256 na API do GitHub; o b12366 da ADR 0009 também tem `digest`, a troca é pela release estável) e um GGUF da Unsloth: `Qwen3.5-2B-Q4_K_M.gguf` (1 280 835 840 B) ou `Qwen3.5-4B-Q4_K_M.gguf` (2 740 937 888 B). Arquivos por alvo: `llama-b12359-bin-ubuntu-x64.tar.gz`, `-win-cpu-x64.zip`, `-macos-arm64.tar.gz`, `-macos-x64.tar.gz`. Roda só em CPU em todo alvo (`-ngl 0`; o binário do Mac arm64 tem Metal, mas o joBot não o usa).
- **Manifesto** `nucleo/dados/ia_local.json`: por arquivo, URL com versão fixa (GitHub `releases/download/b12359/...`; Hugging Face `resolve/<commit>/...`, nunca `main`), tamanho, sha256 (`digest` do GitHub e oid LFS do Hugging Face; o llama-server também com `gh attestation verify --owner ggml-org`), **licença** e **origem** (MIT, llama.cpp/ggml-org; Apache-2.0, Qwen/Unsloth; conferidas em 2026-11-17). Testes: toda URL tem versão fixa, todo arquivo tem sha256 de 64 dígitos, tamanho, licença e origem. O cartão de Ferramentas mostra licença e origem.
- **De onde** (D185.7): da fonte oficial, pelo joBot, a pedido da pessoa (instalador com o item marcado, ou Ferramentas › Baixar). Não vai no instalador nem na release: o 4B passa do limite de 2 GiB por anexo de release do GitHub e o instalador passaria de 1,5 GB. É uma segunda exceção à D174.1, do tipo da D183.24 (que o dono ainda não confirmou), com sha256 conferido.
- **Onde fica:** `<dados>/ferramentas/llama/b12359/` e `<dados>/ferramentas/modelos/<arquivo>.gguf`. `PASTA_FERRAMENTAS = "ferramentas"` entra em `preparar_pasta` como `PASTA_NAVEGADOR` e `PASTA_DA_CASCA`: só a pasta fecha, o conteúdo não (o `+x` do `llama-server` sobrevive à subida seguinte). O que está baixado fica anotado em `<dados>/ferramentas/ia_local.json` (build, modelo, sha256); se o manifesto da versão nova do joBot mudar, o cartão mostra "Atualizar".
- **Download** (`sistema/baixar.py`): `httpx` em fluxo, user agent do joBot. Antes: `shutil.disk_usage` contra o tamanho do manifesto. Grava em `<arquivo>.<12 primeiros do sha256>.parcial`, retoma com `Range` (servidor que responde 200 recomeça), corta ao passar do tamanho do manifesto, confere tamanho e sha256 no fim e só então `os.replace`. Sem prazo total: prazo de inatividade (60 s sem bytes, proposta) e retomada. Saltos: só `https`, no máximo 5 (regra injetável no teste, que roda em `http` local). Trava de arquivo por download (casca, painel e CLI não escrevem o mesmo `.parcial`). Motivos fechados: `sem_rede`, `espaco`, `arquivo` (sha256 ou tamanho; apaga o `.parcial`) e `cancelado` (mantém o `.parcial` para retomar). Progresso em linhas JSON `{"etapa":"ia_local","feito":N,"total":T}` e `{"fim":...}` (o protocolo do navegador). Primeiro o `llama-server` (23 MB) e `llama-server --version`; só então o modelo, para falhar em 23 MB e não em 2,7 GB. Extração do `.tar.gz` com `tarfile` e `filter="data"`; do `.zip` com `zipfile`, recusando caminho para fora; no Linux e no Mac, `chmod +x`.
- **Qual modelo** (D139.11, D185.19): `sistema/memoria.py` lê a memória total em bytes (`os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")` no Linux e no Mac; `GlobalMemoryStatusEx` por `ctypes` no Windows). O sistema informa menos que o nominal (um PC de 16 GB informa uns 13,3 GiB). Cortes em `ia.json`, em GiB (2^30 bytes), com folga: 4B a partir de 11 GiB; 2B abaixo; aviso "pode ficar lento" só abaixo de 7 GiB (proposta). Teste com valores reais: 7,7 GiB (um PC de 8 GB) leva o 2B sem aviso; 11,5 GiB (um PC de 12 GB) leva o 4B. A pessoa troca em Ferramentas › Trocar modelo, com o tamanho à vista.
- **Rodar** (`sistema/llama.py`, lançador injetável): sobe sob demanda, na primeira chamada local; `llama-server -m <gguf> --host 127.0.0.1 --port <porta> -c 8192 -np 1 -ngl 0 --no-webui --no-slots --reasoning off --sleep-idle-seconds 600` e a amostragem na subida (opções conferidas com `--help` do b12359 na T408). A chave vai pelo ambiente (`LLAMA_API_KEY`) ou por `--api-key-file` 0600, o que o `--help` tiver; nunca no argv (`ps` mostra a todos). Saída em `DEVNULL`. Pelo `processo.py` (sessão própria, encerra a árvore). Espera `GET /health` até 120 s; só fala com a porta se o filho segue vivo (porta tomada no meio vira `programa_ausente`, não pedido a outro processo). PID e porta em `<dados>/ferramentas/llama.json`; a subida do servidor do joBot encerra a sobra de uma subida anterior que morreu. Uma instância só por joBot; cai quando o servidor do joBot para. O `--sleep-idle-seconds` descarrega o modelo depois de 10 min parado, no lugar de um temporizador nosso; o `--reasoning off` desliga o pensamento do Qwen3.5 sem campo próprio no cliente.
- **Remover** (Ferramentas › Remover, `jobot ferramentas remover ia-local`): derruba o `llama-server`, apaga as duas pastas e desliga as tarefas que usavam o local. Desinstalar a casca não apaga a pasta de dados: o README de desinstalar diz que `ferramentas` pode ocupar até 2,7 GB e como apagar.
- **Velocidade.** Medição de terceiros: 4B Q4_K_M em CPU compartilhada gerou 8,6 tokens/s; a leitura do pedido em CPU também pesa (2000 tokens de vaga). Estimativa sem medida: de 1 a 2 min por vaga no 4B. Por isso o limite por rodada, o laço fora da busca e a medida da T410 antes das telas.

## 8. Perfil, currículo e questionário

- **0.5.0** (migração `0012_ia.sql`, D185.13): `perfil` de uma linha (`id = 1` com CHECK): `habilidades` (JSON, lista) e `atualizado_em`. Configurações ganha a aba **Perfil** com as habilidades (uma por linha) e "Apagar perfil", que apaga a linha; as `habilidades_vaga` ficam, porque não dependem do perfil. A frase "suas habilidades ficam no seu computador; só o texto da vaga vai para <serviço>" fica na aba Perfil e na aba IA.
- **0.6.0** (migração `0013`): colunas novas em `perfil` (`nome`, `email`, `telefone`, `cidade_moradia`, `cargo_atual`, `anos_de_experiencia`, `formacao_nivel`, `resumo`, `idiomas_falados`, `links`), mais `experiencia`, `curso` e `pergunta_perfil`. Sem CPF, sem data de nascimento e sem projetos (ADR 0011 inclui projetos; corte para confirmar, D185.13). **O texto do currículo não é guardado**: só serve à extração e some no fim do pedido. "Apagar perfil" apaga também experiências, cursos, perguntas e preparos.
- **Currículo** (0.6.0, ADR 0011): a rota de upload exige o cabeçalho do token CSRF (não cai no `request.form()` de `exigir_csrf`) e recusa pelo `Content-Length` acima de 5 MB antes de ler o corpo. O `pypdf` roda num **processo filho** com prazo de 30 s e `encerrar_arvore` (uma thread não para um PDF patológico), lendo até 20 páginas (proposta). PDF com senha, corrompido, que não é PDF ou só de imagem: aviso próprio, nos dois idiomas. O PDF não vai para a pasta de dados nem para o banco; o arquivo temporário do Starlette (upload acima de 1 MB) some ao fim do pedido. É isso que o teste mede.
- **Extração** (tarefa `curriculo`): o formulário vem preenchido; cada valor que não aparece, normalizado, no texto do PDF vem marcado "não achei no currículo" e fica fora do "Aprovar todas". E-mail, telefone e CPF são tirados do texto antes de mandar e preenchidos no próprio computador, por regex. Nada é gravado antes do "Salvar". Sem IA (ou com falha), o formulário vem vazio. A frase "o texto do currículo vai para <serviço>" fica junto do upload.
- **Questionário.** Perguntas base: as do bloco A do mapa (A1 a A9) mais nome, e-mail, telefone e links. Com a tarefa `perguntas` ligada, até 5 perguntas de lacuna (5.2); a pessoa responde ou ignora; a resposta fica em `pergunta_perfil` e entra nos pedidos como dado (com a limpeza de contato).

## 9. Preparar candidatura (0.6.0)

- Botão "Preparar candidatura" no detalhe da vaga, ao lado dos de hoje (`contexto_do_detalhe`, `painel/detalhe_vaga.py`), só com a tarefa `candidatura` ligada; sem ela, leva a Configurações › IA. Sem perfil, explica o que falta. A frase "o seu perfil e o texto da vaga vão para <serviço>" fica junto do botão.
- `POST /vagas/{id}/candidatura/preparar` (CSRF) dispara a tarefa e devolve o fragmento de espera (polling de 2 s). Clique duplo com preparo em curso não dispara outro. O resultado fica em `preparo_candidatura` (uma linha por vaga, `ON CONFLICT DO UPDATE`): `idioma`, `carta`, `resumo`, `tem`, `faltam`, `perguntar`, `usou`, `backend`, `modelo`, `versao`, `feito_em`. Falha (backend, prazo, formato) mostra o motivo e mantém o preparo anterior.
- A tela mostra carta e resumo em caixas editáveis com "Copiar", "Você tem" e "Falta" (do código, 5.5), "Dados que a IA usou" (`usou`), o aviso fixo "Confira antes de usar: a IA pode errar." e, quando for o caso, "A carta cita algo que não está no seu perfil: <item>". As perguntas de `perguntar` passam pela conferência de `perguntas` e viram `pergunta_perfil` (origem `ia`).
- O texto sai no idioma da vaga (`VagaTratada.idioma`; sem ele, o do painel).
- O joBot nunca envia nada: o `mailto:` de hoje (só o assunto, ADR 0014) não ganha o corpo.
- IA manual: o fragmento mostra o pedido para copiar e o campo para colar; a resposta colada passa pelo mesmo esquema e pelas mesmas conferências.

## 10. Instalador, Ferramentas, Serviços e Configurações › IA

### 10.1 Instalador (casca, 0.5.0)

- Grupo novo "Inteligência artificial (opcional)" no passo Ferramentas, depois do navegador, só com o **Modelo local**, **desmarcado** (D139.3). Frase: "Para usar IA sem internet e sem pagar. Baixa da internet de 1,3 a 2,7 GB, conforme a memória do computador; dá para baixar depois em Configurações › Ferramentas." (D139.2: "baixa se você marcar", nunca "vem com").
- `invoke('instalar', {navegador, modelo_local, progresso})`; `estado_instalador` devolve os tamanhos dos dois modelos, lidos do `manifesto.json` dos recursos, que o build escreve a partir do `ia_local.json` (o venv ainda não existe nessa tela).
- **Ordem** (D185.17): o Modelo local roda **depois** de gravado o `instalacao.json`, pelo `jobot ferramentas baixar ia-local` do venv, lendo as mesmas linhas JSON; `ler_linha` aceita a etapa `ia_local`. Etapa "Baixando o modelo local" com barra por bytes; o rodapé de espaço soma o modelo.
- **Falha do Modelo local não é falha da instalação**: a página Pronto diz o que não baixou e "Baixe depois em Configurações › Ferramentas". Fechar a janela no meio pede confirmação, encerra a árvore e **mantém** o `.parcial` (Ferramentas retoma); o joBot fica instalado.
- Textos em `desktop/ui/i18n/{pt,en}.json`.

### 10.2 Ferramentas (0.5.0)

- Sempre visível (D185.20): `SO_COM_LEITOR` sai; o cartão do navegador só aparece com leitor com login, como hoje.
- Cartão Modelo local: estado, modelo baixado, tamanho, licença e origem; "Baixar" (com barra por bytes), "Trocar modelo" (2B ↔ 4B, tamanho à vista), "Atualizar" (manifesto mudou) e "Remover". Molde do `_ferramenta_navegador.html` (fragmento HTMX, `app.state.ferramentas[nome]`, polling de 5 s).
- `configuracoes.ferramentas.explicacao` perde o "Hoje é só o navegador dos sites com login." nos dois catálogos.

### 10.3 Serviços e Configurações › IA (0.5.0)

- Serviços ganha cartões de chave: Anthropic, OpenAI, Google Gemini e "Compatível com OpenAI" (endereço e chave opcional), no molde do 2Captcha: grava no cofre (`no_cofre`), nunca devolve a chave ao HTML, "Apagar", aviso quando o cofre cai no arquivo 0600. Eles não dependem dos clientes: só guardam.
- Aba nova **IA** em Configurações (`GRUPOS`, depois de Funções; proposta): os atalhos no topo; uma linha por tarefa com liga/desliga, backend (só os configurados) e modelo; o estado do teste; a frase de privacidade ("o texto da vaga vai para <serviço>" ou "fica no seu computador"); "cobrado por uso" e "experimental, ainda não provado" onde couber; "N de 200 hoje" do laço.

### 10.4 Primeira execução (0.6.0)

Dois passos novos, opcionais, antes dos de hoje (ADR 0011; D185.15): **IA** (os atalhos e "Pular") e **Perfil** (currículo e perguntas do bloco A, com as perguntas de lacuna se a tarefa estiver ligada; "Pular"). O passo de busca continua e chega com cargo atual e cidade do perfil.

## 11. Segurança e privacidade

- IA desligada por padrão; nada sai do computador sem a pessoa ligar uma tarefa num backend de fora. Cada tarefa diz, na aba IA e junto do botão ou do upload, o que vai e para onde.
- **Pedidos novos que o joBot faz**, todos a pedido da pessoa: os serviços de IA (Anthropic, OpenAI, Google Gemini, o endereço do compatível) e os downloads do modelo local (GitHub, com o CDN de anexos, para o `llama-server`; Hugging Face, com o CDN dele, para o Qwen). O README, a tela Privacidade e o `CITA` de `test_privacidade_cita_todos_os_pedidos` ganham todos (ADR 0014; como a D183.24 fez com o CDN do Playwright).
- Minimização por lista permitida e limpeza de contato (5.2). O `encaixe` só leva o texto da vaga, que já é público.
- Chaves no cofre (ADR 0009, ADR 0014); nunca no log, no HTML nem em mensagem de erro.
- Cliente da IA sem seguir salto, com teto de resposta, e `trust_env=False` no local (5.1); endereço do compatível conferido (5.1).
- `llama-server` em `127.0.0.1`, porta livre, chave por subida fora do argv, `--no-slots`, sem web UI; PID guardado e sobra encerrada (7).
- Downloads: só URLs do manifesto, saltos só `https`, sha256 conferido antes de usar, tamanho cortado, espaço conferido (7).
- Injeção pelo texto da vaga: sem ferramentas, saída só por esquema, item de `pede` só se estiver na vaga, texto mostrado escapado, a pessoa revisa tudo.
- Regra de ouro na entrada do perfil: o que a IA extrai do currículo e não está no texto vem marcado e não entra no "Aprovar todas" (8).

## 12. Testes e provas

- **Critérios de guarda.** Critério que pode nascer verde (uma recusa, uma ausência, "não muda") leva mutação numa cópia que o derruba (padrões «Teste que nasce verde») e um controle positivo que prova que o teste vê o caso (padrões «Nome de teste»). O plano marca cada um com "(guarda)".
- **Unidade (sem rede):** esquemas, `esquema_para` por backend contra a lista permitida, anti-invenção e casamento (com respostas que inventam, `pede` repetido, item fora do texto da vaga, vaga com instrução embutida); montagem das mensagens (marcas trocadas, lista permitida, limpeza de contato); cada cliente HTTP com `httpx.MockTransport` (sucesso, 400, 401, 404, 429, 5xx, prazo, conexão fechada no prazo, salto recusado, resposta acima do teto, JSON fora do esquema, recusa); `baixar.py` com servidor em thread em `127.0.0.1` (retomada, 200 no lugar de 206, sha256 errado, corte acima do tamanho, espaço, inatividade com relógio injetado, salto, trava, cancelado mantém o `.parcial`); `memoria.py` com valores reais; `llama.py` com lançador injetado e servidor em thread (argv sem a chave, `--no-slots`, `-ngl 0`, `/health`, filho morto antes da porta, sobra de PID); `preparar_pasta` com `ferramentas` (o `+x` fica); manifesto (versão fixa, sha256, licença, origem); `_habilidades` puro; todo motivo de `Falha` com texto pt e en; `test_camadas.py` com a regra nova.
- **Integração:** migrações; laço com `BackendFalso` (fila por `nivel_base`, limite, chave, falha de backend para a rodada, falha de vaga com tentativas, três vagas que sempre falham na frente não impedem a quarta, duas rodadas pedidas juntas viram uma, teto do dia, perfil muda e a nota muda sem chamada nova); rotas de IA e perfil (CSRF, teste ao ligar em fila, polling, chave nunca no HTML, aviso de custo); Ferramentas com o download falso.
- **Tela (Playwright, CI):** aba IA, teste ao ligar, aba Perfil, Ferramentas › Modelo local, instalador com o grupo de IA (`__TAURI__` falso). Na 0.6.0: preparar candidatura, upload do currículo, passos da primeira execução.
- **Rust:** `ler_linha` com `ia_local`, ordem (depois do `instalacao.json`), falha que não desfaz, cancelamento que mantém o `.parcial`.
- **Modelo de verdade** (`.github/workflows/ia.yml`, **reutilizável**, `on: workflow_call`, chamado por um job `ia` do `casca.yml` atrás de uma entrada `ia` do `workflow_dispatch`, no molde da entrada `pacotes`; o `casca.yml` já está registrado na `main`, então roda num `lote/**` por `gh workflow run casca.yml --ref lote/<nome> -f ia=true`). `contents: read`, sem segredo, Actions por hash. Matriz: `ubuntu-22.04` (a base da casca, D180.1), Windows e Mac. Passos: `jobot ferramentas baixar ia-local --modelo auto` (imprime a memória lida e o modelo escolhido) e `--modelo 2b`; `scripts/provar_ia.py` com o conjunto de ouro (abaixo) e meta; `scripts/medir_modelo.py` (tokens/s de leitura e de geração, tempo por vaga) no resumo do job. `tests/unidade/test_ia_ci.py` trava `workflow_call`, a entrada no `casca.yml`, permissões e ausência de segredo.
- **Conjunto de ouro** (`tests/fixtures/ia/ouro_habilidades.json`, fictício, escrito por nós): umas 20 vagas curtas com a lista esperada de habilidades. Casos óbvios: a vaga pede Python e o perfil tem Python, então `tem` contém Python; `pede` nunca vazio quando a vaga lista requisitos. Meta (proposta): pelo menos 80% dos itens esperados achados e nenhuma vaga com `pede` vazio, no 2B e no 4B. Abaixo da meta, o padrão sobe para o 4B onde couber ou volta ao dono (risco 4). O mesmo script prova um serviço de fora com `--backend` e a chave numa variável de ambiente, rodado à mão por quem tem a chave.
- **Dono (portão):** instalar a 0.5.0 com o Modelo local marcado, ligar "Tudo offline", pôr as habilidades, rodar uma busca, ver as habilidades e medir o tempo por vaga na máquina dele. Só ele prova: o instalador de verdade com o item marcado, a retomada contra os CDNs reais, o Defender e o SmartScreen no `llama-server.exe` e a velocidade num PC comum. O README diz o que só foi provado no CI (selo de plataforma, D184.4).

## 13. Riscos

1. **Termos dos backends de sessão** (D185.5, D185.6): fora até o dono responder (6.2).
2. **Velocidade do Qwen em CPU** (de 1 a 2 min por vaga no 4B, sem medida): laço fora da busca, limite por rodada, fila só de vagas boas e médias; a T410 mede antes das telas e os números podem mudar limites, prazos e cortes.
3. **Qualidade do 2B**: a gramática garante a forma, não o conteúdo; o conjunto de ouro tem meta (12).
4. **Gramática do llama.cpp**: `maxLength`/`maxItems` acima de 2000 quebram; `esquema_para` tira e o `ia.yml` prova no servidor de verdade.
5. **Invenção na carta** (0.6.0): o código confere `usou` e avisa quando a carta cita `faltam`; a carta é texto livre que a pessoa lê.
6. **Injeção pelo texto da vaga**: no `encaixe`, a vaga não vê o perfil e só vale o que está escrito nela; na `candidatura`, carta torta que a pessoa lê.
7. **Download grande** (até 2,7 GB) e CDN fora do ar: retomada por `Range`, inatividade sem prazo total, sha256, espaço conferido; falha não desfaz o joBot.
8. **Memória**: `llama-server` (2 a 5 GB) + Chromium + painel em 8 GB. Uma instância, modelo descarregado depois de 10 min, 2B abaixo de 11 GiB.
9. **Binário do llama.cpp no Linux** feito para uma glibc nova pode não abrir em distro velha: `llama-server --version` logo depois do download; falhou, `programa_ausente` com o que fazer (o Ollama pelo compatível). O `ia.yml` roda na `ubuntu-22.04`.
10. **PDF malicioso ou pesado** (0.6.0): 5 MB pelo `Content-Length`, 20 páginas, processo filho com prazo.
11. **Serviços pagos sem prova real**: "experimental, ainda não provado" até alguém rodar o `provar_ia.py --backend` (6).
12. **Laya**: o `convaiinnovations/laya-multilingual` (Apache-2.0, sobre mmBERT-base, 322M) é um modelo de decisão (escolha, nota, "verdadeiro ou falso"), não de embedding de competências. Não há conjunto de ouro de habilidades no gabarito da ADR 0007 (ele mede rótulos); o conjunto de ouro fictício (12) é a medida mínima para comparar.

## 14. Documentos que mudam

- **Na T400** (com teste): ADR nova **0026. IA da fase 4: tarefas, backends e modelo local** (resume a D185 com "para confirmar"); status da fase 4 juntos (padrões «Troca de versão»): ADR 0017 (inclusive a linha do Laya antes da fase 4: "adiado, para confirmar"), índice das ADRs, `wiki/Roteiro.md`/`Roadmap.md`, `README.md`/`.en.md` (tabela de fases), `.github/CONTRIBUTING.md`/`.en.md`. Notas com "Atualizada" e "Ver também": 0002 (a IA não dá nota; a "nota de encaixe" por IA manual da versão Pages muda, e os esquemas em pydantic não servem ao JavaScript da fase 8, que decide nessa hora), 0007 (e5-small fora, D185.9), 0009 (b12359; sem áudio; baixado da fonte oficial; OpenAI e Gemini pelo compatível; teste ao ligar por par backend-modelo; "ainda não tem código" sai), 0010 (o texto legal novo; a pessoa não instala mais o Claude Code só pelo site, D138.7; sessões esperam o dono), 0011 (passos IA e Perfil na 0.6.0; sem CPF, data de nascimento e projetos, para confirmar), 0014 (serviços e downloads novos; RunPod no Laya só com o dono), 0015 (Laya adiado, para confirmar; o público é modelo de decisão), 0023 (Ferramentas sempre visível; Modelo local removível).
- `duvidas.md`: D185; "Ver também" na D1, D97, D122, D125, D139, D141 e D174.
- **Na T420 e na T440** (fim de cada versão): README pt/en (IA, atalhos, backends, "experimental", o modelo local baixado da fonte oficial, sem Whisper na tabela do pacote offline, privacidade com os pedidos novos, o que só foi provado no CI, a sobra de até 2,7 GB ao desinstalar); `CHANGELOG` (pt/en); `wiki/` (Tecnologias, Como funciona, Perguntas frequentes, pt e en); CONTRIBUTING (como testar a IA sem rede; como rodar o `ia.yml`).
- `registros/padroes.md`: as lições que aparecerem.

## 15. Espera o dono

Nada aqui trava a 0.5.0; o que depende do dono fica de fora até a resposta.

1. **Laya, primeira pergunta** (D141, D185.8): autoriza o gasto estimado (README da T419) ou adia? Até a resposta, a D141 fica "adiada, para confirmar" nas ADR 0015 e 0017.
2. Confirmar a D185 (ou trocar itens), antes da tag da 0.5.0.
3. Sessões (6.2): o texto legal do Claude Code (D185.5), os Termos da OpenAI para o Codex (D185.6), o instalador do Claude Code sem sha256 (D185.18) e os botões Entrar (D139.14).
4. Serviços pagos (D185.27): rodar o `provar_ia.py --backend` com a chave dele (custa centavos) ou deixar a marca "experimental".
5. Medir a velocidade na máquina dele (`uv run python scripts/medir_modelo.py`) e dizer se o 9B entra (D139.11).
6. Portões da 0.5.0 (T422) e da 0.6.0 (T442).

## 16. Decisões (D185)

Escolhas da sessão de 2026-11-17, revistas depois da crítica do mesmo dia, para o dono confirmar; o texto completo, o motivo e o desfazer de cada uma estão na D185 do `duvidas.md`. Resumo: 1 duas versões (0.5.0 fatia, 0.6.0 resto); 2 tarefas desligadas por padrão; 3 contrato com pydantic; 4 backends sem SDK; 5 Claude Code espera o dono; 6 Codex idem; 7 modelo local b12359 + Qwen3.5 da fonte oficial com sha256 e licença; 8 Laya: pergunta ao dono, só o conjunto preparado; 9 e5-small fora; 10 sem Whisper; 11 `encaixe` só extrai, casamento no código, peso 25; 12 laço em `vida`, 20 por rodada, falhas separadas; 13 perfil mínimo na 0.5.0, cortes na 0.6.0; 14 currículo em processo filho, texto não guardado; 15 passos novos na 0.6.0; 16 preparar candidatura sem envio; 17 instalador só com o Modelo local; 18 ferramentas em `<dados>/ferramentas`, fora da varredura; 19 modelo pela memória com folga; 20 telas; 21 teste ao ligar por par; 22 lista permitida por tarefa; 23 nome do modelo digitado fora do Claude; 24 nenhum lote antes da tag `v0.4.0`; 25 documentos na T400; 26 status da fase 4 na T400; 27 serviços pagos "experimental"; 28 custo à vista e teto por dia; 29 prova do modelo cedo, reutilizável pelo `casca.yml`.
