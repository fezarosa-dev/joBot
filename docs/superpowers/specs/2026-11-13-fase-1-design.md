# Desenho da fase 1 (Base) do joBot

- **Data:** 2026-11-13
- **Status:** proposta revisada com os fatos conferidos ao vivo em 2026-11-13. A Q6 (termos de uso) foi decidida pelo dono em 2026-11-13. Nada espera resposta dele.
- **Base:** ADRs 0001 a 0017, `duvidas.md`, as respostas do dono nesta sessão (Q1 a Q7 da primeira rodada; Q1 a Q6 da rodada de revisão, resumidas na seção 20.1) e as decisões de 2026-11-13 tomadas depois da revisão (seção 20.2)
- **Apêndice:** [fontes da fase 1](2026-11-13-fase-1-fontes.md) — endereço, método, paginação, campos, limites e termos de cada fonte, a lista das 67 empresas e a cotação PTAX
- **Para quem:** quem vai transformar este desenho em plano de implementação e em código

## Como ler este documento

Este texto diz **o que** a fase 1 entrega e **por quê**. O plano passo a passo sai dele depois. Os fatos de cada fonte ficam no apêndice, para este texto não repetir endereço e campo.

Marcas usadas no texto:

- **(DR-nn)**: decisão do redator. Não está nas ADRs nem nas respostas do dono. O dono pode trocar. A lista completa está na seção 18.
- **[a confirmar]**: ponto que a conferência ao vivo de 2026-11-13 não testou. Só vira código depois de uma captura nossa (seção 9). São poucos e estão listados na seção 20.3.
- **(decisão da sessão)**: decisão tomada pela sessão de trabalho em 2026-11-13, depois da revisão. Não é exigência dos termos de nenhuma fonte (seção 20.2).
- **(Qn)**: resposta do dono na primeira rodada desta sessão.
- **(revisão, Qn)**, **resposta do dono** ou **resolução do dono**: rodada de revisão, resumida nas seções 20.1 e 20.2. No apêndice, Q1 a Q6 são sempre os da revisão.
- **(ADR nnnn)**: decisão já registrada em `docs/decisions/`.
- **(apêndice, n)**: seção do apêndice de fontes.

Não há código aqui, só esboços de interface e de SQL.

---

## 1. Intenção e porquê

A fase 1 constrói a base sobre a qual todas as outras fases vão rodar (ADR 0017):

- o **núcleo comum**: coletores, remoção de duplicadas, leitura de salário, rótulos e encaixe;
- as **fontes públicas**, sem login;
- o **banco** SQLite;
- o **painel** local;
- a **agenda** das buscas.

Por que começar por aqui:

- Sem vagas limpas no banco, nenhuma outra função tem com o que trabalhar. A IA (fase 3), a extensão (fase 4) e o Gmail (fase 5) dependem disso.
- O núcleo precisa nascer separado do painel, porque a versão GitHub Pages (fase 7) reaproveita o núcleo sem o painel (ADR 0002).
- O dono quer testar algo útil já no fim da fase 1: abrir o painel e ver vagas reais, organizadas (Q1).

## 2. Objetivos

No fim da fase 1, no computador do dono (Fedora Silverblue, com o joBot rodando dentro da distrobox `fedora-dev`; seção 12.5):

1. O joBot coleta vagas das fontes públicas das levas A e B (Q2), com coleta educada e saúde por fonte. Fonte sem caminho público, ou fora por termos de uso, fica de fora com o motivo anotado (seção 8.5).
2. As vagas chegam sem duplicadas, com salário lido e convertido para reais quando há cotação, rótulos, ciclo de vida e nota de encaixe por regras (Q5).
3. O painel mostra tudo com as abas, os filtros e o visual da ADR 0008, em português e inglês.
4. A busca roda sozinha a cada 3 horas, com botão "buscar agora", recuperação da execução perdida e sem duas execuções ao mesmo tempo (ADR 0006).
5. Com o segundo plano ligado, o joBot inicia junto com a sessão do usuário, sem janela, e um atalho "joBot" abre o painel. Funciona instalado direto no sistema e dentro de uma distrobox.
6. A primeira execução tem dois passos: preferências de busca e segundo plano (Q4).
7. Uma lista inicial de 67 empresas, já conferidas ao vivo (Q3; apêndice, 7), e uma tela para o dono adicionar, desligar e remover.
8. Toda função tem chave liga/desliga nas configurações (ADR 0001).
9. Tudo feito com TDD, com testes que nunca usam a rede, e com ruff, mypy --strict e pytest passando.
10. Desde o primeiro dia, o banco guarda o texto completo de toda vaga e o histórico das ações da pessoa no painel, para a fase 6 usar depois (seção 7.6).

## 3. Não-objetivos (o que fica para depois)

| Item | Fase | Origem |
|---|---|---|
| Sites com login, Chrome visível, perfil persistente do Playwright, CAPTCHA, horários 9h e 18h | 2 | ADR 0005, 0017 |
| Aviso no computador (notificação do sistema) para CAPTCHA | 2 | ADR 0005 |
| Passo "logins nos sites" da primeira execução | 2 | Q4 |
| Qualquer IA: nota de encaixe por IA, Claude Code, chave da API, modelo local, IA manual | 3 | ADR 0009, 0010, Q5 |
| Passos "escolher a IA", "currículo" e "questionário" da primeira execução; perfil completo, CPF e data de nascimento | 3 | ADR 0011, Q4 |
| Habilidades que a pessoa tem (✓) e que faltam, por vaga (precisa do perfil) | 3 | ADR 0007, 0011 |
| Botão "preparar candidatura" | 3 (a confirmar no desenho da fase 3) | ADR 0001 |
| Cofre de senhas (keyring): a fase 1 não guarda nenhum segredo | 3 | ADR 0014 |
| Rótulo pelo modelo multilingual-e5-small, se algum rótulo ficar abaixo de 90%. A fase 1 só mede e registra | 3, junto com a IA local | ADR 0007 |
| Extensão do navegador | 4 | ADR 0012 |
| Gmail, áudio, passo "Gmail" da primeira execução, resumo no Telegram | 5 | ADR 0011, 0013 |
| Classificador "salvar ou descartar" e treino de modelos. A fase 1 só guarda os dados que eles vão usar (seção 7.6) | 6 | ADR 0015 |
| Versão GitHub Pages, regras rodando em JavaScript, teste em JavaScript dos casos de regras, exportar e importar perfil | 7 | ADR 0002, 0007 |
| Navegador sem janela para ler fonte pública: nenhuma fonte conferida precisa de JavaScript (seção 8.5) | só se uma fonte nova exigir | DR-16 |
| Segundo plano no Windows e no macOS, instaladores, revisão de segurança final | 8 | ADR 0003, 0017 |

Nesta fase também **não** entram: notificação push, ntfy, Telegram, digitar senha e contornar CAPTCHA (restrições do pedido e ADR 0013 e 0014).

## 4. Antiobjetivos (o que faria a fase fracassar, mesmo funcionando)

- **Fonte quebrada que some em silêncio.** Uma fonte muda de formato, devolve zero vagas e aparece como "ok". Pior: o joBot fecha todas as vagas dela.
- **Uma fonte derrubando as outras.** Uma exceção ou um site lento trava a busca inteira.
- **Robô mal-educado.** Pedidos rápidos demais, 429 ignorado, limite da fonte estourado, sites bloqueando o joBot.
- **Contornar bloqueio.** Forjar cabeçalho, fingir ser navegador, passar por login ou CAPTCHA.
- **Crédito faltando.** Vaga de fonte que exige atribuição aparecendo sem "via <fonte>" e sem o link da origem.
- **Dado real no repositório.** O conjunto de ouro, ou qualquer amostra com dado pessoal, indo para o git.
- **Testes que usam a rede**, ou fixtures copiadas de terceiros (ADR 0016).
- **Endereço inventado** virando coletor sem captura própria.
- **Núcleo amarrado ao painel.** Se o núcleo importar FastAPI ou Jinja2, a fase 7 fica impossível.
- **Painel que vaza para fora:** escutar fora de 127.0.0.1, carregar fonte ou script de CDN, mandar qualquer dado de uso.
- **XSS pela descrição da vaga.** O texto vem de terceiros e não é confiável.
- **Lixo repetido:** a mesma vaga várias vezes na lista.
- **Perda de dados ao atualizar.** Mudança de esquema sem migração, ou status da pessoa apagado.
- **Apagar o que a fase 6 precisa.** Vaga fechada ou antiga apagada, texto de vaga cortado, ou ação da pessoa sem registro no histórico (seção 7.6).
- **Painel feio ou confuso para um leigo.** O dono é iniciante; se ele se perde, a fase falhou.
- **Escopo vazando:** puxar login, IA ou Gmail para a fase 1.
- **Entrega pela metade:** "v1", "por enquanto", stub ou valor fixo no lugar do real.

## 5. Critérios de aceite

### 5.1 Verificáveis por teste ou comando

A fase 1 fecha quando **tudo** abaixo vale, com as levas A e B prontas (Q2). Os testes rodam dentro da `fedora-dev`, que é onde o dono roda o joBot.

**Qualidade**

1. `uv run ruff check`, `uv run ruff format --check`, `uv run mypy` (strict) e `uv run pytest` passam sem erro.
2. A suíte inteira passa com a rede bloqueada (a guarda da seção 9.4 está ligada em todos os testes).
3. Todo coletor registrado tem pelo menos uma fixture com o arquivo `.meta.json` da captura (teste automático).
4. Um teste garante que nada em `jobot.nucleo` importa `fastapi`, `starlette`, `jinja2`, `jobot.painel`, `jobot.agenda`, `jobot.banco`, `jobot.sistema` ou `jobot.cli`.
5. O CI do PR `dev` → `main` passa.

**Coleta**

6. Cada fonte das levas A e B tem coletor, chave liga/desliga e linha na tela de saúde. A exceção é a fonte sem caminho público ou fora por termos de uso: ela aparece no apêndice (seção 4) e no `duvidas.md`, com o motivo, e não impede o fechamento da fase.
7. Teste: uma fonte que lança exceção ou estoura o tempo fica "falhou" e as outras terminam normalmente.
8. Teste: resposta 429 com `Retry-After` faz o coletor esperar o tempo pedido (com teto); sem o cabeçalho, espera crescente; tudo com relógio falso.
9. Teste: o user agent sai em todo pedido, e dois pedidos ao mesmo host respeitam o intervalo mínimo.
10. Teste: fonte que devolve zero vagas, depois de três execuções com vagas, fica "parcial" com o motivo "zero inesperado" e não fecha vagas.
11. Teste: resposta 304 deixa o escopo "sem mudança": todas as ocorrências continuam abertas, com `ultima_vista_em` atualizada; nenhuma ganha `sumiu_em`; não dispara "zero inesperado". O `ETag` e o `Last-Modified` ficam guardados por URL. Dois casos a mais: (a) se a gravação do escopo é desfeita (queda no meio), os validadores daquela resposta também não ficam guardados, e o pedido seguinte traz a resposta inteira; (b) escopo sem nenhuma ocorrência aberta (por exemplo, empresa desligada e ligada de novo) não manda pedido condicional, e as vagas dele voltam.
12. Teste: nenhum pedido sai com `Origin`, `Cookie`, `Authorization` ou `Referer`, e nenhum coletor consegue trocar o user agent.
13. Teste: fonte com `intervalo_min` ainda não cumprido, ou com o orçamento de pedidos da execução gasto, fica "no limite" e não fecha vagas. Fonte sem `intervalo_min` roda sempre, inclusive no "buscar agora". O limite próprio de um escopo só segura esse escopo: um 429 da Microsoft deixa só o escopo dela "no limite" até o dia seguinte, e as outras empresas do Eightfold terminam normalmente.
14. Teste: resposta maior que o teto dá erro; o feed do Google e o índice do Common Crawl são lidos em fluxo, com o teto próprio deles.
15. Na semana de testes do dono, cada fonte ligada fica "ok" pelo menos uma vez, na rede real. Fonte que não consegue isso fica listada no `duvidas.md` com o motivo.

**Tratamento**

16. Teste: duas vagas com a mesma URL canônica viram uma linha só, mesmo vindas de escopos ou fontes diferentes; uma vaga que a fonte publica com várias cidades vira uma linha com vários locais. A única chave de duplicata é o hash da URL (ADR 0007).
17. Testes do ciclo de vida cobrem fonte "ok", "parcial" (só fecha depois de 30 dias) e "falhou" (não fecha nada), e a volta de uma vaga que reaparece.
18. O arquivo JSON de casos de salário tem pelo menos 60 casos e todos passam (DR-01). Os casos de rótulo também ficam em JSON. Nenhum teste lê YAML.
19. Testes de câmbio: salário em moeda com cotação ganha o valor em reais; o filtro de salário mínimo usa o valor convertido; sem cotação, a vaga não é ocultada pelo salário; só sai um pedido de cotação por moeda por dia; fim de semana usa o último dia útil.
20. O conjunto de ouro (gabarito) tem 329 vagas reais rotuladas e fica **só no computador**, fora do repositório (seção 10.7). O comando `uv run jobot avaliar-rotulos <caminho>` recebe o caminho do gabarito por argumento e mostra o acerto de cada rótulo. Teste: o comando lê o caminho passado, com um gabarito pequeno de exemplo, feito por nós. O resultado medido de cada rótulo fica registrado no repositório (seção 10.7). Meta: 90% ou mais. Rótulo abaixo da meta **não** impede o fechamento: fica registrado, com o número, e segue para a fase 3.
21. Teste: `git check-ignore dados_locais/` responde que a pasta é ignorada, e nenhuma fixture versionada traz e-mail, telefone ou nome de pessoa (o teste procura os padrões).

**Painel e agenda**

22. Testes de tela (Playwright) cobrem: as oito abas, chips com contagem, filtro na URL, tecla `/`, ordenações, mudança de status, ocultar e trazer de volta, "Algo errado nesta vaga?", configurações com todas as chaves, saúde das fontes, empresas, sites acompanhados, primeira execução, troca de idioma e de tema.
23. Teste de tela: vaga de fonte com crédito obrigatório mostra "via <fonte>" com link para a vaga na origem; na Himalayas, o botão de candidatura usa o link de candidatura dela, sem mudança.
24. Teste de tela: vaga com salário em moeda estrangeira mostra o valor original e, ao lado, menor e mais apagado, a cotação e o valor em reais; sem cotação, só o valor original.
25. Teste de tela: busca sem nenhuma preferência mostra o pedido de preferências, e os Destaques saem por data.
26. Teste: cada chave da seção 13.7, desligada, faz a função parar de rodar e sumir da tela certa. Teste da remoção de empresa (seção 8.6): a empresa removida continua na tabela, com `removida_em` preenchido; não é buscada; e uma nova carga do `empresas.json` não a traz de volta nem cria outra linha.
27. Teste de tela: durante toda a navegação, nenhum pedido sai para fora de `127.0.0.1`.
28. Teste de tela: dá para usar as abas, os chips, a busca e a mudança de status só com o teclado.
29. Teste: os pares de cor do tema claro e do escuro têm contraste de pelo menos 4,5:1 (fórmula da WCAG).
30. Testes da agenda: a próxima busca sai 3 horas depois da última busca completa, seja ela da agenda ou do "buscar agora"; execução perdida roda ao iniciar; segunda busca simultânea é recusada; descoberta e páginas acompanhadas rodando **não** impedem a busca de começar.
31. Testes do segundo plano: o texto do serviço e do atalho sai certo nos dois casos, instalado direto e dentro de uma distrobox (com `distrobox-enter`); a detecção usa `CONTAINER_ID`; dentro da distrobox, os comandos do `systemctl` passam pelo `distrobox-host-exec`.
32. Testes de segurança: Host errado → 400; POST sem token CSRF → 403; cabeçalho CSP presente; descrição com `<script>` aparece como texto; o servidor só aceita `127.0.0.1` como endereço de escuta.

**Guarda para a fase 6** (seção 7.6)

33. Teste: uma vaga que fecha, ou cujo prazo vence, continua no banco com o texto puro e a descrição bruta (o HTML, quando a fonte manda), inteiros. O mesmo vale quando a empresa dela é desligada ou removida, e quando o cache de enriquecimento vence. Três casos a mais: (a) uma segunda coleta que traz a mesma vaga só pela listagem, com a descrição vazia, não apaga a descrição bruta nem o `descricao_texto` que vieram do `detalhar`; (b) `DELETE FROM vaga` dá erro; (c) gravar de novo a mesma vaga mantém o `id` dela e as ocorrências (DR-69).
34. Teste: salvar, ocultar, mostrar, mudar de status e desfazer gravam, cada um, uma linha em `evento`, com a data. `UPDATE` e `DELETE` em `evento` dão erro. Voltar de "candidatei" para "salva" grava um `desfez` e nenhum `salvou`.

**Termos das fontes** (seção 20.2)

35. Teste: o `README.md` traz o aviso de uso pessoal e de responsabilidade pelos termos das fontes ligadas: o joBot é de uso pessoal, roda no computador de cada pessoa, e cada pessoa responde pelos termos das fontes que deixar ligadas.

### 5.2 Roteiro do dono (teste manual no fim da fase)

O dono segue estes passos **dentro da distrobox `fedora-dev`**, que é onde ele roda o joBot. Cada passo diz o que ele deve ver. O navegador é o do sistema de fora (a `fedora-dev` não tem navegador): o joBot manda o sistema abrir o endereço (seção 12.6).

1. No terminal do sistema: `distrobox enter fedora-dev`. Dentro dela, na pasta do projeto: `uv sync` e depois `uv run jobot`. **Deve ver:** o navegador abre o painel em `http://127.0.0.1:<porta>`. Se o navegador não abrir, o terminal mostra o endereço para clicar.
2. Primeira execução, passo 1: preencher cargos, cidades, modalidade, nível, salário mínimo e idiomas. **Deve ver:** um resumo do que foi salvo.
3. Passo 2: ligar o segundo plano. **Deve ver:** "segundo plano ligado", com o aviso de que o joBot roda dentro da `fedora-dev`.
4. Clicar em **Buscar agora**. **Deve ver:** o andamento na tela, e no fim a quantidade de vagas novas.
5. Abrir **Saúde das fontes**. **Deve ver:** cada fonte com ok, sem mudança, parcial, falhou, no limite ou desligada, com a hora e a quantidade de vagas.
6. Abrir **Destaques de hoje**. **Deve ver:** até 10 vagas, nunca duas da mesma empresa, cada uma com ●, ◐ ou ○ e os motivos.
7. Em **Todas**, clicar em dois chips (por exemplo, "Remoto" e "Júnior"). **Deve ver:** a contagem dos chips muda e o endereço da página muda. Copiar o endereço, abrir numa aba nova: **deve ver** o mesmo filtro.
8. Apertar `/`, digitar uma palavra. **Deve ver:** a lista filtrada.
9. Trocar a ordenação (encaixe, mais recentes, prazo, salário). **Deve ver:** a ordem mudar.
10. Abrir uma vaga. **Deve ver:** descrição, salário, rótulos, a faixa de 12 meses e os links "ver na fonte".
11. Abrir uma vaga com salário em dólar ou euro (filtrar por "Remoto" ajuda a achar). **Deve ver:** o salário na moeda original e, ao lado, menor e mais apagado, a cotação do dia e o valor em reais.
12. Abrir uma vaga vinda de Remotive, RemoteOK, Jobicy, Himalayas ou We Work Remotely. **Deve ver:** "via <fonte>" com link, no cartão e no detalhe. O link abre a vaga no site da fonte.
13. Salvar a vaga e depois marcar "candidatei". **Deve ver:** a vaga nas abas **Salvas** e **Candidatei**.
14. Abrir **Ocultas**. **Deve ver:** quantas vagas cada motivo escondeu, e conseguir trazer uma de volta.
15. Numa vaga, clicar em **Algo errado nesta vaga?** e corrigir um rótulo. **Deve ver:** o rótulo corrigido, que continua certo depois de outra busca.
16. Em **Configurações → Fontes**, desligar uma fonte e clicar em **Buscar agora** de novo, sem esperar. **Deve ver:** a busca começa na hora; a fonte desligada aparece como "desligada"; as fontes com intervalo mínimo ainda não cumprido (seção 8.3) aparecem como "no limite", com a hora em que podem rodar de novo.
17. Em **Configurações**, desligar **Conversão de moeda** e abrir a vaga do passo 11. **Deve ver:** só o salário original. Ligar de novo.
18. Em **Empresas**, adicionar uma empresa e clicar em "testar". **Deve ver:** quantas vagas ela tem agora, antes de salvar. Desligar uma empresa da lista inicial: **deve ver** que ela para de ser buscada.
19. Em **Sites acompanhados**, adicionar a página de um programa de trainee. **Deve ver:** a página na aba **Programas**.
20. Trocar o idioma para inglês e o tema para escuro. **Deve ver:** tudo traduzido e escuro, e continua assim depois de recarregar.
21. Reiniciar o computador e entrar na sessão. Sem abrir terminal nem distrobox, clicar no atalho **joBot** no menu de aplicativos. **Deve ver:** o painel abre (a primeira vez pode levar alguns segundos, enquanto a `fedora-dev` sobe); se a última busca tem mais de 3 h, a saúde mostra uma busca de recuperação cerca de 1 minuto depois; senão, mostra a hora da próxima busca.
22. *Retirado em 2026-11-13.* A tela "Conferir rótulos" saiu da fase 1 (DR-67). Os outros passos mantêm o número.
23. No terminal, dentro da `fedora-dev`: `uv run jobot avaliar-rotulos <caminho do gabarito>` (a sessão informa o caminho; seção 10.7). **Deve ver:** o acerto de cada rótulo no gabarito. Fora dela, na pasta do projeto: `git status` **não** mostra nada do gabarito nem de `dados_locais/`.
24. Desligar o segundo plano nas configurações e reiniciar. **Deve ver:** o joBot não inicia sozinho.

