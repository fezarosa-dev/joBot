# Manutenção do CI e dos testes: plano de implementação

> Cada tarefa roda num worktree próprio e passa por revisão de outra pessoa ou sessão, diferente de quem implementou. TDD com vermelho válido: o teste-alvo falha numa asserção do comportamento pedido; erro de import, de coleta ou zero testes não valem como vermelho.

**Objetivo:** deixar a bateria de testes de tela rápida e estável no CI em paralelo (D149), sem esconder falha com repetição automática.

**Regra de medida:** aqui a RAM é curta, então a medida é o CI. Nesta máquina rodam só o arquivo de teste da tarefa e o `ruff`; as medições de tempo vêm de uma branch `lote/manutencao` no Actions. Nenhum teste espera tempo real (`CLAUDE.md` do projeto), e não entra dependência nova (ADR 0021).

**Base:** `dev` atual. Escolhas em aberto, se aparecerem, vão para o `duvidas.md`.

### T292: testes de tela lentos e instáveis
`depende_de: —` · D149

O sintoma: `tests/tela/test_buscar_agora.py::test_form_sem_htmx_chega_numa_pagina_que_ja_mostra_o_andamento` já falhou de vez em quando no CI por setup lento (o `painel` de `tests/tela/conftest.py` sobe um servidor a cada teste e espera até 10 s). A causa de cada teste lento ou instável tem de ser achada e corrigida; repetir o teste até passar não vale.

Outro caso, em 2026-11-16: `tests/navegador/test_navegacao_logada.py::test_cloudflare_que_leva_a_url_com_fragmento_segue` falhou uma vez no CI (a visita voltou `bloqueio` em vez de `Captura`) num lote que só mexia em CSS. Entra na lista para investigar.

**Arquivos:**
- modificar `tests/tela/conftest.py` e os arquivos de `tests/tela/` que a medição apontar;
- modificar `.github/workflows/ci.yml` só para medir (`--durations=25`, depois volta ao valor de hoje);
- modificar `registros/padroes.md` (ou `registros/padroes-tela.md`) com a lição, se sair uma.

- [ ] **Medir antes:** numa branch `lote/manutencao`, rodar `uv run pytest -m tela --durations=25` em cada parte (`JOBOT_PARTE=i/16`) e anotar, no fim desta tarefa, os 25 mais lentos de cada parte (setup, chamada e fim separados), o tempo de cada job `tela` e as falhas da rodada.
- [ ] **Achar a causa** de cada lento: fixture que sobe servidor ou banco a cada teste sem precisar, espera fixa (`time.sleep`, `wait_for_timeout`), `expect` sem condição clara, semeadura repetida, pedido que espera o tempo limite. Uma linha por causa, com `arquivo:linha`.
- [ ] **Teste que falha antes:** para cada causa que dá para provar sem relógio, um teste em `tests/unidade/` ou `tests/tela/` que falha numa asserção (por exemplo, a fixture não pode esperar mais do que o necessário depois de `started`; nenhum teste de tela chama `wait_for_timeout` nem `time.sleep`, conferido por varredura do texto). Causa que só aparece na máquina do CI fica com a medição como prova: o tempo antes e depois.
- [ ] **Ver falhar:** `uv run pytest tests/unidade/<arquivo>.py -q` (e o teste de tela da causa, no CI).
- [ ] **Corrigir a causa**, sem tocar no que não foi medido: fixture por escopo certo, espera por condição (`expect`, `wait_for`) no lugar de tempo, semente menor. Sem plugin de repetição e sem dependência nova.
- [ ] **Ver passar:** o arquivo do teste novo e `uv run ruff check && uv run ruff format --check` aqui; `-m tela` no CI.
- [ ] **Critério de pronto:** 3 rodadas seguidas do CI verdes, sem nenhuma falha de tela, na mesma branch. Anotar no fim desta tarefa os tempos antes e depois (por parte e total da rodada).

**Tempos (preencher ao fechar):**

| Medida | Antes | Depois |
|---|---|---|
| Job `tela` mais lento | | |
| Rodada inteira | | |
| Falhas de tela em 3 rodadas | | |