O roteiro vem **antes** do PR `dev` → `main`. O dono anota o que estranhou. Cada item vira correção antes do PR, ou entra no `duvidas.md`. O push da `dev` e o PR só saem com o ok do dono.

---

## 6. Arquitetura e pastas

### 6.1 Camadas

```
jobot.nucleo   → puro: modelo, coletores, tratamento, encaixe, regras (reaproveitado na fase 7)
jobot.banco    → SQLite: conexão, migrações, consultas
jobot.agenda   → executa as buscas: liga núcleo + banco, agenda, trava
jobot.sistema  → coisas do sistema operacional: pastas, instância única, segundo plano, abrir navegador
jobot.painel   → FastAPI + Jinja2 + HTMX
jobot.cli      → comandos de terminal
```

Regras de dependência (testadas, critério 4):

- `nucleo` não importa nenhuma outra camada do joBot, nem FastAPI, Starlette ou Jinja2.
- `banco` importa só `nucleo`.
- `agenda` importa `nucleo` e `banco`.
- `painel` importa `nucleo`, `banco`, `agenda` e `sistema`.
- `cli` pode importar tudo.

O núcleo recebe o cliente HTTP e o relógio de fora (injeção). Assim os testes trocam os dois por versões falsas.

### 6.2 Layout de pastas

```
pyproject.toml
uv.lock
src/jobot/
  __init__.py            # versão
  __main__.py            # python -m jobot
  cli.py
  nucleo/
    modelo.py            # VagaColetada, VagaTratada, enums
    texto.py             # normalizar, HTML/Markdown → texto, detectar idioma
    url.py               # URL canônica e hash
    http.py              # protocolo HttpEducado + implementação com httpx
    cambio.py            # cotação PTAX e conversão para reais (seção 10.3)
    relogio.py           # protocolo Relogio (agora em UTC)
    coletores/
      base.py            # contrato Coletor, ResultadoEscopo
      executor.py        # roda coletores isolados, mede saúde
      registro.py        # lista de coletores disponíveis
      github_issues.py remotive.py remoteok.py jobicy.py himalayas.py
      hn_algolia.py wwr.py greenhouse.py lever.py ashby.py smartrecruiters.py gupy.py
      workday.py eightfold.py oracle_hcm.py inhire.py quickin.py recrutei.py
      portais/           # ciee.py solides.py iel.py super_estagios.py cia_de_talentos.py abler.py eureca.py
      carreiras/         # google.py amazon.py (Microsoft e NVIDIA usam eightfold.py)
                         # sem meta.py: a Meta fica fora por decisão do dono (seção 8.5)
      usp.py
      descoberta_cc.py   # Common Crawl
      paginas.py         # acompanhar mudanças em páginas
    tratamento/
      duplicadas.py ciclo_de_vida.py salario.py rotulos.py estagio.py locais.py
    encaixe.py
    destaques.py
    dados/               # arquivos de dados, lidos também pelo JavaScript na fase 7
      rotulos.json encaixe.json rastreamento.json ufs.json empresas.json fontes.json
  banco/
    conexao.py
    migracoes/0001_inicial.sql
    migrar.py
    consultas.py
  agenda/
    execucao.py          # uma execução completa
    agendador.py         # laço de agenda
  sistema/
    pastas.py instancia.py segundo_plano_linux.py abrir.py   # os dois últimos tratam também a distrobox
  painel/
    app.py seguranca.py i18n.py
    rotas/               # vagas.py fontes.py empresas.py sites.py buscas.py configuracoes.py primeira_execucao.py
    i18n/pt.json i18n/en.json
    templates/
    static/
      css/ js/app.js
      vendor/htmx.min.js vendor/htmx.LICENSE
      fontes/Inter*.woff2 fontes/OFL.txt
tests/
  unidade/ integracao/ tela/
  fixtures/<fonte>/<caso>.<ext> + <caso>.meta.json
  casos/salario.json casos/rotulos.json   # casos de regras, feitos por nós, sem dado pessoal
dados_locais/            # no .gitignore: nunca vai para o git. Opcional: para quem preferir
                         # guardar o gabarito dentro da pasta do projeto (seção 10.7)
docs/rotulos-medidos.md  # só os números medidos
scripts/
  capturar.py            # só ele acessa a rede, e só quando alguém roda à mão
  conferir_empresas.py
.github/workflows/ci.yml
.gitignore               # inclui dados_locais/
```

Os nomes dos arquivos são indicação. O construtor pode juntar ou dividir arquivos, desde que as camadas e as regras de dependência valham.

---

## 7. Dados

### 7.1 O que o coletor entrega: `VagaColetada`

Todo coletor devolve vagas neste formato. É o contrato que deixa a lista de fontes crescer sem mexer no núcleo (ADR 0004).

| Campo | Tipo | Obrigatório | Observação |
|---|---|---|---|
| `fonte` | `str` | sim | chave da fonte, ex.: `greenhouse` |
| `escopo` | `str` | sim | identificador da empresa ou do quadro; `""` quando a fonte é uma lista só |
| `id_externo` | `str \| None` | não | id da vaga na fonte |
| `url` | `str` | sim | só `http` ou `https`; é a página da vaga na fonte |
| `url_candidatura` | `str \| None` | não | link de candidatura que a fonte manda usar; guardado e usado **sem nenhuma mudança** (Himalayas: `applicationLink`) |
| `titulo` | `str` | sim | |
| `empresa` | `str` | sim | |
| `descricao` | `str` | não (padrão `""`) | como veio |
| `descricao_formato` | `Literal["html", "markdown", "texto"]` | sim | |
| `locais` | `tuple[str, ...]` | não | texto livre, como veio |
| `modalidade_declarada` | `str \| None` | não | o que a fonte diz, ex.: `remote` |
| `contrato_declarado` | `str \| None` | não | |
| `salario_texto` | `str \| None` | não | |
| `salario_estruturado` | `SalarioBruto \| None` | não | quando a fonte já separa moeda, mínimo, máximo e período |
| `publicada_em` | `datetime \| None` | não | sempre com fuso |
| `prazo` | `date \| None` | não | |
| `inicio` | `date \| None` | não | início do programa, quando houver |
| `etiquetas` | `tuple[str, ...]` | não | tags, departamento, rótulos da issue |

### 7.2 O que o núcleo produz: `VagaTratada`

Tudo de `VagaColetada`, mais:

| Campo | Tipo | Observação |
|---|---|---|
| `url_canonica` / `url_hash` | `str` | seção 10.1 |
| `descricao_texto` | `str` | texto puro, já limpo (seção 14.3) |
| `idioma` | `Literal["pt","en","es","outro"]` | heurística por palavras comuns (DR-02) |
| `locais` | `tuple[Local, ...]` | `cidade`, `uf`, `pais` (ISO 3166-1 alfa-2), cada um opcional |
| `area`, `nivel`, `modalidade`, `contrato` | enums | seção 10.4 |
| `avisos` | `tuple[Aviso, ...]` | ex.: `exige_visto`, `exige_doutorado`, `restrito_a_pais` |
| `salario` | `Salario \| None` | seção 10.3; o valor em reais entra depois, no banco, quando há cotação |
| `requisitos_estagio` | `RequisitosEstagio \| None` | seção 10.5 |
| `versao_regras` | `str` | hash dos arquivos de regras usados |

### 7.3 Esquema SQLite

Conexão: `PRAGMA journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000`. Datas em texto ISO 8601, sempre em UTC. Dinheiro em inteiro de centavos, na moeda original. A exceção são os valores convertidos para reais (colunas `_brl`): reais inteiros, arredondados para o real mais próximo (seção 10.3). Cotação em texto decimal, lida com `decimal.Decimal`. Listas em texto JSON. Sem ORM: `sqlite3` da biblioteca padrão (DR-03).

```sql
CREATE TABLE fonte (
  chave         TEXT PRIMARY KEY,                 -- 'greenhouse', 'remotive'...
  leva          TEXT NOT NULL CHECK (leva IN ('A','B')),
  ligada        INTEGER NOT NULL DEFAULT 1,
  intervalo_min INTEGER                           -- NULL = sem intervalo mínimo. Preenchido quando os termos ou os limites da fonte exigem, ou com um intervalo prático (seção 8.3)
);

CREATE TABLE empresa (
  id            INTEGER PRIMARY KEY,
  nome          TEXT NOT NULL,
  area          TEXT,
  pais          TEXT,                                    -- país da empresa, ISO 3166-1 alfa-2 (vem do empresas.json)
  fonte         TEXT NOT NULL REFERENCES fonte(chave),   -- o ATS
  identificador TEXT NOT NULL,
  parametros    TEXT NOT NULL DEFAULT '{}',              -- JSON: o que o ATS pede além do identificador (seção 8.6)
  ativa         INTEGER NOT NULL DEFAULT 1,
  removida_em   TEXT,                                    -- NULL = não removida. Remover marca a linha, não apaga (seção 8.6)
  origem        TEXT NOT NULL CHECK (origem IN ('lista_inicial','pessoa','descoberta')),
  conferida_em  TEXT,
  UNIQUE (fonte, identificador)
);

CREATE TABLE empresa_sugerida (                    -- vinda do Common Crawl
  id            INTEGER PRIMARY KEY,
  fonte         TEXT NOT NULL REFERENCES fonte(chave),
  identificador TEXT NOT NULL,
  url_exemplo   TEXT NOT NULL,
  descoberta_em TEXT NOT NULL,
  estado        TEXT NOT NULL DEFAULT 'pendente' CHECK (estado IN ('pendente','aprovada','descartada')),
  UNIQUE (fonte, identificador)
);

CREATE TABLE execucao (
  id            INTEGER PRIMARY KEY,
  tipo          TEXT NOT NULL CHECK (tipo IN ('busca','descoberta','paginas')),
  motivo        TEXT NOT NULL CHECK (motivo IN ('agenda','agora','recuperacao')),
  iniciada_em   TEXT NOT NULL,
  batimento_em  TEXT NOT NULL,                     -- atualizado a cada 30 s
  terminada_em  TEXT,
  estado        TEXT NOT NULL CHECK (estado IN ('rodando','concluida','interrompida'))
);
-- no máximo uma execução rodando de cada tipo, garantido pelo próprio banco.
-- Descoberta e páginas acompanhadas nunca seguram a busca (seção 12.3).
CREATE UNIQUE INDEX execucao_uma_por_tipo ON execucao(tipo) WHERE estado = 'rodando';

CREATE TABLE saude (
  execucao_id   INTEGER NOT NULL REFERENCES execucao(id) ON DELETE CASCADE,
  fonte         TEXT NOT NULL REFERENCES fonte(chave),
  escopo        TEXT NOT NULL DEFAULT '',
  estado        TEXT NOT NULL CHECK (estado IN ('ok','sem_mudanca','parcial','falhou','desligada','no_limite')),
  vagas         INTEGER NOT NULL DEFAULT 0,
  pedidos       INTEGER NOT NULL DEFAULT 0,
  duracao_ms    INTEGER NOT NULL DEFAULT 0,
  motivo        TEXT,                              -- chave de i18n + detalhe curto
  PRIMARY KEY (execucao_id, fonte, escopo)
);

CREATE TABLE vaga (
  id                 INTEGER PRIMARY KEY,
  url_hash           TEXT NOT NULL UNIQUE,         -- única chave de duplicata (ADR 0007)
  titulo             TEXT NOT NULL,
  empresa            TEXT NOT NULL,
  descricao_texto    TEXT NOT NULL DEFAULT '',
  url                TEXT NOT NULL,                -- URL canônica
  idioma             TEXT,
  area TEXT, nivel TEXT, modalidade TEXT, contrato TEXT,
  avisos             TEXT NOT NULL DEFAULT '[]',
  sal_moeda TEXT, sal_min INTEGER, sal_max INTEGER, sal_periodo TEXT,
  sal_mensal_min INTEGER,                          -- na moeda original
  sal_mensal_min_brl INTEGER,                      -- em reais inteiros (não centavos), para ordenar e filtrar; NULL sem cotação
  sal_mensal_max_brl INTEGER,                      -- o máximo mensal, em reais inteiros; NULL sem cotação ou sem máximo
                                                   -- vaga em BRL: os dois valem centavos ÷ 100, arredondado, sem cotação
                                                   -- e mesmo com a conversão desligada (seção 10.3)
  sal_cotacao_data TEXT,                           -- dia da cotação usada; NULL na vaga em BRL
  sal_plausivel INTEGER, sal_texto TEXT,
  beneficios         TEXT NOT NULL DEFAULT '[]',
  requisitos_estagio TEXT,
  publicada_em TEXT, prazo TEXT, inicio TEXT,
  primeira_vista_em  TEXT NOT NULL,
  ultima_vista_em    TEXT NOT NULL,
  fechada_em         TEXT,
  status             TEXT NOT NULL DEFAULT 'nova'
                     CHECK (status IN ('nova','salva','candidatei','entrevista','recusada','oferta')),
  status_em          TEXT,
  oculta_manual      INTEGER NOT NULL DEFAULT 0
                     CHECK (oculta_manual IN (-1,0,1)),  -- 0 regras, 1 à mão, -1 mostrar mesmo assim (DP2)
  versao_regras      TEXT NOT NULL
);
CREATE INDEX vaga_lista ON vaga(fechada_em, oculta_manual, status);
CREATE INDEX vaga_primeira_vista ON vaga(primeira_vista_em);
CREATE INDEX vaga_prazo ON vaga(prazo);
CREATE INDEX vaga_empresa ON vaga(empresa);
-- mais um gatilho BEFORE DELETE ON vaga que recusa a remoção (RAISE(ABORT)), igual aos de evento:
-- vaga nunca é apagada (seção 7.6)
-- gravar de novo é sempre INSERT ... ON CONFLICT(url_hash) DO UPDATE; nunca INSERT OR REPLACE nem REPLACE (DR-69)

CREATE TABLE local_vaga (
  vaga_id  INTEGER NOT NULL REFERENCES vaga(id) ON DELETE CASCADE,
  cidade TEXT, uf TEXT, pais TEXT
);
CREATE INDEX local_vaga_uf ON local_vaga(uf);

CREATE TABLE ocorrencia (                          -- cada vez que uma fonte mostra a vaga
  id               INTEGER PRIMARY KEY,
  vaga_id          INTEGER NOT NULL REFERENCES vaga(id) ON DELETE CASCADE,
  fonte            TEXT NOT NULL REFERENCES fonte(chave),
  escopo           TEXT NOT NULL DEFAULT '',
  id_externo       TEXT,
  url              TEXT NOT NULL,                  -- como a fonte mandou
  coletada         TEXT NOT NULL,                  -- VagaColetada em JSON (inclui url_candidatura), para reprocessar sem baixar de novo
  primeira_vista_em TEXT NOT NULL,
  ultima_vista_em  TEXT NOT NULL,
  sumiu_em         TEXT,
  UNIQUE (vaga_id, fonte, escopo)                  -- a mesma URL pode aparecer em mais de um escopo ou fonte
);
CREATE INDEX ocorrencia_escopo ON ocorrencia(fonte, escopo, ultima_vista_em);
CREATE INDEX ocorrencia_vaga ON ocorrencia(vaga_id);

CREATE TABLE busca (                               -- buscas salvas (ADR 0001)
  id INTEGER PRIMARY KEY,
  nome TEXT NOT NULL,
  ativa INTEGER NOT NULL DEFAULT 1,
  cargos TEXT NOT NULL DEFAULT '[]',               -- palavras-chave
  cidades TEXT NOT NULL DEFAULT '[]',              -- [{cidade, uf, pais}]
  modalidades TEXT NOT NULL DEFAULT '[]',
  niveis TEXT NOT NULL DEFAULT '[]',
  salario_min INTEGER, salario_moeda TEXT,         -- mensal, em centavos de salario_moeda
  idiomas TEXT NOT NULL DEFAULT '[]',
  regras_ocultar TEXT NOT NULL DEFAULT '{}',       -- quais regras de ocultar estão ligadas
  criada_em TEXT NOT NULL
);

CREATE TABLE encaixe (                             -- calculado por busca
  busca_id INTEGER NOT NULL REFERENCES busca(id) ON DELETE CASCADE,
  vaga_id  INTEGER NOT NULL REFERENCES vaga(id) ON DELETE CASCADE,
  nota     INTEGER,                                -- 0 a 100; NULL quando a busca não tem nenhum critério (seção 11.1)
  nivel    TEXT CHECK (nivel IN ('bom','medio','fraco')),
  motivos  TEXT NOT NULL,                          -- [{chave, params}]
  oculta_motivo TEXT,                              -- regra que escondeu; NULL se visível
  PRIMARY KEY (busca_id, vaga_id)
);
CREATE INDEX encaixe_ordem ON encaixe(busca_id, oculta_motivo, nota DESC);

CREATE TABLE correcao (                            -- "Algo errado nesta vaga?"
  id INTEGER PRIMARY KEY,
  vaga_id INTEGER NOT NULL REFERENCES vaga(id) ON DELETE CASCADE,
  campo TEXT NOT NULL,                             -- 'area','nivel','modalidade','contrato','uf','salario','fechada','outro'
  valor_antigo TEXT, valor_novo TEXT, comentario TEXT,
  criada_em TEXT NOT NULL
);

CREATE TABLE evento (                              -- histórico das ações da pessoa no painel; só de acréscimo (seção 7.6)
  id        INTEGER PRIMARY KEY,
  vaga_id   INTEGER NOT NULL REFERENCES vaga(id),  -- sem CASCADE: vaga nunca é apagada
  acao      TEXT NOT NULL CHECK (acao IN ('salvou','ocultou','mostrou','mudou_status','desfez')),
  de        TEXT,                                  -- status anterior, quando a ação mexe no status
  para      TEXT,                                  -- status novo, quando a ação mexe no status
  criado_em TEXT NOT NULL
);
-- mais dois gatilhos que recusam UPDATE e DELETE em evento (RAISE(ABORT))

CREATE TABLE cotacao (                             -- PTAX de fechamento, uma linha por moeda e dia
  moeda      TEXT NOT NULL,                        -- 'USD', 'EUR'...
  data       TEXT NOT NULL,                        -- dia do boletim
  venda      TEXT NOT NULL,                        -- reais por 1 unidade da moeda, em decimal
  buscada_em TEXT NOT NULL,
  PRIMARY KEY (moeda, data)
);

CREATE TABLE cache_http (                          -- validadores para pedido condicional (seção 8.2)
  url           TEXT PRIMARY KEY,
  etag          TEXT,
  last_modified TEXT,
  visto_em      TEXT NOT NULL
);

CREATE TABLE enriquecimento (                      -- cache de 30 dias
  url_hash TEXT PRIMARY KEY,
  buscado_em TEXT NOT NULL,
  conteudo TEXT NOT NULL                           -- vazio quando o detalhe não trouxe título ou empresa (DR-70)
);

CREATE TABLE pagina_acompanhada (
  id INTEGER PRIMARY KEY,
  url TEXT NOT NULL UNIQUE,
  nome TEXT NOT NULL,
  ativa INTEGER NOT NULL DEFAULT 1,
  texto TEXT, hash_texto TEXT,
  verificada_em TEXT, mudou_em TEXT,
  estado TEXT                                      -- ok, falhou
);
CREATE TABLE mudanca_pagina (
  id INTEGER PRIMARY KEY,
  pagina_id INTEGER NOT NULL REFERENCES pagina_acompanhada(id) ON DELETE CASCADE,
  detectada_em TEXT NOT NULL,
  diferenca TEXT NOT NULL,                         -- saída do difflib
  vista INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE config (chave TEXT PRIMARY KEY, valor TEXT NOT NULL);   -- valor em JSON

CREATE VIRTUAL TABLE vaga_fts USING fts5(
  titulo, empresa, descricao_texto,
  content='vaga', content_rowid='id',
  tokenize='unicode61 remove_diacritics 2'
);
-- mais os gatilhos de INSERT e UPDATE que mantêm vaga_fts igual a vaga.
-- Não há gatilho de DELETE: vaga nunca é apagada. A tabela e os dois gatilhos só são criados quando há FTS5
```

Chaves de `config` na fase 1: `idioma`, `tema`, `destaques_n`, `primeira_execucao_concluida`, `versao_regras`, e as chaves liga/desliga `segundo_plano`, `descoberta_cc_ligada`, `paginas_ligadas`, `enriquecimento_ligado`, `destaques_ligados`, `conversao_moeda_ligada` e `regras_ocultar_ligadas`. As fontes têm a chave em `fonte.ligada`, e as empresas em `empresa.ativa` (lista completa na seção 13.7).

Notas:

- **Status é da vaga, não da busca.** Encaixe e ocultação são por busca (DR-04).
- **Uma vaga, várias ocorrências.** A vaga é a URL canônica. Cada fonte e escopo que mostra essa URL tem a sua ocorrência. A vaga fecha quando todas as ocorrências sumiram (seção 10.2).
- **Crédito da fonte.** O "via <fonte>" sai das ocorrências abertas da vaga. O link de candidatura fica dentro de `ocorrencia.coletada`.
- **Correção ganha da regra.** Ao reprocessar, as correções da tabela `correcao` são aplicadas por cima do resultado das regras.
- **Reprocessar.** Quando `versao_regras` muda (arquivo de regras editado), o app reaplica as regras às vagas abertas, a partir de `ocorrencia.coletada`, sem baixar nada.
- **Nada é apagado.** Vaga fechada ou antiga fica no banco, com o texto completo. Um gatilho recusa `DELETE` em `vaga`. Cada ação da pessoa no painel vira uma linha em `evento` (seção 7.6).
- **Regravar sem `REPLACE`.** Vaga, ocorrência e empresa são gravadas sempre com `INSERT ... ON CONFLICT(...) DO UPDATE`. Nenhuma tabela com filhos usa `INSERT OR REPLACE` nem `REPLACE`: eles apagam a linha antiga e criam outra, com outro `id` (seção 7.6; DR-69).
- **FTS5.** Ao iniciar, o app confere se o SQLite tem FTS5. Se não tiver, a busca usa `LIKE` e o painel funciona igual, só mais lento (DR-05). O `vaga_fts` e os gatilhos de `INSERT` e `UPDATE` dele só são criados quando há FTS5. Ele não tem gatilho de `DELETE`: seria código morto, porque vaga nunca é apagada.

### 7.4 Migrações

- Arquivos SQL numerados em `src/jobot/banco/migracoes/` (`0001_inicial.sql`, `0002_...sql`).
- A versão atual fica em `PRAGMA user_version`.
- Ao iniciar, o app aplica as que faltam, em ordem, cada uma numa transação.
- **A migração roda com as chaves estrangeiras desligadas.** O `migrar` roda `PRAGMA foreign_keys=OFF` antes do `BEGIN`, aplica a migração, roda `PRAGMA foreign_key_check` antes do `COMMIT` e liga as chaves de novo depois. Se a conferência devolver alguma linha, a migração é desfeita e o app para com erro.
  - Por quê: para mudar uma restrição, o SQLite pede reconstruir a tabela. O `DROP TABLE` faz um `DELETE` implícito: nenhum gatilho dispara, mas as ações de chave estrangeira rodam. Reconstruir `vaga` apagaria em cascata ocorrências, locais, encaixe e correções. É a mesma armadilha do `REPLACE` (DR-69).
  - O `PRAGMA foreign_keys` não muda dentro de uma transação. Por isso ele vem antes do `BEGIN`.
- Antes de migrar, copia o banco com a API de backup do `sqlite3` para `jobot.db.antes-v<N>`. Guarda só as 3 cópias mais recentes (DR-06).
- Migração aplicada nunca é editada. Mudança nova = arquivo novo.
- Testes: banco vazio → todas as migrações → esquema esperado; banco na versão N com dados → N+1 sem perder dados.

### 7.5 Pasta de dados e permissões (ADR 0014)

| Sistema | Pasta |
|---|---|
| Linux | `$XDG_DATA_HOME/jobot`, ou `~/.local/share/jobot` se a variável não existir |
| Windows (fase 8) | `%LOCALAPPDATA%\joBot` (não é a pasta que sincroniza com nuvem) |
| macOS (fase 8) | `~/Library/Application Support/joBot` |

- Calculada com a biblioteca padrão, sem `platformdirs` (DR-07).
- Variável `JOBOT_DADOS` troca a pasta (usada nos testes).
- No Linux: pasta com modo `0700`, arquivos com `0600`, `umask 0o077` no início do processo. Se a pasta existir com permissão mais aberta, o app corrige e registra no log.
- Conteúdo: `jobot.db`, cópias de migração, `jobot.lock`, `logs/` (com rotação, `RotatingFileHandler`).
- Logs não trazem preferências da pessoa (cidades, salário).
- A fase 1 não guarda nenhum segredo. O keyring entra quando aparecer o primeiro segredo (fase 3).
- A tela **Configurações → Privacidade** recomenda ligar a criptografia de disco (LUKS, BitLocker ou FileVault), como pede a ADR 0014.

### 7.6 O que a fase 1 guarda para a fase 6

A fase 6 treina modelos (ADR 0015). Ela precisa de dados que só existem se forem guardados desde o primeiro dia (decisão de 2026-11-13; seção 20.2). A fase 1 não treina nada: só guarda.

**Texto completo de toda vaga**

- O texto puro fica em `vaga.descricao_texto`.
- A descrição bruta, como a fonte mandou (o HTML, quando houver), fica em `ocorrencia.coletada`, nos campos `descricao` e `descricao_formato`.
- Os dois ficam inteiros, sem corte. Não há coluna nova para isso: o esquema já guardava os dois.
- Quando a descrição vem da página de detalhe (seção 10.6), a vaga completa é gravada em `ocorrencia.coletada`. O cache de 30 dias só evita baixar de novo: quando ele vence, o texto continua na ocorrência.
- **Coleta repetida não apaga a descrição** (DR-69). O `detalhar` só roda para vagas novas (seção 10.6). Na busca seguinte, a mesma vaga chega só pela listagem, com a descrição vazia. Ao gravar de novo a ocorrência, os campos `descricao` e `descricao_formato` que vieram do `detalhar` ficam como estão, e o `vaga.descricao_texto` também. Só uma descrição não vazia substitui a anterior. Os outros campos da ocorrência são atualizados normalmente.

**Nada é apagado**

- Vaga fechada, vencida ou antiga continua no banco, com as ocorrências dela. O ciclo de vida marca (`sumiu_em`, `fechada_em`); não apaga (seção 10.2).
- Desligar ou remover uma empresa, ou desligar uma fonte, também não apaga vaga. A empresa removida também não é apagada: a linha dela fica marcada (seção 8.6).
- Um gatilho do banco recusa `DELETE` em `vaga` (`RAISE(ABORT)`), igual aos de `evento` (DR-69). O esquema ainda tem `ON DELETE CASCADE` em tabelas que apontam para `vaga`. Com o gatilho, a remoção dá erro antes de qualquer cascata.
- **Regravar nunca usa `REPLACE`** (DR-69). Vaga, ocorrência e empresa são gravadas sempre com `INSERT ... ON CONFLICT(...) DO UPDATE`. O `INSERT OR REPLACE` e o `REPLACE` apagam a linha antiga e criam outra. Com `recursive_triggers` desligado, que é o padrão do SQLite, essa remoção **não** dispara o gatilho de `DELETE`, e as cascatas rodam: a vaga trocaria de `id` e perderia ocorrências, locais, encaixe e correções. Teste: gravar de novo a mesma vaga mantém o `id` e as ocorrências.
- Não há limpeza automática na fase 1.

**Histórico das ações da pessoa**

Tabela `evento`, só de acréscimo: cada ação no painel vira uma linha nova, com a data. O app nunca altera nem apaga linha dela, e dois gatilhos do banco recusam `UPDATE` e `DELETE` (DR-66).

| `acao` | Quando é gravada |
|---|---|
| `salvou` | o status foi de "nova" para "salva". Só esse caso |
| `mudou_status` | qualquer outra mudança de status para a frente; `de` e `para` dizem qual |
| `ocultou` | botão "ocultar" na vaga. No painel da fase 1, descartar uma vaga é ocultá-la à mão: é o mesmo gesto |
| `mostrou` | botão "mostrar mesmo assim" numa vaga oculta por regra |
| `desfez` | o status voltou para o anterior (`de` e `para` dizem qual), inclusive de "candidatei" para "salva"; ou a pessoa trouxe de volta uma vaga que tinha ocultado à mão |

- **Um gesto, um evento.** A volta vale primeiro: toda volta para o status anterior é `desfez`, nunca `salvou`. O `salvou` vale só para a ida de "nova" para "salva". Assim a fase 6 não conta o mesmo gesto de dois jeitos (DR-66).
- O evento é gravado na mesma transação da mudança.
- `vaga.status`, `vaga.status_em` e `vaga.oculta_manual` continuam a dizer o estado de agora. A tabela `evento` diz como se chegou nele.
- As correções de "Algo errado nesta vaga?" já têm histórico próprio, com data, na tabela `correcao`. Não são repetidas em `evento`.
- O histórico não aparece em nenhuma tela na fase 1.
- **É dado pessoal.** Fica só no computador da pessoa, dentro do `jobot.db`. Nunca vai para fora, nem para treino de modelo público (ADR 0015).

---

## 8. Coleta

### 8.1 Contrato do coletor

```python
class Coletor(Protocol):
    chave: str                              # 'greenhouse'
    nome: str                               # nome mostrado no painel e no "via <fonte>": 'Greenhouse'
    leva: Literal["A", "B"]
    hosts: tuple[str, ...]                  # hosts que ele acessa (para o intervalo por host)
    credito_obrigatorio: bool               # os termos pedem crédito e link de volta (seção 8.2)
    intervalo_min: int | None               # minutos entre execuções; None = sem intervalo mínimo
    max_pedidos: int | None                 # orçamento de pedidos por execução; None = sem teto
    espera_s: float                         # espera entre pedidos no mesmo host (padrão 1.0)
    por_escopo: Mapping[str, LimiteEscopo]  # limites próprios de um escopo; vazio na maioria das fontes

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]: ...
    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo: ...
    async def detalhar(self, item: VagaColetada | UrlListada, http: HttpEducado) -> VagaColetada | None: ...
        # opcional: para fontes cuja listagem não traz a descrição, e para as de sitemap (UrlListada)
    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]: ...
        # opcional: descobre os parâmetros fixos de uma empresa (seção 8.6). Roda no "testar" do painel
        # e no conferir_empresas.py, nunca na coleta normal

@dataclass(frozen=True)
class LimiteEscopo:
    intervalo_min: int | None = None        # minutos entre coletas desse escopo; None = o da fonte
    espera_s: float | None = None           # espera entre pedidos desse escopo; None = a da fonte
    para_no_429: bool = False               # o primeiro 429 encerra o escopo, sem nova tentativa

@dataclass(frozen=True)
class ContextoColeta:
    empresas: Sequence[Empresa]             # as ativas e não removidas desse ATS, com identificador e parametros
    termos: Sequence[str]                   # cargos das buscas ativas (para fontes que buscam por termo)
    paises: Sequence[str]                   # países das buscas ativas (para fontes que filtram por país)

@dataclass(frozen=True)
class UrlListada:                           # item de fonte que só lista endereços (sitemap); DR-70
    url: str
    atualizada_em: datetime | None          # a data que o sitemap traz (<lastmod>), com fuso

@dataclass(frozen=True)
class ResultadoEscopo:
    vagas: tuple[VagaColetada | UrlListada, ...]   # UrlListada só nas fontes de sitemap
    estado: Literal["ok", "sem_mudanca", "parcial", "falhou", "no_limite"]
    motivo: str | None                      # chave de i18n, ex.: 'saude.formato_mudou'
    pedidos: int
```

Os valores de `intervalo_min`, `max_pedidos`, `espera_s` e `por_escopo` de cada fonte ficam em `nucleo/dados/fontes.json` e vêm do apêndice. O `intervalo_min` da fonte é copiado para a tabela `fonte`. Os valores de `por_escopo` são lidos direto do arquivo.

Significado do estado (ADR 0004):

- **ok**: a listagem do escopo veio inteira. Só nesse caso as vagas que sumiram podem fechar na hora.
- **sem_mudanca**: a fonte respondeu 304 em toda a listagem do escopo. Nada mudou desde a última vez: todas as ocorrências abertas do escopo ganham `ultima_vista_em` de agora, nenhuma é marcada como sumida, e o zero de vagas novas não conta como "zero inesperado". Na saúde da fonte, vale como "ok".
- **parcial**: veio uma parte (página falhou, item fora do formato, zero inesperado).
- **no_limite**: o escopo não rodou, ou parou no meio, para respeitar um limite real da fonte: `intervalo_min` ainda não cumprido (da fonte ou do escopo), orçamento de pedidos gasto, 429 em escopo com `para_no_429`, ou a fonte avisou que a cota acabou (por exemplo, `X-RateLimit-Remaining: 0` no GitHub). Nada fecha. O painel mostra quando a fonte pode rodar de novo.
- **falhou**: nada aproveitável.

Regras:

- Item sem campo obrigatório é pulado e conta para o estado "parcial", com o número de itens pulados no motivo (DR-08).
- **Fonte de sitemap (DR-70):** Abler e Super Estágios listam só o endereço e a data de cada vaga. O `coletar` delas devolve `UrlListada`, não `VagaColetada`, e devolve **todas** as URLs do sitemap, cada uma com a sua data. A `VagaColetada` continua a exigir `titulo` e `empresa`. O executor trata assim:
  - URL que já tem ocorrência dessa fonte no banco conta como vista no ciclo de vida (seção 10.2), sem pedido novo, com qualquer data. Assim a vaga antiga que continua no sitemap não fecha.
  - O filtro de 30 dias vale só para URL nova e é do executor, não do coletor: URL nova com data de mais de 30 dias não vai ao `detalhar`. URL nova sem data vai, por último.
  - URL nova vai para o `detalhar`, dentro do orçamento de enriquecimento (50 por fonte; seção 10.6), as mais recentes primeiro.
  - A vaga só é gravada se o detalhe trouxer título e empresa.
  - Detalhe sem título ou sem empresa: a tentativa fica no cache `enriquecimento`, com `conteudo` vazio, e a URL não volta ao `detalhar` por 30 dias. Isso **não** muda o estado do escopo: entra só no motivo `saude.sem_detalhe_n`, com a contagem.
  - O que não couber no orçamento espera a próxima execução.
  - Para o "zero inesperado", conta o número de URLs listadas.
- O executor (`coletores/executor.py`) roda cada escopo dentro de `asyncio.timeout` (5 minutos por escopo) e captura **qualquer** exceção. Exceção vira "falhou" com o tipo do erro. Nada sobe para fora (falha isolada).
- Até 4 hosts diferentes ao mesmo tempo; no mesmo host, um pedido de cada vez (DR-09).
- **Zero inesperado:** se o escopo devolve zero vagas e as três últimas execuções "ok" desse escopo trouxeram vagas, o estado vira "parcial" com o motivo `saude.zero_inesperado` (DR-10).
- Fonte desligada não roda e aparece como "desligada".
- **Escopo paginado e 304:** o escopo só é "sem_mudanca" se **todas** as páginas da listagem responderem 304. Se uma responder 200, o coletor refaz o escopo inteiro sem pedido condicional (DR-12).
- **Orçamento de pedidos:** fonte com `max_pedidos` atende primeiro os escopos coletados há mais tempo. O que não couber fica "no_limite" e entra na frente na próxima execução (DR-52).
- **Limite próprio de um escopo (`por_escopo`):** quando um coletor atende vários sites e só um deles tem limite, o limite fica nesse escopo, não na fonte. Na fase 1 há um caso: no Eightfold, o escopo da Microsoft (`apply.careers.microsoft.com`) tem `intervalo_min` 1440, `espera_s` 5 e `para_no_429`. Os outros escopos do Eightfold seguem os valores da fonte e rodam a cada busca. Com `para_no_429`, o primeiro 429 encerra só aquele escopo, sem nova tentativa: ele fica "no_limite" até cumprir o intervalo, e os outros continuam (DR-64).
- **Como o intervalo é contado:** o `intervalo_min`, da fonte ou do escopo, conta do início da última execução em que a fonte ou o escopo fez pelo menos um pedido (`saude.pedidos > 0`). Nada novo é guardado no banco para isso.
- **Escopo que deixou de existir** (empresa removida ou desligada, termo tirado da busca): as ocorrências dele são marcadas como sumidas na execução seguinte.
- **Escopo sem ocorrência aberta** (primeira coleta, ou escopo que voltou depois de removido ou desligado): o executor desliga o pedido condicional desse escopo, e o `HttpEducado` ignora o `condicional`. Sem isso, um 304 deixaria fechadas vagas que continuam na fonte. O custo é uma resposta inteira nos escopos vazios.
- **País:** fonte mundial com filtro de país (SmartRecruiters, Workday, Eightfold, Oracle HCM, Amazon) pede só os países das buscas ativas (DR-53).

### 8.2 Coleta educada: `HttpEducado`

```python
class HttpEducado(Protocol):
    async def pedir(
        self, metodo: Literal["GET", "POST"], url: str, *,
        params: Mapping[str, str] | None = None,
        cabecalhos: Mapping[str, str] | None = None,   # só os da lista permitida
        corpo_json: object | None = None,
        condicional: bool = False,                      # envia If-None-Match / If-Modified-Since
        teto_bytes: int | None = None,                  # só para as exceções declaradas
    ) -> Resposta: ...
    def ler_em_fluxo(self, url: str, *, teto_bytes: int,
                     cabecalhos: Mapping[str, str] | None = None) -> AsyncIterator[bytes]: ...

@dataclass(frozen=True)
class Resposta:
    status: int                             # 200, 202, 206 ou 304
    texto: str
    cabecalhos: Mapping[str, str]
    def json(self) -> object: ...
```

Implementação única com `httpx.AsyncClient`. Todo coletor, a descoberta, as páginas acompanhadas e o câmbio usam só ela; ninguém cria cliente próprio. O que a conferência ao vivo mostrou que ela precisa aceitar: `POST` com corpo JSON (Workday, Recrutei, Cia de Talentos), resposta 202 com JSON (Recrutei), cabeçalho `X-Tenant` (InHire), pedido de faixa com `Range` e resposta 206 (Common Crawl) e leitura em fluxo (feed do Google, índice do Common Crawl).

| Regra | Valor | Origem |
|---|---|---|
| User agent | `joBot/<versão> (+https://github.com/fezarosa-dev/joBot)`, fixo. Nenhum coletor consegue trocar | ADR 0004; formato DR-11 |
| Cabeçalhos extras | só `Accept`, `Accept-Language`, `Content-Type`, `Range` e `X-Tenant`. Nunca `Origin`, `Cookie`, `Authorization` nem `Referer`. Outro nome dá erro | DR-51 |
| Bloqueio | 401, 403, página de login, CAPTCHA ou desafio anti-robô = a fonte falhou, com motivo claro. O joBot **nunca** contorna | ADR 0004 |
| Intervalo mínimo por host | 1 s entre pedidos; mais quando a fonte pede (`espera_s`) | DR-11 |
| Tempo limite | conexão 10 s, leitura 30 s | DR-11 |
| Tamanho máximo da resposta | 5 MB; acima disso, erro. Exceções declaradas, lidas em fluxo: feed do Google (32 MB) e `cluster.idx` do Common Crawl (128 MB) | DR-11; apêndice, 3.4 e 5 |
| 429 ou 503 com `Retry-After` | espera o tempo pedido (segundos ou data HTTP), até 10 min; acima de 10 min, desiste do escopo e marca "parcial" | ADR 0004; teto DR-11 |
| 429 ou 503 sem `Retry-After` | espera 30 s, 60 s, 120 s; depois desiste ("parcial") | DR-11 |
| Erro de rede ou 5xx | até 2 novas tentativas, com espera crescente | DR-11 |
| Pedidos condicionais | lê `ETag` e `Last-Modified` por URL na tabela `cache_http`; com `condicional=True`, envia `If-None-Match` / `If-Modified-Since`. 304 = "sem mudança" (seção 8.1). Os validadores novos são gravados junto com as ocorrências do escopo, na mesma transação (seção 12.4). Escopo sem ocorrência aberta não manda pedido condicional | resolução do dono; detalhe DR-12 |
| Compressão | aceita gzip | |
| Redirecionamento | segue até 5, só para `http`/`https` | |

- **`robots.txt` não bloqueia a coleta** (resposta do dono; ADR 0004). O joBot não lê nem consulta `robots.txt`. O que vale é a coleta educada desta tabela, os limites documentados de cada fonte e a regra de nunca contornar bloqueio.
- **Limites da fonte.** Os termos e os limites de cada fonte já foram lidos (apêndice). Tem `intervalo_min` a fonte que exige intervalo mínimo e a que ganhou um intervalo prático (decisão da sessão; seção 8.3). As outras ficam com `NULL` e rodam a cada busca, inclusive no "buscar agora".
- **Atribuição.** Remotive, RemoteOK, Jobicy, Himalayas e We Work Remotely exigem crédito e link de volta (`credito_obrigatorio`). O painel mostra "via <fonte>" com link para a vaga na fonte, no cartão e no detalhe. Na RemoteOK o link sai sem `nofollow`. Na Himalayas o botão de candidatura usa o `applicationLink` dela, sem mudança. Nenhum logotipo de fonte é usado. Para as outras fontes, o painel mostra o mesmo "via <fonte>", por clareza (DR-14).
- Fonte nova, no futuro: os termos e os limites são lidos antes de escrever o coletor, e entram no apêndice.
- O armazenamento dos validadores (`cache_http`) entra por injeção: o núcleo define o protocolo e a camada `banco` implementa. Assim o núcleo continua puro. O `HttpEducado` só **lê** os validadores. Os que chegam numa resposta 200 ficam na memória, e o executor grava todos na mesma transação que grava as ocorrências do escopo, e só quando o escopo termina "ok". Se a transação é desfeita, eles se perdem junto, e o pedido seguinte traz a resposta inteira.
- O relógio e o `sleep` vêm de fora (injeção), para os testes não esperarem de verdade.

### 8.3 Saúde por fonte

- Cada escopo de cada execução grava uma linha em `saude`.
- O estado da **fonte** na execução olha só os escopos que rodaram: "ok" se todos ficaram "ok" ou "sem_mudanca"; "falhou" se todos falharam; "parcial" nos outros casos. Se nenhum rodou por causa de limite, a fonte fica "no limite". Um escopo "no_limite" ao lado de outros que rodaram não muda o estado da fonte: a Microsoft esperando o intervalo dela não deixa o Eightfold "parcial". Ele aparece na lista de empresas da fonte, com a hora em que pode rodar de novo.
- Fontes com intervalo mínimo na fase 1 (apêndice). São sete, em dois grupos:

| Fonte | `intervalo_min` | Por quê |
|---|---|---|
| Remotive | 360 | os termos pedem: cerca de 4 consultas por dia |
| Jobicy | 60 | os termos pedem: uma passada por hora |
| We Work Remotely | 60 | o feed pede: `ttl` de 60 min |
| Google | 1440 | prático (decisão da sessão): o feed é grande e muda uma vez por dia |
| Himalayas | 1440 | prático (decisão da sessão): os dados mudam uma vez por dia |
| RemoteOK | 360 | prático (decisão da sessão) |
| Amazon | 360 | prático (decisão da sessão) |

- "Prático" quer dizer: escolhido pela sessão em 2026-11-13. Não é exigência dos termos: nenhuma dessas quatro fontes publica limite.
- Um escopo com intervalo próprio: Microsoft, no Eightfold, 1440 min (`por_escopo`, seção 8.1).
- Todas as outras fontes ficam sem intervalo mínimo. O que protege essas fontes é o pedido condicional (304), o orçamento de pedidos e a obediência ao 429.
- O "buscar agora" respeita o `intervalo_min`, como nas seções 8.1 e 12.2: a fonte que ainda não cumpriu o intervalo fica "no limite", com a hora em que pode rodar de novo.
- Outros limites, além do intervalo: GitHub sem token aceita 60 pedidos por hora por IP (o coletor usa pedido condicional e para quando a cota acaba); Gupy tem orçamento de 30 pedidos por execução, com 2 s entre eles (DR-52; o rodízio da seção 8.1 atende o resto na execução seguinte); Himalayas, 30 pedidos, com 2 s (o que não couber fica para o dia seguinte, por causa do intervalo de 1440 min); Amazon, 2 s entre pedidos; Microsoft (escopo do Eightfold), 5 s entre pedidos, e um 429 encerra só esse escopo até o dia seguinte.
- A tela de saúde (seção 13.8) mostra a fonte e, ao abrir, cada empresa.

### 8.4 Fontes da leva A (JSON e RSS)

Todas foram conferidas ao vivo em 2026-11-13. Endereço, parâmetros, campos, limites e termos estão no apêndice; aqui fica só o resumo.

| Fonte | Tipo | Escopo | Intervalo mínimo | Crédito | Apêndice |
|---|---|---|---|---|---|
| Issues do GitHub: `backend-br/vagas`, `frontendbr/vagas`, `soujava/vagas-java`, `remotejobsbr/design-ux-vagas`, `developersRJ/vagas` | API REST do GitHub | um por repositório | não (60 pedidos/h por IP) | não | 2.1 |
| Remotive | API JSON | lista única | 360 min | sim | 2.2 |
| RemoteOK | API JSON | lista única | 360 min (prático) | sim, link sem `nofollow` | 2.2 |
| Jobicy | API JSON, por cursor | lista única | 60 min | sim | 2.2 |
| Himalayas | API JSON de busca | um por cargo e país das buscas | 1440 min (prático); orçamento de 30 pedidos | sim; candidatura pelo `applicationLink` | 2.2 |
| We Work Remotely | RSS | um por feed | 60 min | sim | 2.2 |
| Hacker News "Who is hiring" | API da Algolia | o tópico do mês | não | não | 2.3 |
| Greenhouse | API pública do quadro | um por empresa | não | não | 2.4 |
| Lever | API pública | um por empresa | não | não | 2.4 |
| Ashby | API pública | um por empresa | não | não | 2.4 |
| SmartRecruiters | API pública | um por empresa e país | não | não | 2.4 |
| Gupy | JSON de busca do portal | um por empresa da lista [a confirmar: parâmetro `careerPageName`] e um por cargo das buscas | não (orçamento de 30 pedidos) | não | 2.5 |

Notas:

- **GitHub.** Sem token. Issue fechada some da lista e a vaga fecha pelo ciclo de vida. Descrição em Markdown. O login do autor da issue não é guardado (DR-15). O `developersRJ/vagas` está parado desde agosto de 2026, mas ainda tem vagas abertas e continua na lista.
- **Hacker News.** Cada comentário de primeiro nível é uma vaga. Empresa, cargo e local vêm da primeira linha, separada por `|` (heurística). O joBot usa só a API de busca, nunca as páginas de `news.ycombinator.com`.
- **We Work Remotely.** XML lido com `xml.etree` (seção 14.4).
- **Greenhouse, Lever e Ashby** trazem a descrição na lista. **SmartRecruiters** usa o `detalhar`.
- **Intervalo "prático".** É o intervalo escolhido pela sessão, sem exigência dos termos (seção 8.3).
- **Gupy.** Entra por decisão do dono (revisão, Q6; seção 20.2), com chave liga/desliga, ritmo educado (2 s entre pedidos, até 30 por execução), link para a vaga original e aviso no README. O endereço é interno do portal, sem contrato publicado: o coletor valida o formato e falha com mensagem clara. Se o `careerPageName` não funcionar, a busca é por nome da empresa e o filtro é feito na resposta (apêndice, 2.5).

### 8.5 Fontes da leva B (páginas)

A leva B começa só depois que a leva A funciona; a fase 1 só fecha com as duas (Q2).

A conferência ao vivo achou caminho público, sem JavaScript, para todas as fontes que ficam, menos a Eureca: ela entrou depois, por decisão do dono, e o caminho dela ainda vai ser conferido (ver abaixo). Ordem de preferência usada, que vale também para a Eureca e para fonte nova (DR-16):

1. Um JSON que a própria página carrega.
2. Dados embutidos no HTML (JSON-LD, `__NEXT_DATA__`, `window.__NUXT__`) ou o próprio HTML, lido com `selectolax`.
3. Se uma fonte futura só funcionar com JavaScript: página aberta pelo Playwright sem janela, com o Chrome instalado quando existir (`channel="chrome"`) e, se não existir, o Chromium baixado. A `fedora-dev` não tem Chrome. Isso exige mover o Playwright para dependência de execução e vai antes para o `duvidas.md` (R4). **Na fase 1 nenhuma fonte conferida precisa disso**, e o Playwright fica só nos testes de tela.

| Fonte | Tipo | Escopo | Intervalo mínimo | Apêndice |
|---|---|---|---|---|
| InHire | API JSON, com o cabeçalho `X-Tenant` | um por empresa | não | 3.1 |
| Quickin | API JSON paginada | um por empresa | não | 3.1 |
| Recrutei | `POST` que responde 202 com JSON; detalhe no HTML | um por empresa | não | 3.1 |
| Sólides | API JSON paginada | um por empresa | não | 3.1 |
| Abler | sitemap + HTML com dados embutidos | lista única, só os recentes | não (orçamento de pedidos) | 3.1 |
| CIEE | API JSON | estágio e aprendiz | não | 3.2 |
| IEL | HTML com as vagas embutidas | um por UF das buscas | não | 3.2 |
| Super Estágios | sitemap + HTML com JSON-LD | lista única, só os recentes | não (orçamento de pedidos) | 3.2 |
| Cia de Talentos | `POST` com JSON | lista única | não | 3.2 |
| Eureca | [a confirmar]: caminho público a achar na captura | [a confirmar] | [a confirmar] | 3.2 |
| Mural da USP | HTML de duas unidades (IF e FEA) | um por unidade | não | 3.2 |
| Workday | `POST` com JSON, 20 por página | um por empresa | não | 3.3 |
| Eightfold | API JSON, duas gerações | um por empresa (Mercado Livre, NVIDIA, Microsoft, Bayer) | não; só o escopo da Microsoft: 1440 min | 3.3 |
| Oracle HCM | API JSON | um por empresa | não | 3.3 |
| Google | feed XML grande, lido em fluxo | lista única | 1440 min (prático); pedido condicional | 3.4 |
| Amazon | JSON de busca | um por país das buscas | 360 min (prático) | 3.4 |

**Ficam fora da fase 1** (motivo completo no apêndice, seção 4, e no `duvidas.md`):

| Fonte | Motivo | Estado |
|---|---|---|
| Meta | os termos proíbem coleta automática sem permissão por escrito. O caminho técnico existe, mas não é usado | fora, por decisão do dono (revisão, Q6; 2026-11-13) |
| Mural da USP, IME e Poli | o IME pede login; a Poli publica em PDF dentro de postagem | fora, definitivo |

- **Eureca, Abler e Gupy entram** por decisão do dono (revisão, Q6; seção 20.2). Cada uma tem chave liga/desliga, ritmo educado, link para a vaga original e aviso no README.
- **Eureca: caminho a confirmar.** O apêndice traz os termos da Eureca, mas não o endereço nem os campos: ela estava fora quando a conferência foi feita. O construtor acha o caminho público na captura (bloco B6), pela ordem de preferência desta seção, e completa o apêndice antes de escrever o coletor. A espera entre pedidos e o orçamento por execução são definidos nessa captura, nunca abaixo do padrão da seção 8.2. Se não houver caminho público sem login, vale a regra de sempre: a fonte fica fora, com o motivo no `duvidas.md`.
- Microsoft e NVIDIA não têm coletor próprio: são empresas do coletor Eightfold.
- **Abler e Super Estágios são fontes de sitemap.** A listagem traz só o endereço e a data de cada vaga. Elas seguem a regra da seção 8.1 (DR-70): devolvem `UrlListada`, e a vaga só é gravada depois do `detalhar`.
- As empresas da leva B que a conferência viu responder (apêndice, 3.1 e 3.3) são o ponto de partida. Cada uma entra em `empresas.json` com `conferida_em` e com os `parametros` do ATS (seção 8.6), pelo `scripts/conferir_empresas.py`, no bloco B6.
- Fonte da leva B que perder o caminho público durante a construção sai com o motivo no `duvidas.md`, e a fase fecha do mesmo jeito (resolução do dono). `robots.txt` não conta como motivo.

### 8.6 Lista de empresas (Q3)

- Arquivo `src/jobot/nucleo/dados/empresas.json`, no nosso formato:

```json
{"versao": 1, "empresas": [
  {"nome": "…", "area": "banco", "fonte": "greenhouse", "identificador": "…", "pais": "BR", "parametros": {}, "conferida_em": "AAAA-MM-DD"}
]}
```

- `pais` é o país da empresa (ISO 3166-1 alfa-2) e vai para a coluna `empresa.pais`. `parametros` guarda o que o ATS pede além do identificador e vai para `empresa.parametros`. Nos ATS da leva A fica `{}`. Nos da leva B (DR-65):

| ATS | `identificador` | Chaves de `parametros` |
|---|---|---|
| InHire | tenant (o subdomínio) | nenhuma |
| Quickin | slug da página de vagas | `account_id` |
| Recrutei | `label` | nenhuma |
| Sólides | slug (o subdomínio) | nenhuma |
| Workday | `tenant/site` (ex.: `mastercard/CorporateCareers`) | `wd` (ex.: `wd1`) |
| Eightfold | host (ex.: `mercadolibre.eightfold.ai`) | `dominio`, `geracao` (`pcsx` ou `v2`) |
| Oracle HCM | host | `site_number` (ex.: `CX_45001`), `site` (ex.: `jobsearch`) |

- Quem preenche os `parametros`: o método `resolver` do coletor (seção 8.1), chamado pelo "testar" do painel e pelo `scripts/conferir_empresas.py`. Ele descobre o que dá para descobrir sozinho: o `account_id` do Quickin, a `geracao` do Eightfold e o `site_number` do Oracle. O resto sai do endereço do quadro que a pessoa cola; se faltar, o painel pede o campo. A coleta normal só lê os `parametros`, nunca grava.
- O id de país do Workday e o `GeographyId` do Oracle **não** ficam em `parametros`: mudam por país, e o coletor lê os dois da primeira resposta de cada execução (apêndice, 3.3).

- A lista inicial tem **67 empresas**, já conferidas ao vivo em 2026-11-13: 15 no Greenhouse, 8 no Lever, 5 no Ashby, 11 no SmartRecruiters e 28 na Gupy. Nomes, áreas e identificadores estão no apêndice, seção 7.
- Não há espera pelo dono: a lista entra como está, e ele revê, desliga ou remove pelo painel depois.
- `scripts/conferir_empresas.py` refaz a conferência quando alguém roda à mão: acessa cada quadro, conta as vagas e grava `conferida_em`. Quadro que não responde sai da lista.
- Empresas de ATS da leva A entram com a leva A; as de ATS da leva B, com a leva B.
- Na primeira execução, a lista é copiada para a tabela `empresa` (`origem = 'lista_inicial'`). Em atualizações, entradas novas da lista entram; o que a pessoa mudou nunca é sobrescrito. A carga compara por `fonte` e `identificador`: entrada que já tem linha na tabela é pulada, mesmo que a linha esteja desligada ou removida.
- No painel, a pessoa adiciona empresas: escolhe o ATS, cola o identificador ou o endereço do quadro, clica em "testar". O app faz um pedido ao vivo e mostra quantas vagas achou, antes de salvar.
- No painel, a pessoa também desliga (`ativa = 0`) ou remove qualquer empresa, inclusive as da lista inicial.
- **Remover marca, não apaga** (DR-68). A linha fica na tabela `empresa`, com `removida_em` preenchido. A empresa removida some da tela **Empresas**, a coleta a ignora e a carga da lista inicial a pula. Por isso, empresa removida da lista inicial não volta numa atualização. A descoberta (seção 8.7) também não a sugere de novo.
- Se a pessoa adicionar de novo a mesma empresa (mesmo ATS e mesmo identificador), o app limpa o `removida_em` da linha que já existe. Não cria outra linha.

### 8.7 Descoberta semanal pelo Common Crawl

- Uma vez por semana, o joBot olha a lista de índices do Common Crawl. Só roda a descoberta quando aparece um índice novo (sai um por mês, mais ou menos).
- Usa o **índice bruto**: lê o `cluster.idx` em fluxo e busca só os blocos dos hosts de interesse, com pedido de faixa (`Range`). A API de consulta do Common Crawl é limitada demais e não é usada (apêndice, 5).
- Procura endereços de quadros de Greenhouse, Lever, Ashby e Gupy. Espera de 10 s entre pedidos.
- Extrai o identificador, descarta os que já estão na tabela `empresa` (inclusive os removidos) e testa cada um no ATS. Só vira sugestão, em `empresa_sugerida`, a empresa que tem vaga no Brasil ou remota.
- As sugestões aparecem na tela **Empresas → Sugeridas**. A pessoa aprova uma por uma (o app testa ao vivo, como na seção 8.6) ou descarta. Nada entra sozinho na busca (resolução do dono; DR-17).
- Chave liga/desliga em **Configurações → Fontes**. Ligada por padrão (a ADR 0004 diz "pode desligar").
- É uma execução do tipo `descoberta`: tem trava própria e nunca segura a busca (seção 12.3). Falha na descoberta não afeta as buscas normais.

### 8.8 Acompanhar páginas de programas ("adicionar site")

- Na tela **Sites acompanhados**, a pessoa cola o endereço de uma página (por exemplo, um programa de trainee ou de escola de verão) e dá um nome.
- Uma vez por dia (DR-18), o app baixa a página, transforma em texto (seção 14.3), calcula o hash e compara com a versão anterior.
- Se mudou, grava a diferença (`difflib`) em `mudanca_pagina`. A aba **Programas** mostra "mudou em <data>" e a diferença.
- Endereço aceito: só `http`/`https`, e nunca para `localhost`, `127.0.0.0/8`, rede privada ou link-local (para o app não ser usado contra o próprio computador ou a rede de casa) (DR-19).
- Página que falha fica com estado "falhou" na tela, sem afetar o resto.
- É uma execução do tipo `paginas`: tem trava própria e nunca segura a busca (seção 12.3). Chave liga/desliga em configurações.

---

## 9. Fixtures e captura

### 9.1 Regra de ouro

Nenhum endereço vira coletor sem uma captura nossa. Os testes usam só essas capturas (ADR 0004 e 0016). A conferência ao vivo de 2026-11-13 (apêndice) confirmou os endereços e os campos; ela não substitui a captura, que gera a fixture versionada de cada coletor.

### 9.2 Como capturar

- `uv run python scripts/capturar.py <fonte> [--escopo <id>] --caso <nome>`.
- Faz o pedido ao vivo, com o mesmo `HttpEducado` e o mesmo user agent do app. A conferência de 2026-11-13 usou um user agent genérico; a primeira captura de cada fonte confirma que o user agent do joBot também é aceito.
- Grava `tests/fixtures/<fonte>/<caso>.<json|html|xml>` e `<caso>.meta.json` com: URL, data e hora, código HTTP, cabeçalhos úteis (`Content-Type`, `ETag`, `Retry-After`), sha256 do arquivo e versão do joBot.
- Reduz a amostra: no máximo 5 itens e 50 KB por arquivo (DR-20). A redução é feita pelo script, nunca à mão no meio do JSON.
- Remove dados pessoais: e-mails, telefones e nomes de pessoas (por exemplo, o autor de uma issue ou o recrutador) viram valores de exemplo. Um teste procura esses padrões nas fixtures (critério 21).
- Para a leva B, a captura também guarda o JSON visto na aba Rede, quando for ele o caminho escolhido.

### 9.3 Casos mínimos por coletor

1. Resposta normal → vagas certas, estado "ok".
2. Lista vazia → zero vagas, "ok".
3. Formato mudado (campo obrigatório faltando) → "parcial" ou "falhou", nunca exceção.
4. Paginação, quando a fonte tiver.
5. 429 e erro de rede, com `httpx.MockTransport`.
6. 304, quando a fonte manda `ETag` ou `Last-Modified` → "sem_mudanca".
7. Bloqueio (403 ou página de login) → "falhou", sem nova tentativa com outro cabeçalho.

Os casos 3 a 7 podem usar cópias editadas da fixture capturada; o arquivo editado diz no nome que foi editado (`*.editado.json`).

### 9.4 Testes nunca usam a rede

- Um `conftest.py` na raiz dos testes troca `socket.socket.connect` por uma versão que só aceita `127.0.0.1` e `::1` (para o servidor dos testes de tela). Qualquer outro destino dá erro (DR-21).
- `scripts/capturar.py` e `scripts/conferir_empresas.py` são as únicas partes que acessam a rede de propósito, e só rodam à mão.
- Teste automático: todo coletor em `registro.py` tem pelo menos uma fixture com `.meta.json`.

---

## 10. Tratamento (ADR 0007)

As regras ficam em arquivos JSON em `nucleo/dados/`. JSON é lido direto pelo Python e pelo JavaScript da fase 7, sem biblioteca extra (DR-22). Expressões regulares nesses arquivos usam só o pedaço comum entre Python e JavaScript: sem grupos com nome, sem flags dentro da expressão, sem lookbehind. Um teste confere isso.

Normalização de texto (igual nas duas linguagens): Unicode NFKD, tira acentos, `casefold`, junta espaços.

### 10.1 Duplicadas

- **URL canônica:** host em minúsculas, sem `#fragmento`, sem barra final, parâmetros em ordem alfabética, sem os parâmetros de rastreamento da lista `rastreamento.json` (`utm_*`, `gclid`, `fbclid` e outros). Parâmetros que identificam a vaga (por exemplo, um id de vaga na query) ficam.
- **`url_hash`:** sha256 da URL canônica. Mesmo hash = mesma vaga. É a **única** chave de duplicata (ADR 0007). Não existe segunda chave por empresa e título.
- A mesma URL vista em mais de um escopo ou fonte (por exemplo, a mesma vaga da Gupy achada pela empresa e pelo cargo) vira uma vaga só, com uma ocorrência por escopo.
- **Vários locais.** Quando a fonte publica uma vaga com várias cidades (Lever `allLocations`, Ashby `secondaryLocations`, Greenhouse `offices`, Amazon `locations`), ela vira uma linha com vários locais.
- **Limite conhecido.** Se a empresa publica a mesma vaga com uma URL diferente por cidade, ou em dois sites, o joBot mostra uma linha por URL. É o preço de não juntar vagas diferentes por engano. A pessoa pode ocultar as repetidas.
- A limpeza da URL nunca mexe no `url_candidatura`.

### 10.2 Ciclo de vida

Por escopo, no fim de cada execução (função pura: recebe as ocorrências abertas do escopo, os `url_hash` vistos agora, o estado do escopo e a data; devolve o que muda):

| Estado do escopo | Ocorrência não vista agora |
|---|---|
| ok | marca `sumiu_em` agora |
| parcial | marca `sumiu_em` só se `ultima_vista_em` tiver mais de 30 dias |
| sem_mudanca | nada some; todas as ocorrências abertas do escopo ganham `ultima_vista_em` de agora |
| falhou, desligada, no_limite | nada muda |

- A vaga fecha (`fechada_em`) quando todas as ocorrências dela sumiram.
- Se uma ocorrência reaparece, `sumiu_em` volta a vazio e a vaga reabre.
- **Fonte de sitemap (DR-70):** a URL listada que já tem ocorrência dessa fonte no banco conta como vista, sem novo pedido de detalhe, mesmo com data antiga. A URL nova que ainda espera o `detalhar` não entra no ciclo de vida: ela ainda não é vaga.
- Vaga com `prazo` vencido sai das listas (ADR 0007), mesmo aberta na fonte.
- Vaga fechada ou vencida com status "salva" ou além continua em **Salvas** e **Candidatei**, com o selo "fechada" (DR-24). O histórico da pessoa nunca some.
- Nenhuma vaga é apagada, nem fechada nem antiga: o ciclo de vida marca, não apaga. O texto completo fica guardado para a fase 6 (seção 7.6).

### 10.3 Salário

```python
@dataclass(frozen=True)
class Salario:
    moeda: str                    # ISO 4217: BRL, USD, EUR...
    minimo: int | None            # centavos
    maximo: int | None            # centavos
    periodo: Literal["hora", "dia", "semana", "mes", "ano"]
    mensal_minimo: int | None     # centavos, na moeda original
    plausivel: bool
    texto: str                    # como veio
    beneficios: tuple[str, ...]   # separados do salário

def ler_salario(texto: str | None, estruturado: SalarioBruto | None, idioma: str) -> Salario | None: ...
```

- Separa salário de benefícios (VR, VA, plano de saúde, bônus, PLR).
- Entende `R$ 5.000,00`, `5k`, `5 mil`, `120k-150k`, `$50/hr`, `a combinar` (vira `None`).
- Período: lido do texto; se não vier, deduzido pela ordem de grandeza e marcado assim.
- **Sem símbolo nem código de moeda:** vaga em português → BRL; em inglês → USD; em outro idioma → o salário não é lido (vira `None`). É regra de produto (decisão DP4 do plano, aceita pela sessão em 2026-11-13).
- Conversão para mensal (DR-25): ano ÷ 12; semana × 4,33; dia × 21; hora × 160.
- Plausível: faixas por moeda e período num arquivo de dados (por exemplo, BRL por mês entre 500 e 150.000) (DR-25). Implausível fica guardado, mas não é usado para ocultar nem para ordenar.
  - As faixas vêm em unidades inteiras da moeda (reais, dólares), não em centavos. A comparação usa `mensal_minimo` ÷ 100. Exemplo: `R$ 5.000,00` são 500.000 centavos, isto é, 5.000 reais: plausível.
- `tests/casos/salario.json`: cada caso tem `texto`, `idioma` e o resultado esperado. É JSON para o teste em JavaScript da fase 7 ler o mesmo arquivo (ADR 0007). Bug corrigido vira caso novo.

**Conversão para reais (resposta do dono; ADR 0007).**

- Fonte: PTAX de fechamento do Banco Central, API pública sem chave (apêndice, 6). Usa a cotação de **venda**, com `decimal.Decimal`.
- Um pedido por moeda por dia, só das moedas que aparecem em vaga aberta. O pedido cobre os últimos 7 dias e usa a linha mais recente: assim fim de semana e feriado caem no último dia útil. O resultado fica na tabela `cotacao`.
- O PTAX cobre 10 moedas: AUD, CAD, CHF, DKK, EUR, GBP, JPY, NOK, SEK e USD.
- Com cotação: `sal_mensal_min_brl` = mínimo mensal × cotação, em **reais inteiros** (não centavos), arredondado para o real mais próximo. Exemplo: 5.000 USD por mês, a 5,65, viram 28250. O `sal_mensal_max_brl` é o máximo mensal, convertido do mesmo jeito, quando a vaga traz máximo. O filtro de salário mínimo, a ordenação por salário e a parte de salário da nota usam esse valor. Quando chega cotação nova, o app refaz o valor das vagas abertas e o encaixe.
- **Vaga em BRL:** não precisa de cotação. `sal_mensal_min_brl` e `sal_mensal_max_brl` valem os centavos ÷ 100, arredondados para o real mais próximo, e `sal_cotacao_data` fica `NULL`. Vale mesmo com a conversão desligada: o filtro, a ordenação e a nota continuam a ver as vagas em reais.
- O salário mínimo da busca é guardado em centavos da `salario_moeda` (seção 7.3) e também vira reais inteiros. Em BRL: centavos ÷ 100, arredondado. Em outra moeda: pela cotação mais recente guardada. Sem cotação, o mínimo fica sem valor em reais e a parte de salário da nota fica neutra.
- **Unidade nas assinaturas.** Os valores na moeda original (`Salario.minimo`, `maximo` e `mensal_minimo`) são centavos. Os convertidos são reais inteiros: o encaixe recebe `sal_mensal_brl: int | None` e `minimo_busca_brl: int | None`, os dois em reais (seção 11.2). Toda assinatura que leva dinheiro diz a unidade.
- **Vaga em moeda estrangeira sem cotação** (moeda fora das 10, PTAX fora do ar e sem cotação guardada dos últimos 7 dias, ou conversão desligada): o painel mostra só o valor original, a vaga **não** é ocultada pela regra de salário, e a parte de salário da nota fica neutra (seção 11.2).
- Na tela (seção 13.5): o salário na moeda original e, ao lado, menor e mais apagado, a cotação do dia e o valor em reais.
- Chave **Conversão de moeda** em configurações. Ligada por padrão. Desligada: nenhum pedido vai ao PTAX, e os valores `_brl` e a `sal_cotacao_data` das vagas em moeda estrangeira voltam a `NULL`, para o filtro, a ordenação e a nota não usarem valor velho. As vagas em BRL não mudam. Ao religar, o app refaz o valor das vagas abertas com as cotações guardadas.
- A leitura da resposta do PTAX e a conta ficam em `nucleo/cambio.py`, funções puras, testadas com uma captura nossa. O pedido passa pelo `HttpEducado`.

### 10.4 Rótulos

| Rótulo | Valores (DR-27) |
|---|---|
| área | tecnologia, dados, design, produto, marketing, vendas, finanças, rh, jurídico, operações, engenharia, saúde, educação, administrativo, atendimento, pesquisa, outra |
| nível | estágio, trainee, júnior, pleno, sênior, especialista, liderança, não informado |
| modalidade | presencial, híbrido, remoto, não informado |
| contrato | clt, pj, estágio, trainee, temporário, aprendiz, bolsa_pesquisa, programa, concurso, freelance, não informado |
| região | país (ISO), UF (Brasil), cidade |
| avisos | exige_visto, exige_doutorado, restrito_a_pais |

- Regras em `rotulos.json`: para cada valor, termos e expressões em pt e en, com peso, onde procurar (título, etiquetas, descrição) e prioridade. O que a fonte declara (`modalidade_declarada`, `contrato_declarado`) ganha da descrição.
- `tests/casos/rotulos.json`: casos pequenos, feitos por nós, sem dado pessoal. São os que rodam no CI.
- Locais: `ufs.json` com siglas, nomes e capitais. Lista completa de municípios do IBGE só se a licença dos dados permitir [a confirmar]; senão, capitais e o texto livre.
- Idioma da vaga: contagem de palavras comuns de pt, en e es (DR-02).

### 10.5 Requisitos de estágio

Expressões regulares (ADR 0007) extraem, quando houver: curso, semestre ou ano mínimo, previsão de formatura, carga horária e bolsa. Ficam em `requisitos_estagio` e aparecem no detalhe da vaga.

### 10.6 Enriquecimento

- Para fontes cuja listagem não traz descrição, o coletor implementa `detalhar`.
- Só roda para vagas novas, com cache de 30 dias na tabela `enriquecimento` (ADR 0007).
- O resultado do `detalhar` é gravado em `ocorrencia.coletada`. A tabela `enriquecimento` é só o cache: quando ele vence, o texto da vaga continua guardado (seção 7.6). Na coleta seguinte, a listagem sem descrição não apaga esse texto (seção 7.6).
- Limite por execução: 50 por fonte e 200 no total (DR-28). O que não couber fica para a próxima.
- **Fonte de sitemap (DR-70):** nas fontes que devolvem `UrlListada` (seção 8.1), o `detalhar` é o que cria a vaga, e quem o chama é o executor. As URLs novas entram no mesmo limite, as mais recentes primeiro. Detalhe sem título ou sem empresa não vira vaga: a tentativa fica no cache, com `conteudo` vazio, e a URL só volta ao `detalhar` depois de 30 dias (seção 8.1).
- Chave **Enriquecimento** em configurações. Desligada, as vagas dessas fontes ficam só com o que a listagem traz. Nas fontes de sitemap, nenhuma vaga nova entra; as URLs que já têm ocorrência dessa fonte no banco continuam a contar como vistas.

### 10.7 Conjunto de ouro (gabarito) e medição

O conjunto de ouro, ou gabarito, são vagas reais, cada uma com os rótulos certos (ADR 0007). Ele serve para medir as regras. Esta seção segue a decisão de 2026-11-13 (seção 20.2).

**As vagas**

- **Já estão coletadas:** 329 vagas reais, de 30 fontes, coletadas em 2026-11-13, em três grupos: g1 com 84, g2 com 130 e g3 com 115.
- **Ficam só no computador, fora do repositório:** na pasta `joBot-dados/ouro/bruto/`, vizinha da pasta do projeto. Vaga real pode trazer dado pessoal no texto, e nada disso vai para o GitHub (resposta do dono).
- **Arquivos (conferidos pela sessão em 2026-11-13):** três, na pasta do bruto: `g1.jsonl` (84 vagas), `g2.jsonl` (130) e `g3.jsonl` (115). As pastas de cache ao lado deles não são lidas.
- **Formato:** um JSON por linha. As chaves de topo são iguais nos três arquivos: `id`, `fonte`, `url`, `titulo`, `empresa`, `local`, `descricao_texto`, `descricao_html`, `metadados` e `coletado_em`.
- **`metadados` é um objeto livre**, que muda de fonte para fonte (por exemplo, `careerPageName` e `workplaceType` na Gupy, `salaryPeriod` no Remotive). O `avaliar-rotulos` lê todos os `*.jsonl` da pasta do bruto e não depende de nenhuma chave de `metadados`.
- A coleta não é código do app e não passa pelo `scripts/capturar.py`.
- Mistura de fontes, áreas, níveis e idiomas.
- **A proporção de vagas no Brasil é uma medida, não uma exigência** (DR-29). Ela é contada pelo `avaliar-rotulos`, a partir do campo `pais` de `rotulos.jsonl`, e registrada em `docs/rotulos-medidos.md`. O gabarito está fechado: nenhuma vaga é coletada a mais para mudar a proporção, mesmo que ela fique abaixo da metade.

**A rotulagem**

- É orquestrada pela sessão de trabalho. Não é código do app.
- Agentes Sonnet rotulam.
- O Fable rotula de novo, às cegas: sem ver a primeira resposta.
- Onde os dois discordam, o Fable decide e registra o porquê.
- O dono **não** confere amostra do gabarito.
- **Arquivo rotulado:** `<caminho do gabarito>/rotulos.jsonl`, fora do repositório. O caminho do gabarito é a pasta que contém `bruto/`. Uma linha por vaga do bruto, ligada pelo `id`:

  ```json
  {"id":"…","rotulos":{"area":"…","nivel":"…","modalidade":"…","contrato":"…","pais":"BR","uf":"SP","avisos":[]}}
  ```

- Os valores são os da seção 10.4, em ASCII minúsculo, com `_` no lugar do espaço (decisão DP1 do plano): por exemplo `junior`, `hibrido`, `nao_informado`. `pais` é o código ISO 3166-1 alfa-2. `uf` é a sigla, só para vaga no Brasil; fora dele, `null` ou ausente: o `avaliar-rotulos` trata os dois como sem UF. `avisos` é uma lista, vazia quando não há aviso. Da região, o gabarito traz país e UF; a cidade não é rotulada.
- A linha pode trazer também `divergencias`: o registro de onde os dois rotuladores discordaram e do porquê. O `avaliar-rotulos` lê só `id` e `rotulos`.
- **O gabarito nunca entra em dados de treino** (ADR 0015). Ele só mede.

**A medição**

- `uv run jobot avaliar-rotulos <caminho>` recebe o caminho do gabarito por argumento, roda as regras e mostra o acerto por rótulo e a lista de erros. O app não tem caminho fixo para o gabarito.
- Caminho que não existe: o comando diz que o gabarito não está neste computador e sai sem erro (DR-63).
- A pasta `dados_locais/` continua no `.gitignore`, para quem preferir guardar o gabarito dentro da pasta do projeto.
- **Para o GitHub vai só o resultado:** as regras ajustadas (`rotulos.json`) e os números medidos, em `docs/rotulos-medidos.md` (rótulo, acerto, tamanho da amostra, data, e a proporção de vagas no Brasil). Nenhum texto de vaga.
- **O CI não usa o conjunto de ouro.** Usa só `tests/casos/rotulos.json` e as fixtures pequenas, feitas por nós. O teste do `avaliar-rotulos` usa um gabarito pequeno de exemplo, também feito por nós.
- **Meta de 90% por rótulo.** A fase 1 mede e registra. Rótulo abaixo de 90% **não** impede o fechamento da fase: fica anotado e o modelo multilingual-e5-small entra na fase 3 (resposta do dono; ADR 0007).
- **O painel não tem tela de conferência.** A tela "Conferir rótulos" saiu da fase 1 em 2026-11-13. Ela existia para o dono avaliar as regras, e o dono trocou essa avaliação pelo gabarito rotulado por modelos (DR-67).

---

## 11. Encaixe por regras e Destaques de hoje

### 11.1 Preferências (uma busca salva)

Cargos ou palavras-chave, cidades, modalidades aceitas, níveis, salário mínimo mensal com moeda, idiomas aceitos (Q4).

- A pessoa pode ter várias buscas salvas (ADR 0001). O encaixe e a ocultação são calculados para cada busca ativa. O painel tem um seletor de busca, guardado na URL (`?busca=<id>`). A primeira busca nasce na primeira execução (DR-04).
- O país da pessoa é o das cidades que ela informou (padrão: Brasil) (DR-30).
- **Critério vazio é neutro.** Campo que a pessoa não preencheu não soma nem tira ponto, e não oculta nada.
- **Busca sem nenhum critério.** O painel pede as preferências ("diga o que você procura"), as listas e os Destaques saem por data, e nenhuma vaga ganha ●, ◐ ou ○ (`encaixe.nota` fica vazio).

### 11.2 Nota de 0 a 100 (Q5)

Pesos em `encaixe.json` (DR-31):

| Parte | Pontos |
|---|---|
| Cargo ou palavra-chave no título | 40 (só na descrição: 20) |
| Local e modalidade (cidade igual, mesma UF, ou remoto aceito) | até 20 |
| Nível dentro dos escolhidos | 15 (não informado: 7) |
| Salário igual ou acima do mínimo, já em reais | 15 (não informado, implausível ou sem cotação: 7) |
| Idioma da vaga aceito | 10 (não detectado: 5) |

- **Nota = 100 × pontos obtidos ÷ soma dos pesos dos critérios preenchidos.** Com tudo preenchido, a soma é 100 e a nota é a soma dos pontos. Com um critério vazio, o peso dele é repartido entre os outros (resolução do dono).
- Nível do encaixe: **● bom** a partir de 70, **◐ médio** de 40 a 69, **○ fraco** abaixo de 40 (ADR 0007; limites DR-31).
- Cada parte gera um motivo (chave de i18n com parâmetros), por exemplo "cargo 'backend' no título" ou "salário não informado". O painel mostra todos os motivos.
- Habilidades que a pessoa tem e que faltam ficam para a fase 3. Na fase 1, o detalhe mostra só quais palavras-chave da busca apareceram na vaga (DR-32).

### 11.3 Ocultar por regra

Regras ligadas por padrão, cada uma desligável na busca, mais uma chave geral em configurações que desliga todas de uma vez (DR-33):

- modalidade fora das aceitas (só quando a modalidade é conhecida);
- nível fora dos escolhidos (só quando conhecido);
- salário plausível, em reais (convertido quando há cotação), abaixo do mínimo. Sem cotação, a regra não se aplica;
- idioma da vaga fora dos aceitos (só quando detectado);
- remoto restrito a outro país.

A primeira regra que bater vira o `oculta_motivo`. A aba **Ocultas** mostra um chip por motivo, com a contagem (ADR 0007), e em cada vaga o botão "mostrar mesmo assim". O botão "ocultar" manual em cada vaga usa `oculta_manual`.

### 11.4 Destaques de hoje

- Vagas abertas, não ocultas, com status "nova", vistas pela primeira vez nas últimas 24 horas (DR-34).
- Uma por empresa: a de maior nota de cada empresa.
- Ordem: nota, depois data de publicação. Busca sem nenhum critério: só data.
- Mostra as N primeiras. N = 10 por padrão, ajustável em configurações (resolução do dono; DR-34).
- Chave **Destaques** em configurações. Desligada, a aba some e o painel abre em **Todas**.
- Sem vagas: mensagem amigável e a hora da próxima busca.
- Função pura em `nucleo/destaques.py`, testada sem banco.

---

## 12. Agenda e segundo plano

### 12.1 Um processo só

O servidor do painel e a agenda rodam no **mesmo processo** (DR-35):

- `uvicorn` serve o painel.
- Uma tarefa `asyncio` (o agendador) acorda a cada 60 segundos e confere o que está na hora.
- A conferência usa o relógio de parede e a última execução gravada no banco, não um "dormir 3 horas". Assim, suspender o computador não confunde a agenda.

### 12.2 O que roda e quando

| Tarefa | Quando | Origem |
|---|---|---|
| Busca nas fontes públicas | 3 horas depois do início da última busca **completa**, seja da agenda, do "buscar agora" ou da recuperação. Busca interrompida não conta | ADR 0006; "do início" é DR-61 |
| Buscar agora | botão no painel, ou `uv run jobot buscar`. Busca tudo na hora e ignora o intervalo da agenda. Só espera a fonte que tem `intervalo_min` ainda não cumprido (seção 8.3) | ADR 0006 |
| Execução perdida | ao iniciar, se a última busca passou de 3 horas: roda 60 segundos depois, para dar tempo da rede subir | ADR 0006; espera DR-35 |
| Descoberta Common Crawl | 7 dias depois da última; só baixa quando há índice novo | ADR 0004 |
| Páginas acompanhadas | 24 horas depois da última | DR-18 |
| Cotação PTAX | dentro da busca, uma vez por dia por moeda (seção 10.3) | ADR 0007 |

### 12.3 Uma execução de cada tipo por vez

Há três tipos de execução: **busca**, **descoberta** e **páginas**. Cada tipo tem a sua trava. Descoberta e páginas acompanhadas **nunca** seguram a busca (resolução do dono).

Travas (DR-36):

1. **Por instalação:** `jobot.lock` na pasta de dados, com `fcntl.flock`. Um segundo processo `jobot serve` não sobe; avisa que o joBot já está aberto. O arquivo guarda o PID do servidor.
2. **No banco, por tipo:** o índice único `execucao_uma_por_tipo` impede duas execuções "rodando" do mesmo tipo.
3. **No processo, por tipo:** um `asyncio.Lock` para cada tipo.

- Os três tipos usam o mesmo `HttpEducado`. Assim o intervalo por host vale mesmo com dois tipos rodando ao mesmo tempo.
- "Buscar agora" com uma busca já rodando não começa outra: mostra o andamento da que está rodando.
- "Buscar agora" com a descoberta ou as páginas rodando começa na hora.
- Execução com `batimento_em` parado há mais de 5 minutos (processo morto) vira "interrompida" ao iniciar o app.

### 12.4 Passos de uma execução

1. Cria a linha em `execucao`, com `tipo = 'busca'`.
2. Para cada fonte ligada, roda os escopos (seção 8.1). Fonte com `intervalo_min` ainda não cumprido fica "no limite" e não é chamada. O mesmo vale para o escopo com intervalo próprio. Nas fontes de sitemap, o executor já manda as URLs novas ao `detalhar` aqui, dentro do orçamento de enriquecimento (DR-70; seção 8.1).
3. Para cada escopo, numa transação: trata as vagas (seção 10), junta duplicadas, grava ocorrências, saúde e os validadores do `cache_http` (seção 8.2), aplica o ciclo de vida. Ao gravar de novo uma ocorrência que já existe, a descrição vazia da listagem não substitui a que veio do `detalhar`: `descricao`, `descricao_formato` e `vaga.descricao_texto` ficam como estão. Só uma descrição não vazia substitui a anterior (seção 7.6). Vaga, ocorrência e empresa são gravadas com `INSERT ... ON CONFLICT(...) DO UPDATE`, nunca com `REPLACE` (seção 7.6).
4. Enriquece as vagas novas (seção 10.6), se a chave estiver ligada. Os detalhes que o executor já pediu para as fontes de sitemap contam no mesmo limite (DR-70).
5. Busca a cotação do dia das moedas que apareceram, se ainda não tem, e atualiza o valor em reais (seção 10.3). A vaga em BRL ganha o valor em reais neste passo também, sem cotação e mesmo com a conversão desligada. Falha aqui não derruba a busca.
6. Recalcula encaixe e ocultação das vagas novas ou mudadas, para cada busca ativa.
7. Fecha a execução.

Uma queda no meio deixa os escopos anteriores gravados e o atual desfeito, inclusive os validadores dele.

### 12.5 Segundo plano no Linux (fase 1)

Só Linux nesta fase; Windows e macOS na fase 8 (decisão da sessão principal; ADR 0003). O segundo plano é o passo 2 da primeira execução (ADR 0006).

O joBot funciona em dois casos (resposta do dono; ADR 0006):

| | Instalado direto no sistema | Dentro de uma distrobox (caso do dono: `fedora-dev`) |
|---|---|---|
| Como detecta | `CONTAINER_ID` não existe | `CONTAINER_ID` existe e traz o nome do container |
| Onde fica o serviço | `~/.config/systemd/user/jobot.service` | o mesmo arquivo: a distrobox usa a mesma pasta pessoal do sistema |
| `ExecStart` | `<python> -m jobot serve` | `<distrobox-enter> -n <container> -- <python> -m jobot serve` |
| `ExecStop` | não precisa | `<distrobox-enter> -n <container> -- <python> -m jobot sair` |
| Comandos do `systemctl --user` | direto | por `distrobox-host-exec systemctl --user …`, porque o systemd é o do sistema de fora |
| `Exec` do atalho | `<python> -m jobot abrir` | `distrobox-enter -n <container> -- <python> -m jobot abrir` |
| Abrir o navegador | `webbrowser` | `distrobox-host-exec xdg-open <endereço>`, porque o container não tem navegador |

- `<python>` é o caminho absoluto de `sys.executable` (o Python do ambiente do joBot).
- `<distrobox-enter>` é o caminho absoluto no sistema de fora, achado com `distrobox-host-exec sh -c 'command -v distrobox-enter'`.
- O serviço tem `Restart=on-failure` e `WantedBy=default.target` nos dois casos.
- **Por que o `ExecStop`:** dentro da distrobox, parar o serviço só encerra o `distrobox-enter`. O `jobot sair` encerra o servidor de verdade (seção 12.6).
- **Ligar** (primeira execução ou configurações): escreve o arquivo, roda `daemon-reload` e `enable --now jobot.service`.
- **Desligar:** `disable --now jobot.service` e apaga o arquivo.
- **Status:** `is-enabled` e `is-active`, mostrados nas configurações, junto com o caso detectado ("rodando dentro da distrobox fedora-dev").
- **Atalho:** `~/.local/share/applications/jobot.desktop`. Ele é criado ao ligar o segundo plano e também na primeira execução, mesmo com o segundo plano desligado (DR-37).
- "Iniciar com o computador" quer dizer: inicia quando a pessoa entra na sessão. Não usa `loginctl enable-linger` (resolução do dono; DR-38).
- **Quando recusa ligar,** com mensagem clara: `distrobox-host-exec` não existe; o `systemd --user` de fora não responde; ou a pasta pessoal do container não é a do sistema (distrobox criada com pasta própria), porque aí o serviço escrito não seria visto.
- O texto do arquivo `.service` e do `.desktop` sai de funções puras, que recebem o caso (direto ou distrobox, com o nome do container) e são testadas nos dois. As chamadas ao `systemctl` e ao `distrobox-host-exec` passam por uma função que os testes trocam por uma falsa. O teste real é o passo 21 do roteiro.
- O construtor confere ao vivo, no começo do bloco B4, se o `distrobox-enter` roda sem terminal dentro do systemd. Se pedir terminal, a linha ganha a opção `--no-tty` (DR-56).
- Fora do Linux, o passo e a chave aparecem desativados, com o texto "chega numa próxima versão".

### 12.6 Como o painel abre

- `uv run jobot` (sem nada) = `jobot abrir`:
  - se a trava `jobot.lock` estiver presa (servidor rodando), abre `http://127.0.0.1:<porta>` no navegador e sai;
  - se não, sobe o servidor num processo separado (`start_new_session=True`), espera responder e abre o navegador.
  - o navegador abre com `webbrowser`; dentro de uma distrobox, com `distrobox-host-exec xdg-open`. Se nada abrir, o terminal mostra o endereço.
- `uv run jobot serve`: só o servidor, sem abrir nada (usado pelo systemd).
- `uv run jobot sair`: lê o PID no `jobot.lock`, manda o servidor encerrar (SIGTERM) e espera. Usado pelo `ExecStop` na distrobox.
- `uv run jobot buscar`: faz uma busca no terminal e mostra o resumo da saúde.
- `uv run jobot segundo-plano ligar|desligar|status`.
- `uv run jobot avaliar-rotulos <caminho do gabarito>` (seção 10.7).
- Com o segundo plano desligado, o servidor fica rodando até a pessoa clicar em **Sair** no painel (POST `/sair`) ou desligar o computador (DR-39).
- Porta fixa, para o atalho e os favoritos funcionarem: `47615` por padrão, trocável pela variável `JOBOT_PORTA` (DR-40). Porta ocupada por outro programa: mensagem clara no terminal e no log.
- Linha de comando com `argparse`, da biblioteca padrão.

---

## 13. Painel

### 13.1 Base

- FastAPI + Jinja2 + HTMX (ADR 0003). Páginas completas no primeiro acesso; trechos de HTML quando o pedido vem do HTMX (cabeçalho `HX-Request`).
- Todo filtro, aba, ordenação e busca vive na URL. GET nunca muda dados; toda mudança é POST.
- Paginação de 50 vagas, com botão "carregar mais" (DR-41).
- Um único arquivo de JavaScript próprio, `static/js/app.js`, sem script inline: tecla `/`, chave de tema, envio do token CSRF nos pedidos do HTMX e foco depois de cada troca de conteúdo.

### 13.2 Rotas

| Método | Rota | O que faz |
|---|---|---|
| GET | `/` | vai para `/primeira-execucao` ou `/vagas?aba=destaques` |
| GET | `/vagas` | lista; parâmetros: `aba`, `busca`, `q`, `area`, `nivel`, `modalidade`, `contrato`, `uf`, `fonte`, `encaixe`, `ordem`, `pagina` |
| GET | `/vagas/{id}` | detalhe |
| POST | `/vagas/{id}/status` | muda o status |
| POST | `/vagas/{id}/ocultar`, `/vagas/{id}/mostrar` | ocultar ou mostrar mesmo assim |
| GET, POST | `/vagas/{id}/correcao` | "Algo errado nesta vaga?" |
| POST | `/buscar-agora` | inicia a busca, ou devolve a que está rodando |
| GET | `/execucao/atual` | andamento (o HTMX pergunta a cada 2 s enquanto roda) |
| GET | `/fontes` | saúde das fontes |
| POST | `/fontes/{chave}/ligar`, `/fontes/{chave}/desligar` | |
| GET, POST | `/empresas`, `/empresas/testar`, `/empresas/{id}/…` | listar, testar, adicionar, ativar, remover |
| GET, POST | `/empresas/sugeridas`, `/empresas/sugeridas/{id}/aprovar`, `…/descartar` | Common Crawl |
| GET, POST | `/sites`, `/sites/{id}/…` | páginas acompanhadas |
| GET, POST | `/buscas`, `/buscas/{id}` | buscas salvas |
| GET, POST | `/configuracoes/{grupo}` | fontes, funções (as chaves da seção 13.7), segundo plano, idioma, tema, destaques, privacidade |
| POST | `/preferencias/tema`, `/preferencias/idioma` | troca rápida na casca do painel; grava as mesmas chaves `tema` e `idioma` da configuração |
| GET, POST | `/primeira-execucao/{passo}` | passos 1 e 2 |
| POST | `/sair` | encerra o servidor |
| GET | `/saude-local` | responde o nome e a versão do joBot; o `jobot abrir` pergunta aqui antes de abrir o navegador, para não abrir a página de outro programa que ocupe a porta (seção 12.6) |
| GET | `/static/…` | arquivos locais |

### 13.3 Abas (ADR 0008)

| Aba | O que mostra (DR-42) |
|---|---|
| Destaques de hoje | seção 11.4 |
| Todas | abertas, não ocultas, dentro do prazo |
| Novas | abertas, não ocultas, status "nova", vistas pela primeira vez nas últimas 72 horas |
| Fecham logo | prazo nos próximos 7 dias |
| Salvas | status "salva" (inclui fechadas, com selo) |
| Candidatei | status candidatei, entrevista, recusada e oferta, com chip por status |
| Programas | contrato trainee, programa, bolsa_pesquisa e concurso, mais as páginas acompanhadas |
| Ocultas | ocultas por regra ou à mão, com chip por motivo |

### 13.4 Lista, chips, busca e ordem

- **Chips com contagem:** área, nível, modalidade, contrato, UF, fonte e encaixe. A contagem de cada chip considera os outros filtros já escolhidos (DR-43). Chip com zero aparece apagado.
- **Busca:** campo de texto; a tecla `/` põe o foco nele (menos quando o foco já está num campo). Usa FTS5 (seção 7.3).
- **Ordenações:** encaixe (padrão), mais recentes, prazo mais próximo, maior salário, empresa A–Z.
- **Cartão da vaga:** título, empresa, locais, modalidade, salário (ou "não informado"), ● ◐ ○ com o primeiro motivo, selos (nova, fecha logo, fechada, avisos), faixa de 12 meses, "via <fonte>" com link, botões de status.
- **Salário em moeda estrangeira:** o valor original e, ao lado, menor e mais apagado, a cotação e o valor em reais. Exemplo: `US$ 5.000/mês` e, ao lado, `US$ 1 = R$ 5,65 (PTAX de 13/11) · ≈ R$ 28.250/mês`. O texto apagado mantém contraste de 4,5:1. Sem cotação, só o valor original.
- **Busca sem nenhum critério:** no lugar de ● ◐ ○, um aviso no topo: "diga o que você procura", com link para a busca. A ordem padrão vira "mais recentes".
- **Status:** nova → salva → candidatei → entrevista → recusada ou oferta (ADR 0008). Qualquer status pode voltar para o anterior.
- **Histórico:** salvar, ocultar, mostrar, mudar de status e desfazer gravam, cada um, uma linha em `evento`, com a data (seção 7.6). Nada disso aparece na tela na fase 1.

### 13.5 Detalhe da vaga

- Descrição em texto limpo (seção 14.3), salário e benefícios, rótulos, avisos, requisitos de estágio, todos os motivos do encaixe, palavras-chave encontradas, todos os links "ver na fonte" com "via <fonte>".
- **Salário:** como no cartão (seção 13.4), com a cotação e o valor em reais ao lado.
- **Candidatar:** o botão abre o `url_candidatura` da fonte, quando ela manda um (Himalayas), sem nenhuma mudança no endereço. Nas outras, abre a página da vaga na fonte. O joBot nunca se candidata sozinho.
- **Faixa de 12 meses:** 12 colunas, do mês atual em diante. Marca publicação (●), prazo (▲, em vermelho se faltam menos de 7 dias), início do programa (■) e hoje. Ao lado, o mesmo conteúdo em texto, para leitor de tela. Sem datas: "sem datas informadas".
- **"Algo errado nesta vaga?":** formulário com o campo (área, nível, modalidade, contrato, UF, salário, "já fechou", outro), o valor certo e um comentário opcional. Grava em `correcao` e aplica na hora.

### 13.6 Primeira execução (Q4)

- **Passo 1, preferências de busca:** cargos ou palavras-chave (lista com "adicionar"), cidades (com sugestão de UF), modalidades, níveis, salário mínimo mensal e moeda (padrão BRL), idiomas. Tudo opcional, com "pular". Cria a primeira busca.
- **Passo 2, segundo plano:** liga ou desliga, com explicação curta do que isso faz. Dentro de uma distrobox, diz em qual container o joBot vai rodar. Fora do Linux, aparece desativado.
- No fim: grava `primeira_execucao_concluida`, oferece "buscar agora" e vai para Destaques.
- Os outros passos da ADR 0011 entram nas fases deles (seção 3).

### 13.7 Configurações

Toda função tem chave liga/desliga (ADR 0001; resolução do dono). Um teste cobre cada chave (critério 26).

| Chave | Padrão | Desligada, o que acontece |
|---|---|---|
| Cada fonte (uma chave por fonte, agrupadas por leva) | ligada | a fonte não roda e aparece como "desligada" na saúde |
| Cada empresa | ligada | a empresa não é buscada |
| Descoberta pelo Common Crawl | ligada | a descoberta não roda; as sugestões já feitas continuam na tela |
| Páginas acompanhadas | ligada | nenhuma página é conferida |
| Enriquecimento | ligado | não busca a página de detalhe das vagas; as fontes de sitemap (Abler e Super Estágios) não trazem vaga nova |
| Destaques de hoje | ligado | a aba some e o painel abre em **Todas** |
| Conversão de moeda | ligada | nenhum pedido ao PTAX; só o valor original; a regra de salário não oculta vaga em outra moeda; o filtro e a ordem por salário continuam a valer para as vagas em BRL (seção 10.3) |
| Regras de ocultar (geral, e cada regra por busca) | ligadas | nada é ocultado por regra; a ocultação manual continua |
| Segundo plano | escolhido na primeira execução | o joBot não inicia sozinho |

Além das chaves:

- **Segundo plano:** status e o caso detectado (seção 12.5).
- **Idioma:** português ou inglês.
- **Tema:** sistema, claro ou escuro.
- **Destaques:** valor de N.
- **Buscas:** criar, editar, ativar, apagar; regras de ocultar de cada busca.
- **Privacidade:** onde ficam os dados, "sem telemetria" e a recomendação de criptografia de disco.

### 13.8 Saúde das fontes

Estados: ok, sem mudança, parcial, falhou, no limite e desligada. "No limite" mostra a hora em que a fonte, ou a empresa, pode rodar de novo.

Tabela com: fonte, último estado, quando, vagas trazidas, duração, motivo em linguagem simples, as últimas 8 execuções em bolinhas coloridas, a chave liga/desliga e a próxima execução. Fontes por empresa abrem a lista de empresas, cada uma com o seu estado.

### 13.9 Empresas

Lista com nome, área, ATS, identificador, ativa, último estado e "conferida em". Adicionar (com "testar" ao vivo), ativar, desativar e remover. A empresa removida sai da lista, mas a linha dela fica no banco, marcada (seção 8.6). Sub-aba **Sugeridas** (seção 8.7).

### 13.10 Idiomas

- Catálogos `i18n/pt.json` e `i18n/en.json`, com uma função `t(chave, **params)` nos templates. Sem Babel e sem gettext compilado (DR-44).
- Datas e dinheiro formatados por funções próprias para pt e en.
- Idioma inicial: pelo `Accept-Language` do navegador; depois, o escolhido nas configurações. `<html lang>` sempre certo.
- Teste: as duas línguas têm exatamente as mesmas chaves.

### 13.11 Visual (ADR 0008)

- Inspiração Apple, sem copiar texto nem recurso da Apple.
- Fonte: pilha de fontes do sistema com `-apple-system` primeiro (SF no Mac, sem arquivo da Apple no repositório) e Inter embutida para os outros sistemas.
- Inter **4.1**: arquivos `InterVariable.woff2` e `InterVariable-Italic.woff2` da versão oficial, licença SIL OFL 1.1, com o arquivo da licença junto (`OFL.txt`). O construtor anota o sha256 no momento de baixar (decisão da sessão principal).
- Translucidez com `backdrop-filter` na barra do topo e nos painéis; cantos arredondados; espaçamento generoso.
- Animações com efeito de mola, feitas em CSS (`linear()` como curva). Com `prefers-reduced-motion: reduce`, nada se mexe.
- Claro e escuro: segue `prefers-color-scheme`; a chave manual grava `tema` e o servidor já manda `<html data-tema="…">`, sem piscar.
- Cores em variáveis CSS, num lugar só. O teste do critério 29 lê esses pares.

### 13.12 Acessibilidade

- HTML semântico. As abas são links de navegação com `aria-current="page"`, porque cada aba é uma URL (DR-45).
- Chips são botões com `aria-pressed`.
- Link "pular para a lista", foco sempre visível, ordem de Tab lógica.
- Região `aria-live` para o andamento da busca e para avisos.
- Depois de cada troca de conteúdo do HTMX, o foco vai para um lugar previsível.
- Contraste mínimo de 4,5:1 nos dois temas; funciona com zoom de 200%.
- Ícones ● ◐ ○ sempre com texto ("bom", "médio", "fraco") para leitor de tela.

### 13.13 Nenhum recurso externo

HTMX **2.0.11** (versão fixa, sha256 anotado ao baixar, arquivo de licença junto) e a fonte Inter 4.1 são servidos de `/static`. Nenhum CDN, nenhuma imagem de fora (o CSP bloqueia, seção 14.2). Logos de empresas não aparecem (DR-46).

---

## 14. Segurança

### 14.1 Rede

- O servidor escuta só em `127.0.0.1`. O endereço de escuta é fixo no código e não aceita outro valor (ADR 0008 e 0014).
- `TrustedHostMiddleware` do Starlette aceita só `127.0.0.1:<porta>` e `localhost:<porta>`. Isso também barra o ataque de DNS rebinding.
- `server_header=False` e `proxy_headers=False` no uvicorn.

### 14.2 Cabeçalhos

```
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:;
  font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self';
  frame-ancestors 'none'
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
Cross-Origin-Opener-Policy: same-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

- O HTMX é configurado por `<meta name="htmx-config">` para não injetar estilos (`includeIndicatorStyles: false`), não usar `eval` (`allowEval: false`) e só falar com a própria origem (`selfRequestsOnly: true`). Os nomes exatos são conferidos no HTMX 2.0.11 antes de usar [a confirmar].
- O microfone volta a ser permitido só na fase 5.

### 14.3 Conteúdo de terceiros

- Descrição, título e empresa vêm de terceiros: **não confiáveis**.
- HTML e Markdown viram **texto puro** no núcleo (`texto.py`, com `html.parser` da biblioteca padrão): parágrafos e listas viram quebras de linha; scripts, estilos e atributos somem. O painel mostra só esse texto, com o autoescape do Jinja2 (DR-47).
- Links dentro da descrição não viram links clicáveis. Só os links "ver na fonte", "via <fonte>" e o de candidatura são clicáveis, e só se forem `http` ou `https`, com `rel="noopener noreferrer"` e `target="_blank"`. Nunca `nofollow` (a RemoteOK exige link sem ele).
- Autoescape do Jinja2 ligado em todos os templates. Um teste falha se `|safe` aparecer fora de uma lista curta e revisada.

### 14.4 Outras regras

- **CSRF** (DR-48): um token aleatório (`secrets.token_urlsafe`) gerado quando o servidor sobe, guardado só na memória. Vai numa `<meta>` da página e num campo escondido dos formulários; o `app.js` manda no cabeçalho `X-CSRF-Token` dos pedidos do HTMX. Todo POST confere o token com `hmac.compare_digest` e recusa `Sec-Fetch-Site: cross-site` e `Origin` diferente do painel. Token velho (servidor reiniciado) gera a mensagem "recarregue a página".
- **XML:** lido com `xml.etree` da biblioteca padrão, que usa o expat protegido contra "bomba de entidades" nas versões atuais, mais o limite de 5 MB da resposta (DR-49). O feed do Google tem perto de 20 MB: é lido em fluxo com `iterparse`, com teto próprio de 32 MB, e cada item é descartado depois de lido.
- **Sem telemetria.** O único código que faz pedidos para fora é o `HttpEducado`, usado só por coletores, descoberta, páginas acompanhadas e câmbio (um pedido por moeda por dia ao Banco Central, sem nenhum dado da pessoa). Um teste confere que `jobot.painel` não importa `httpx`.
- **Sem senhas e sem CAPTCHA** nesta fase: nenhuma fonte da fase 1 pede login. Fonte que passar a pedir login, CAPTCHA ou desafio anti-robô fica "falhou"; o joBot não contorna.
- Endereços digitados pela pessoa ("adicionar site", "adicionar empresa") passam pela validação da seção 8.8.

---

## 15. Qualidade, ferramentas e processo

### 15.1 Ferramentas

- `pyproject.toml` com `requires-python = ">=3.14"`, script `jobot = "jobot.cli:main"`, grupos de dependências do uv (`[dependency-groups] dev`).
- `uv.lock` versionado.
- **ruff:** `ruff check` e `ruff format`, com regras amplas (incluindo as de segurança, `S`, e de imports).
- **mypy:** `strict = true` em todo o `src/` e nos `tests/`.
- **pytest:** pastas `unidade/`, `integracao/` e `tela/`. Testes assíncronos com o plugin do `anyio`, que já vem com o Starlette e o httpx (DR-50).
- **Testes de tela:** Playwright com `pytest-playwright`, só como dependência de desenvolvimento. O servidor sobe numa porta livre, com banco temporário preenchido a partir das fixtures. A `fedora-dev` não tem Chrome: os testes usam o Chromium baixado pelo Playwright.
- **Relógio:** sempre injetado; nenhum teste espera tempo real.

### 15.2 Comandos (os mesmos na máquina e no CI)

Na máquina do dono, todos rodam dentro da `fedora-dev` (uv 0.12.3 e Python 3.14.6).

```
uv sync --locked
uv run ruff check
uv run ruff format --check
uv run mypy
uv run pytest
uv run playwright install chromium   # uma vez, dentro da fedora-dev, para os testes de tela
uv run jobot                          # abre o painel
```

### 15.3 CI

- `.github/workflows/ci.yml`: roda só em `pull_request` para a `main` (ADR 0016). Passos, com cache do uv: `uv sync --locked`, `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, `uv run playwright install --with-deps chromium` e `uv run pytest`. O CI **não** roda `uv run jobot`: esse comando sobe o servidor e abre o navegador, e o CI ficaria parado.
- Sem Dependabot (ADR 0021): a atualização de dependência é manual, no fim da fase. HTMX e Inter têm a versão e o sha256 de cada um anotados num arquivo ao lado deles.
- Como o CI só roda no fim da fase, cada junção na `dev` roda antes, na máquina, os mesmos comandos de verificação (ruff, mypy e pytest).

### 15.4 Processo (Q6 e Q7)

- Trabalho em ramos `feat/`, `fix/`, `docs/` e `ci/` saindo da `dev`; commits locais em português, no formato `tipo(escopo): descrição`; junção local na `dev`.
- Sem push durante a fase. No fim da fase, depois do roteiro do dono e das correções (seção 5.2), e só com o ok dele: push da `dev` e PR `dev` → `main` (Q6).
- Implementação por workflows com vários agentes, sempre em TDD: o teste falha primeiro, pelo motivo certo, e depois passa (Q7).

---

## 16. Dependências

Versões e licenças conferidas em 2026-11-13, com `uv pip compile --python 3.14`: tudo resolve sem conflito e nada compila do código-fonte. Todas as licenças são compatíveis com MIT. O construtor confere de novo cada licença na versão travada no `uv.lock` antes de juntar.

### 16.1 Execução

| Pacote | Versão | Para quê | Licença |
|---|---|---|---|
| `fastapi` | 0.162.7 | painel; traz `starlette` 1.10.0 e `pydantic` 2.14.3 | MIT (starlette BSD-3-Clause, pydantic MIT) |
| `uvicorn` (sem extras) | 0.54.0 | servidor HTTP do painel | BSD-3-Clause |
| `jinja2` | 3.1.6 | templates | BSD-3-Clause |
| `python-multipart` | 0.0.33 | o FastAPI precisa dele para ler formulários | Apache-2.0 |
| `httpx` | 0.28.1 | cliente HTTP dos coletores; também usado pelo `TestClient`; traz o `MockTransport` | BSD-3-Clause |
| `selectolax` | 1.0.2 | ler HTML com seletores na leva B (USP, IEL) e achar os blocos de dados embutidos (DR-57) | MIT |

Arquivos embutidos (não são pacotes Python):

| Arquivo | Versão | Origem | Licença |
|---|---|---|---|
| HTMX (`htmx.min.js`) | 2.0.11, a marcada como `latest` no npm (a 4.x ainda é `next`) | arquivo oficial da versão | 0BSD |
| Inter (`InterVariable.woff2` e a itálica) | 4.1 | pacote oficial da versão | SIL OFL 1.1, com o arquivo da licença junto |

Biblioteca padrão no lugar de pacote: `sqlite3` (sem ORM), `argparse` (sem click ou typer), `html.parser` (texto da descrição, sem bleach ou nh3), `xml.etree` (RSS e feed do Google), `decimal` (câmbio), `difflib`, `zoneinfo`, `fcntl`, `webbrowser`, `secrets`, `hmac`, `logging`, `json` (regras, casos de teste e i18n).

Conferidos e **não** usados na fase 1: `keyring` (entra na fase 3, com o primeiro segredo), ORM, `platformdirs`, `nh3`, `lxml`, `feedparser`, `babel`, `respx`, `apscheduler`. `playwright` como dependência de execução só se uma fonte futura exigir JavaScript (seção 8.5).

### 16.2 Desenvolvimento

| Pacote | Versão | Para quê | Licença |
|---|---|---|---|
| `pytest` | 9.2.0 | testes | MIT |
| `pytest-playwright` e `playwright` | 0.10.0 e 1.65.1 | testes de tela (o Chromium baixado passa de 100 MB) | Apache-2.0 |
| `mypy` | 2.4.1 | tipos | MIT |
| `ruff` | 0.17.5 | estilo | MIT |

Sem `pyyaml`: os casos de regras são JSON. Sem `pytest-asyncio`, sem `respx`, sem `freezegun`, sem `pytest-socket`: o `anyio`, o `httpx.MockTransport`, o relógio injetado e o `conftest.py` resolvem.

O que a conferência **não** fez: instalar e rodar os pacotes no Python 3.14, e olhar avisos de segurança (CVE). O bloco B0 faz os dois.

---

## 17. Ordem de construção

Blocos grandes; o plano detalhado sai depois.

| Bloco | O que entra | Depende de |
|---|---|---|
| B0. Esqueleto | `pyproject`, uv, ruff, mypy, pytest, guarda de rede, teste das camadas, CLI vazia, pasta de dados, migrações e esquema, CI, `.gitignore` com `dados_locais/`, instalação e importação de todas as dependências no Python 3.14 | — |
| B1. Núcleo de tratamento | modelo, texto, URL e hash, salário com casos em JSON, câmbio (conta e leitura do PTAX), rótulos, locais, estágio, duplicadas, ciclo de vida, encaixe, destaques (tudo puro e offline) | B0 |
| B2. Infra de coleta | `HttpEducado`, contrato, executor com saúde e falha isolada, `capturar.py`, teste "todo coletor tem fixture" | B0 |
| B3. Leva A | captura e coletor de cada fonte da seção 8.4 (um agente por fonte, em paralelo), começando pelo Greenhouse. A Gupy entra neste bloco (decisão do dono, revisão, Q6; seção 20.2). Lista inicial de 67 empresas carregada (apêndice, 7); crédito "via <fonte>" | B1, B2 |
| B4. Agenda e sistema | execução completa, travas por tipo, agendador, recuperação, instância única, `abrir`, `sair`, segundo plano Linux e atalho nos dois casos (direto e distrobox), com a conferência ao vivo na `fedora-dev` | B1, B2 |
| B5. Painel | segurança (Host, CSRF, CSP), layout, visual, temas, i18n, abas, chips, busca, detalhe, status, ocultas, histórico das ações em `evento` (seção 7.6), faixa de 12 meses, "Algo errado", configurações com todas as chaves, saúde, empresas, buscas, primeira execução, salário com cotação, testes de tela | B0, B1 (dados de exemplo das fixtures) |
| Marco interno | a leva A funciona de ponta a ponta na rede real, na `fedora-dev` do dono | B3, B4, B5 |
| B6. Leva B | coletores da seção 8.5 (Abler e Eureca por último; a Eureca começa por achar o caminho público na captura), empresas da leva B conferidas, descoberta Common Crawl e tela de sugeridas, páginas acompanhadas e tela | marco interno |
| B7. Conjunto de ouro | as 329 vagas já coletadas, rotuladas fora do repositório (rotulagem orquestrada pela sessão; seção 10.7), `avaliar-rotulos` com o caminho por argumento, ajuste das regras, números em `docs/rotulos-medidos.md` | B1 (a rotulagem não espera coletor: as vagas já estão coletadas) |
| B8. Fechamento | suíte inteira; roteiro do dono na `fedora-dev` (seção 5.2) e correção do que ele estranhar; README (com o aviso de uso pessoal e de termos das fontes, seção 20.2) e CHANGELOG atualizados; por último, só com o ok do dono, push da `dev` e PR `dev` → `main` | todos |

---

## 18. Decisões do redator

Cada uma pode ser trocada pelo dono. Três números saíram nesta revisão (DR-13, DR-23 e DR-26), porque o dono decidiu o contrário; eles não são reaproveitados. As decisões novas começam em DR-51.

| Nº | Decisão |
|---|---|
| DR-01 | Pelo menos 60 casos de salário no arquivo JSON |
| DR-02 | Idioma da vaga por contagem de palavras comuns (pt, en, es, outro) |
| DR-03 | `sqlite3` da biblioteca padrão, sem ORM |
| DR-04 | Várias buscas salvas já na fase 1; encaixe e ocultação por busca; status por vaga; seletor de busca na URL (confirmada pelo dono) |
| DR-05 | Busca com FTS5; sem FTS5, `LIKE` |
| DR-06 | Cópia do banco antes de migrar, guardando as 3 últimas |
| DR-07 | Pasta de dados calculada sem `platformdirs`; `JOBOT_DADOS` para testes |
| DR-08 | Item fora do formato é pulado e deixa o escopo "parcial" |
| DR-09 | Até 4 hosts em paralelo, um pedido por vez no mesmo host |
| DR-10 | "Zero inesperado" vira "parcial" e não fecha vagas |
| DR-11 | Valores da coleta educada: formato do user agent, 1 s por host, tempos limite, 5 MB, teto de 10 min no `Retry-After`, esperas sem o cabeçalho |
| DR-12 | Como o 304 é tratado: validadores na tabela `cache_http`; estado "sem_mudanca"; escopo paginado só é "sem_mudanca" se todas as páginas derem 304; validadores gravados na mesma transação das ocorrências do escopo; sem pedido condicional em escopo sem ocorrência aberta |
| DR-13 | **Retirada.** Era "respeitar `robots.txt`". O dono decidiu que `robots.txt` não bloqueia a coleta |
| DR-14 | "via <fonte>" aparece em todas as fontes, não só nas cinco que exigem |
| DR-15 | Login do autor da issue do GitHub não é guardado |
| DR-16 | Ordem de preferência de caminho: JSON da página, dados embutidos ou HTML, Playwright só com aprovação. Na fase 1 nenhuma fonte usa Playwright |
| DR-17 | Empresas descobertas pelo Common Crawl só entram com aprovação da pessoa (confirmada pelo dono) |
| DR-18 | Páginas acompanhadas conferidas uma vez por dia |
| DR-19 | "Adicionar site" recusa endereços locais e de rede privada |
| DR-20 | Fixtures com no máximo 5 itens e 50 KB |
| DR-21 | Guarda de rede própria no `conftest.py` |
| DR-22 | Regras em JSON, com expressões regulares no subconjunto comum de Python e JavaScript |
| DR-23 | **Retirada.** Era a segunda chave de duplicadas. Vale só o hash da URL (ADR 0007) |
| DR-24 | Vaga fechada com status da pessoa continua em Salvas e Candidatei; nada é apagado |
| DR-25 | Conversões para mensal e faixas de salário plausível |
| DR-26 | **Retirada.** Era "sem conversão de câmbio". O dono decidiu converter pelo PTAX |
| DR-27 | Listas de valores de área, nível, contrato e avisos |
| DR-28 | Limite do enriquecimento: 50 por fonte, 200 por execução |
| DR-29 | A proporção de vagas no Brasil no conjunto de ouro é medida e registrada em `docs/rotulos-medidos.md`. Não é exigência: o gabarito está fechado e nenhuma vaga é coletada a mais (seção 10.7) |
| DR-30 | País da pessoa = país das cidades informadas |
| DR-31 | Pesos da nota e limites 70 e 40 |
| DR-32 | Na fase 1, o detalhe mostra as palavras-chave encontradas, no lugar de habilidades |
| DR-33 | Regras de ocultar ligadas por padrão, desligáveis por busca, mais uma chave geral |
| DR-34 | Destaques: novas das últimas 24 horas, N = 10 (confirmada pelo dono) |
| DR-35 | Painel e agenda no mesmo processo; agendador de 60 em 60 s; espera de 60 s na recuperação |
| DR-36 | Travas: arquivo por instalação; índice único no banco e `asyncio.Lock`, um por tipo de execução |
| DR-37 | Atalho `.desktop` criado sempre, mesmo sem segundo plano |
| DR-38 | "Iniciar com o computador" = iniciar ao entrar na sessão, sem linger (confirmada pelo dono) |
| DR-39 | Botão "Sair" para encerrar o servidor |
| DR-40 | Porta fixa 47615, trocável por `JOBOT_PORTA` |
| DR-41 | Páginas de 50 vagas, com "carregar mais" |
| DR-42 | Regras de cada aba (72 h em Novas, 7 dias em Fecham logo, tipos em Programas, sub-status em Candidatei) |
| DR-43 | Contagem dos chips considera os outros filtros |
| DR-44 | i18n com catálogos JSON próprios, sem Babel |
| DR-45 | Abas como links de navegação, não como componente ARIA de abas |
| DR-46 | Sem logos de empresas |
| DR-47 | Descrição sempre convertida para texto puro, sem HTML |
| DR-48 | CSRF com token do processo, cabeçalho para o HTMX e conferência de `Origin` e `Sec-Fetch-Site` |
| DR-49 | XML com `xml.etree`, sem `defusedxml`; feed grande lido em fluxo |
| DR-50 | Testes assíncronos com o plugin do `anyio` |
| DR-51 | `HttpEducado` com um método só (`pedir`) e leitura em fluxo; user agent fixo; lista curta de cabeçalhos permitidos; `Origin`, `Cookie`, `Authorization` e `Referer` nunca saem (seção 8.2) |
| DR-52 | Orçamento de pedidos por fonte e rodízio de escopos, com o estado "no limite". Valor da Gupy: 30 pedidos por execução, 2 s entre eles, como a conferência ao vivo recomendou (seções 8.1 e 8.3) |
| DR-53 | Fonte mundial com filtro de país pede só os países das buscas ativas (seção 8.1) |
| DR-54 | Câmbio: cotação de venda do fechamento, janela de 7 dias, só as moedas que aparecem em vaga aberta; o salário mínimo da busca também vira reais; o valor convertido é guardado em reais inteiros, arredondado para o real mais próximo (seções 7.3 e 10.3) |
| DR-55 | Nota com critério vazio: 100 × pontos ÷ soma dos pesos preenchidos. Sem nenhum critério, a nota fica vazia (seção 11) |
| DR-56 | Segundo plano na distrobox: `ExecStart` com `distrobox-enter`, `ExecStop` com `jobot sair`, navegador por `distrobox-host-exec xdg-open`, e recusa quando a pasta pessoal do container não é a do sistema (seção 12.5) |
| DR-57 | `selectolax` no lugar do `beautifulsoup4` para ler HTML: foi o pacote conferido para o Python 3.14 (seção 16.1) |
| DR-58 | Números medidos em `docs/rotulos-medidos.md` (seção 10.7). O resto desta decisão foi trocado em 2026-11-13: o gabarito fica fora do repositório, o caminho vai por argumento, e a tela "Conferir rótulos" saiu da fase 1 (DR-67) |
| DR-59 | A mesma vaga publicada com URLs diferentes fica em linhas separadas. É consequência de usar só o hash da URL (seção 10.1) |
| DR-60 | Gupy com dois tipos de escopo: por empresa da lista e por cargo das buscas (seção 8.4) |
| DR-61 | As 3 horas contam do **início** da última busca completa (seção 12.2) |
| DR-62 | Lista das chaves liga/desliga e o que cada uma faz quando desligada; Destaques desligado esconde a aba (seção 13.7) |
| DR-63 | Casos de regras em `tests/casos/*.json`; `avaliar-rotulos` sai sem erro quando o caminho do gabarito não existe (seções 10.3 e 10.7) |
| DR-64 | Limite próprio de um escopo (`por_escopo`: intervalo, espera e parada no 429), usado pela Microsoft dentro do Eightfold; o intervalo conta pela `saude`, sem coluna nova; escopo "no_limite" não muda o estado da fonte quando outros escopos rodaram (seções 8.1 e 8.3) |
| DR-65 | Colunas `pais` e `parametros` (JSON) na tabela `empresa` já na primeira migração; chaves de cada ATS da leva B; método opcional `resolver` no coletor (seções 7.3, 8.1 e 8.6) |
| DR-66 | Como o histórico de ações é guardado: tabela `evento` com cinco valores de `acao`; toda volta para o status anterior é `desfez`, e `salvou` vale só de "nova" para "salva"; gatilhos que recusam `UPDATE` e `DELETE`; "descartar" é o "ocultar" à mão, porque o painel da fase 1 não tem botão de descartar separado; as correções ficam só em `correcao`; o texto bruto da vaga fica em `ocorrencia.coletada`, sem coluna nova (seção 7.6) |
| DR-67 | Trocada em 2026-11-13: a tela "Conferir rótulos" saiu da fase 1. Ela existia para o dono avaliar as regras, e o dono trocou essa avaliação pelo gabarito rotulado por modelos. Saem a rota, a tabela do banco, os textos de i18n e o passo 22 do roteiro. O dono não confere amostra do gabarito (seções 5.2 e 10.7) |
| DR-68 | Coluna `removida_em` na tabela `empresa`, já na primeira migração: remover marca a linha, não apaga. A carga da lista inicial pula a linha marcada, a coleta a ignora e a descoberta não a sugere de novo. Adicionar de novo a mesma empresa limpa a marca (seções 7.3 e 8.6) |
| DR-69 | Reforço da guarda para a fase 6: ao gravar de novo uma ocorrência, a descrição vazia da listagem não substitui a que veio do `detalhar`; um gatilho recusa `DELETE` em `vaga`; vaga, ocorrência e empresa são gravadas sempre com `INSERT ... ON CONFLICT(...) DO UPDATE`, nunca com `INSERT OR REPLACE` nem `REPLACE`, que apagam a linha antiga sem disparar o gatilho e deixam as cascatas rodar; o `vaga_fts` não tem gatilho de `DELETE`, que seria código morto; e toda migração roda com `foreign_keys` desligado e `foreign_key_check` antes do `COMMIT`, para a reconstrução de uma tabela não apagar os filhos em cascata (seções 7.3, 7.4, 7.6 e 12.4) |
| DR-70 | Fontes de sitemap (Abler e Super Estágios) devolvem `UrlListada(url, atualizada_em)` em vez de `VagaColetada`, e devolvem todas as URLs do sitemap. URL que já tem ocorrência dessa fonte no banco conta como vista no ciclo de vida, com qualquer data. O filtro de 30 dias vale só para URL nova e é do executor. URL nova vai para o `detalhar`, dentro do orçamento de enriquecimento (50 por fonte), as mais recentes primeiro, e só é gravada se o detalhe trouxer título e empresa; o resto espera a próxima execução. Detalhe sem título ou sem empresa fica no cache `enriquecimento` e não volta ao `detalhar` por 30 dias, sem mudar o estado do escopo. A `VagaColetada` continua a exigir `titulo` e `empresa`. Era o ponto PA-1 do plano, aceito pela sessão em 2026-11-13 (seções 8.1, 8.5, 10.2, 10.6 e 12.4) |

---

## 19. O que fica para o construtor decidir

- Nomes internos de funções, classes e arquivos, desde que as camadas da seção 6.1 valham.
- Desenho fino das telas (CSS, espaçamentos, cores exatas), dentro da seção 13.11 e do contraste mínimo.
- Termos e pesos de cada valor em `rotulos.json`, ajustados contra o conjunto de ouro.
- Ajuste fino dos pesos do encaixe dentro da seção 11.2, se o conjunto de ouro ou o teste do dono mostrarem algo melhor (mudança registrada no `duvidas.md`).
- Formato do log e mensagens de erro técnicas.
- Como dividir templates e trechos do HTMX.
- Para cada fonte: detalhes de leitura que o apêndice não fixa (por exemplo, quantas páginas ler por execução dentro do orçamento, e o uso ou não do `detalhar`).
- A opção `--no-tty` do `distrobox-enter`, depois da conferência ao vivo (seção 12.5).
- Divisão do trabalho entre agentes dentro de cada bloco.

O que **não** fica para o construtor (vai para o `duvidas.md`, com opções e recomendação): dependência nova, mudança de contrato do coletor, mudança de esquema fora das migrações, Playwright como dependência de execução, fonte nova ou fonte que perdeu o caminho público, endereço diferente do apêndice, qualquer coisa das seções 3 e 4.

---

## 20. Decisões do dono, pontos em aberto e riscos

### 20.1 O que o dono já decidiu nesta revisão

Os pontos P1 a P11 da versão anterior deste desenho estão todos decididos. Nada aqui espera resposta.

| Assunto | Decisão do dono | Onde está no desenho |
|---|---|---|
| `robots.txt` (revisão, Q1) | Não bloqueia a coleta. A coleta continua educada: user agent honesto, intervalo, 429 e `Retry-After`, limites documentados. Nunca contornar login, CAPTCHA ou bloqueio | 8.2 |
| Onde o joBot roda (revisão, Q2) | Dentro da distrobox `fedora-dev`. O segundo plano funciona nos dois casos: direto no sistema e dentro da distrobox. O roteiro de teste roda na `fedora-dev` | 5.2, 12.5 |
| Rótulo abaixo de 90% (revisão, Q3) | A fase 1 mede e registra; não impede o fechamento. O multilingual-e5-small vai para a fase 3 | 5.1, 10.7 |
| Conjunto de ouro (revisão, Q4) | Só no computador, fora do git. Para o GitHub vão só as regras e os números. O CI usa fixtures pequenas, sem dado pessoal. Quem rotula e quem confere mudou em 2026-11-13 (seção 20.2) | 10.7 |
| Moeda (revisão, Q5) | Converter para reais pelo PTAX, um pedido por dia, com cache. O filtro usa o valor convertido. Na tela, a cotação e o valor em reais ao lado, menores e mais apagados. Sem cotação, só o original, e a vaga não é eliminada | 10.3, 13.4 |
| Atribuição | "via <fonte>" com link; RemoteOK sem `nofollow`; Himalayas com o `applicationLink` | 8.2, 13.5 |
| Resposta 304 | Conta como "sem mudança": mantém as ocorrências abertas e nunca fecha vaga | 8.1, 10.2 |
| Buscar agora | Busca tudo na hora. Intervalo mínimo só para a fonte cujos termos ou limites exigem. Em 2026-11-13 a sessão deu intervalo prático a mais quatro fontes (seção 20.2) | 8.3, 12.2 |
| Fonte da leva B sem caminho público | Fica fora, com o motivo no `duvidas.md`, e a fase fecha | 8.5 |
| Várias buscas salvas | Já na fase 1 | 11.1 |
| Travas | Uma por tipo de execução. Descoberta e páginas nunca seguram a busca | 12.3 |
| Agenda | 3 horas a partir da última busca completa, da agenda ou do "buscar agora" | 12.2 |
| Casos de teste de regras | Em JSON. O teste em JavaScript fica para a fase 7. Sem PyYAML | 10.3, 16.2 |
| Busca sem preferências | Critério vazio é neutro. Sem nenhum critério, o painel pede as preferências e os Destaques saem por data | 11 |
| Lista de empresas | 67 empresas já conferidas. O dono revê pelo painel depois | 8.6; apêndice, 7 |
| Duplicadas | Só pelo hash da URL | 10.1 |
| Chaves | Toda função tem liga/desliga | 13.7 |
| Playwright | Só nos testes. Nenhuma fonte conferida precisa de JavaScript | 8.5, 16 |
| Destaques, segundo plano, Common Crawl, keyring e ORM | N = 10 em 24 horas; inicia ao entrar na sessão, sem linger; Common Crawl ligado, com aprovação de cada empresa; sem keyring e sem ORM na fase 1 | 11.4, 12.5, 8.7, 16 |
| Versões | As conferidas na seção 16; HTMX 2.0.11; Inter 4.1 | 16 |

### 20.2 Pontos em aberto: decididos em 2026-11-13, depois da revisão

Nenhum ponto espera resposta do dono. As marcas de espera saíram do desenho e do apêndice.

**Termos de uso (revisão, Q6): decidida pelo dono em 2026-11-13**

| Fonte | O que os termos dizem | Decisão do dono |
|---|---|---|
| Meta | proíbem coleta automática sem permissão por escrito | **fora** |
| Eureca | pedem consentimento prévio e expresso | **dentro** |
| Gupy | proíbem "agregar, copiar ou duplicar partes" do serviço; não falam de coleta automática de forma explícita | **dentro** |
| Abler | proíbem reproduzir o conteúdo sem autorização | **dentro** |
| As outras | nada achado contra o uso descrito aqui; as cinco da seção 8.2 pedem crédito e link | **dentro** (já estavam) |

Eureca, Abler e Gupy entram, cada uma com:

- chave liga/desliga (seção 13.7);
- ritmo educado (seções 8.2 e 8.3);
- link para a vaga original, sempre. O joBot não republica nada;
- aviso no README: o joBot é de uso pessoal, roda no computador de cada pessoa, e cada pessoa é responsável por respeitar os termos das fontes que deixar ligadas. Um teste confere o aviso (critério 35).

A Eureca ainda não tem caminho conferido (seções 8.5 e 20.3).

O apêndice leu a documentação das APIs do Greenhouse e da Lever, mas não os termos de uso gerais das duas. Fica na lista da seção 20.3.

**Outras decisões de 2026-11-13**

| Assunto | Decisão | Onde está |
|---|---|---|
| Gabarito | 329 vagas reais já coletadas, fora do repositório. O comando de medição recebe o caminho por argumento. Agentes Sonnet rotulam; o Fable rotula de novo, às cegas, e decide onde houver discordância, registrando o porquê. O dono não confere amostra. O gabarito nunca entra em dados de treino | 5.1 (critério 20), 10.7 |
| Guarda para a fase 6 | Desde o primeiro dia: texto completo de toda vaga (texto puro e HTML bruto), sem apagar vaga fechada ou antiga; e histórico das ações da pessoa no painel, com data, numa tabela só de acréscimo | 5.1 (critérios 33 e 34), 7.3, 7.6, 10.2 |
| Intervalos práticos (decisão da sessão) | Google 1440 min, Himalayas 1440, RemoteOK 360 e Amazon 360. Não é exigência dos termos. Remotive 360, Jobicy 60 e We Work Remotely 60 continuam. O "buscar agora" respeita o `intervalo_min` | 8.3, 8.4, 8.5; apêndice |
| Treino de modelos (fase 6) | Decisão reescrita na ADR 0015. Na fase 1, só a guarda dos dados | 7.6; ADR 0015 |
| Descartar (o dono delegou) | Fica a DR-66: na fase 1, descartar é ocultar à mão (evento `ocultou`); o `mostrou` registra o "mostrar mesmo assim". Sem botão novo | 7.6 |
| Tela "Conferir rótulos" (o dono delegou) | Sai da fase 1, com a rota, a tabela, os textos de i18n e o passo 22 do roteiro. A avaliação das regras é a do gabarito rotulado por modelos (DR-67) | 5.2, 10.7, 13.2 |
| Regravar sem `REPLACE` (o dono delegou) | Vaga, ocorrência e empresa sempre com `INSERT ... ON CONFLICT(...) DO UPDATE`. O `vaga_fts` fica sem gatilho de `DELETE` (DR-69) | 7.3, 7.6, 12.4 |
| Salário em reais (o dono delegou) | O valor convertido (`sal_mensal_min_brl` e `sal_mensal_max_brl`) é guardado em reais inteiros, arredondado para o real mais próximo. As assinaturas dizem a unidade | 7.3, 10.3 |
| Salário sem símbolo de moeda (o dono delegou) | Vaga em português → BRL; em inglês → USD; outro idioma → não lê (decisão DP4 do plano) | 10.3 |
| Fontes de sitemap (o dono delegou) | Abler e Super Estágios devolvem `UrlListada`; a vaga só é gravada depois do `detalhar`, com título e empresa (DR-70) | 8.1, 8.5, 10.2, 10.6 |
| Roteiro antes do PR (o dono delegou) | O roteiro do dono na `fedora-dev` vem antes do PR `dev` → `main`. O que ele estranhar vira correção antes do PR. Push da `dev` e PR só com o ok do dono | 5.2, 15.4, 17 |
| Arquivos do gabarito (conferidos pela sessão) | Bruto: `g1.jsonl`, `g2.jsonl` e `g3.jsonl`, com as mesmas chaves de topo; `metadados` é livre e a medição não depende dele. Rotulado: `rotulos.jsonl`, uma linha por vaga. A proporção de vagas no Brasil é contada pelo `avaliar-rotulos`, pelo campo `pais` | 10.7 |
| Decisões do plano (o dono delegou) | DP1, DP2, DP4, DP5, DP6 e DP7 do plano aceitas pela sessão. A DP4 é regra de produto e está na seção 10.3 | plano; 10.3 |
| Valor em reais da vaga em BRL e chave de conversão (decisão da sessão) | Vaga em BRL tem `_brl` = centavos ÷ 100, sem cotação e mesmo com a conversão desligada. Com a chave desligada, os `_brl` das vagas em moeda estrangeira voltam a `NULL`. O mínimo da busca é guardado em centavos da moeda dela | 7.3, 10.3, 12.4, 13.7 |
| Migração e chave estrangeira (decisão da sessão) | Toda migração roda com `foreign_keys` desligado e `foreign_key_check` antes do `COMMIT` | 7.4 |
| Decisões do redator mantidas (o dono delegou) | `selectolax` (DR-57); mesma vaga com URLs diferentes em linhas separadas (DR-59); Gupy com 30 pedidos por execução e escopo por empresa e por cargo (DR-52 e DR-60); 3 horas contadas do início da última busca completa (DR-61); "via <fonte>" em todas as fontes (DR-14). A menção ao Claude Code na fase 3 fica: é recurso do produto, não atribuição | 18 |

### 20.3 Fatos ainda a confirmar

A conferência ao vivo de 2026-11-13 confirmou os endereços, os campos e os limites das fontes, os cinco repositórios do GitHub, as 67 empresas, o PTAX, as versões e as licenças. Sobrou isto:

| O que falta | Quem confere | Onde |
|---|---|---|
| Primeiro pedido de cada fonte com o user agent do joBot (parte da conferência usou um user agent genérico) | construtor, na captura | 9.2; apêndice, 1 e 8 |
| Parâmetro `careerPageName` da Gupy, para buscar por empresa | construtor, bloco B3 | 8.4; apêndice, 2.5 |
| Caminho público da Eureca: endereço, método, paginação, campos e limites | construtor, bloco B6, na captura | 8.5; apêndice, 3.2 |
| `distrobox-enter` rodando sem terminal dentro do systemd, e a parada pelo `jobot sair` | construtor, começo do bloco B4, na `fedora-dev` | 12.5 |
| Nomes de configuração do HTMX 2.0.11 (`includeIndicatorStyles`, `allowEval`, `selfRequestsOnly`) | construtor, bloco B5 | 14.2 |
| sha256 do HTMX e da Inter | construtor, ao baixar | 13.13 |
| Pacotes instalam e rodam no Python 3.14; avisos de segurança (CVE) | construtor, bloco B0 | 16 |
| Bibliotecas de sistema que o Chromium do Playwright pede na `fedora-dev` | construtor, bloco B0 | 15.1 |
| Licença da lista de municípios do IBGE | construtor, bloco B1 | 10.4 |
| Termos de uso gerais do Greenhouse e da Lever (só a documentação das APIs foi lida) | construtor, antes do bloco B3 | apêndice, 2.4 e 8 |
| Demais itens de fonte (formato do Super Estágios em mais vagas, valores do campo `remote` da Recrutei, e outros) | construtor, na captura | apêndice, 8 |

### 20.4 Riscos

| Risco | Efeito | Como reduzir |
|---|---|---|
| Eureca sem caminho público conferido | a fonte pode ficar fora | achar o caminho na captura (bloco B6); sem caminho público, sai com o motivo no `duvidas.md` e a fase fecha (seção 8.5) |
| Nada é apagado (seção 7.6) | o banco cresce com o tempo | texto de vaga é pequeno; olhar o tamanho do `jobot.db` na semana de testes e registrar |
| Endereço interno, sem contrato publicado (Gupy, Amazon, Eightfold, Workday, portais) | fonte quebra sem aviso | coletor valida o formato; saúde visível; "zero inesperado"; registrar no `duvidas.md` |
| Fonte passa a bloquear o joBot (403, login, CAPTCHA) | fonte fica "falhou" | o joBot não contorna; a pessoa vê na saúde e desliga a fonte |
| `distrobox-enter` dentro do systemd: pede terminal, demora a subir o container no login, ou deixa o servidor rodando depois de parar o serviço | segundo plano não liga, liga tarde ou não desliga | conferir ao vivo no começo do B4; `--no-tty`; `ExecStop` com `jobot sair`; `Restart=on-failure` |
| Distrobox com pasta pessoal própria | o serviço escrito não é visto pelo sistema | "ligar" recusa com mensagem clara |
| Chromium do Playwright sem as bibliotecas de sistema na `fedora-dev` | testes de tela não rodam na máquina do dono | conferir no B0; instalar as bibliotecas na distrobox |
| Limite de 60 pedidos por hora do GitHub, por IP | issues param de chegar depois de várias buscas seguidas | pedidos condicionais, poucas páginas, estado "no limite" |
| Limites não publicados (Himalayas, RemoteOK, Google, Amazon, Gupy) | bloqueio temporário | intervalo prático nas quatro primeiras (seção 8.3), pedido condicional, orçamento de pedidos, espera entre pedidos, obediência ao 429 |
| Respostas grandes (feed do Google, índice do Common Crawl) | memória e tempo | leitura em fluxo, teto próprio; o feed do Google é pedido no máximo uma vez por dia e usa `If-Modified-Since`; o índice só é lido quando há índice novo |
| PTAX fora do ar, ou moeda fora das 10 | vaga sem valor em reais | usa a última cotação dos 7 dias; sem cotação, mostra o original e não oculta |
| Mesma vaga com URLs diferentes | linhas repetidas na lista | limite aceito (ADR 0007); a pessoa oculta à mão |
| Python 3.14 sem pacote pronto de alguma dependência | instalação falha | a resolução já passou; instalar e importar no B0, antes de tudo |
| Leitura do "Who is hiring" por heurística | empresa ou local errados | casos de teste com capturas reais; conjunto de ouro |
| Conjunto de ouro dá trabalho | atraso no fim da fase | as 329 vagas já estão coletadas; a rotulagem é feita por agentes e não espera coletor; abaixo de 90% não impede o fechamento |
| Conjunto de ouro ou amostra real indo para o git por engano | dado pessoal publicado | o gabarito fica fora da pasta do repositório; `dados_locais/` no `.gitignore`; teste do critério 21 |
| SQLite sem FTS5 | busca mais lenta | `LIKE` como reserva |
| CI só no fim da fase | erro de CI aparece tarde | mesmos comandos na máquina a cada junção |
| Porta 47615 ocupada | painel não abre | mensagem clara; `JOBOT_PORTA` |
| Lista de municípios do IBGE com licença incerta | menos precisão em cidade | usar só UFs e capitais até confirmar |
