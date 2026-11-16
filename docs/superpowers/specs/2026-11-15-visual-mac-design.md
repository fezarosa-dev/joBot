# Visual de app do Mac: desenho

Data: 2026-11-15, revisto em 2026-11-16. Decisões de origem: ADR 0008 (painel e visual, com a nota "Visual de app do Mac e botões da janela"), ADR 0016 (sala limpa), D139 (Contas), D140 (visual de app do Mac), D142 (app de desktop na fase 3), as duas rodadas de respostas do dono de 2026-11-15 e a terceira, de 2026-11-16 (progresso, lateral, linha da vaga e o que fica fora). As decisões novas ficam em `duvidas.md` como D143.

Este documento é a especificação para planejar e construir o lote do visual novo sem voltar ao dono. Todo fato sobre o código vem com `arquivo:linha`, conferido na árvore da `dev` em 2026-11-15 e 2026-11-16. As linhas podem andar: quando a linha não bater, procure pelo nome. As lições de `registros/padroes.md` são citadas pelo rótulo, como `padroes.md («CSS e template»)`.

Cada decisão leva o número da lista completa da seção 11 (D143.1 a D143.71). As decisões 1 a 20 e 55 a 60 são do dono; as outras são da sessão, para confirmar com o dono. Nenhuma pergunta aberta trava o plano (seção 10). As regras da Apple são ditas com as nossas palavras e apontam a página pública das Human Interface Guidelines (HIG), em `https://developer.apple.com/design/human-interface-guidelines/<pagina>`. Nenhum texto, imagem, fonte ou símbolo da Apple entra no repositório (ADR 0016).

**Valores.** A HIG quase não dá números. Todo valor marcado "(proposta)" foi escolhido por nós, sem medição num Mac. Os valores propostos valem para construir agora (D143.31, para confirmar com o dono); eles serão conferidos depois num Mac com o Medidor de Cores Digital. A lista inteira está no fim da seção 11.

## 1. Intenção e porquê

O dono quer que o joBot pareça um app de Mac: a janela organizada como o Mail, as Configurações como os Ajustes do Sistema, o material translúcido da Apple e a tipografia do Mac. Hoje o painel é uma página da web com estilo Apple: um cabeçalho translúcido no alto com 7 links, os seletores de tema e idioma, "Buscar agora" e "Sair" (`src/jobot/painel/templates/base.html:39-62`), texto de 17px (`src/jobot/painel/static/css/base.css:76`) e cartões de conteúdo com vidro (`base.css:322`).

O visual novo muda a casca, os tokens e as telas, mas não muda o que o joBot faz nem os endereços das páginas. Tudo continua renderizado no servidor e funcionando sem JavaScript; o JavaScript só acrescenta atalhos, a paleta de comandos, o menu de contexto, recolher a barra lateral e o cinza da janela inativa.

## 2. Objetivos, não objetivos e anti-objetivos

**Objetivos**

- Janela no estilo do Mail: barra lateral, barra de ferramentas, lista e detalhe (D143.3).
- Tokens de cor, tipo, espaço, raio, vidro, sombra e movimento num lugar só, em `base.css`.
- Texto do Mac (13px em controles e listas) com opção de tamanho em Configurações (D143.12).
- Tema Sistema, Claro ou Escuro escolhido pela pessoa, agora em Configurações > Geral (D143.13, D143.21).
- Desfazer no lugar de pergunta de confirmação para ações que dá para desfazer (D143.16).
- Paleta de comandos e menu de contexto no lugar de uma barra de menus (D143.15).
- Janela no modo app do navegador (D143.6).
- Mesmo visual no Mac, no Windows e no Linux; só a fonte muda (D143.19).
- Um componente único de progresso para toda espera de mais de 1 s, fiel ao andamento real e com a etapa escrita (D143.55 a D143.57; seção 5.9).

**Não objetivos**

- A janela própria em Tauri e os botões de janela desenhados (fase 3, D142).
- A API de notificações do navegador e desconectar um site só. O dono viu e aceitou deixar os dois de fora (D143.60): o aviso do agendador pelo `notify-send` já cobre, e "Esquecer logins" já existe.
- Parar uma busca no meio pelo progresso (D143.71).
- Seleção de várias vagas e ações em lote (D143.27).
- Cor de destaque escolhida pela pessoa, tamanhos pequeno e grande da barra lateral e reordenar itens (D143.48).

**Anti-objetivos**

- Desenhar botões de janela ou barra de título dentro da página antes da casca da fase 3, e barra de menus falsa em qualquer fase (D143.11, D143.15).
- Copiar texto, imagem, a fonte SF Pro ou os SF Symbols da Apple (ADR 0016).
- Carregar qualquer recurso de fora de 127.0.0.1 (a CSP está em `src/jobot/painel/app.py:19-20`).
- Vidro na camada de conteúdo ou vidro sobre vidro (D143.25).

## 3. Restrições

- O painel escuta só em 127.0.0.1 e não carrega recurso externo. A Inter já está embutida em `src/jobot/painel/static/fontes/` com `OFL.txt` e `inter.meta.json`; o Lucide entra do mesmo jeito (D143.8).
- Cor nova vira token em `:root` de `base.css`, em `light-dark(#claro, #escuro)`, com o par de contraste no comentário `/* contraste: ... */` (`base.css:25`), nos dois temas, em hex de 6 dígitos (`padroes.md («CSS e template»)`). O teste `tests/unidade/test_contraste.py` exige 4,5:1 em todo par.
- `backdrop-filter` ou `transform` num ancestral prende `position: fixed`: camada que flutua sobre a página usa `<dialog>` (`padroes.md («CSS e template»)`).
- `opacity: 0` pede `pointer-events: none`; `appearance: none` pede bloco `forced-colors`; o bloco de movimento reduzido fica no fim do arquivo (`padroes.md («CSS e template»)`).
- O `role='alert'` da casca usa aspas simples (`base.html:68-71`); o teste procura assim.
- Texto novo entra nos catálogos `pt` e `en` com as mesmas chaves (`tests/unidade/test_i18n.py`).
- Gravação no banco por `INSERT ... ON CONFLICT DO UPDATE`. Nada é apagado; `evento` só recebe acréscimo.
- Camadas: `sistema` não importa `navegador` (`tests/unidade/test_camadas.py:107-109`); `painel` não importa `httpx`.
- Os endereços das páginas não mudam (D143.3). Onde um grupo muda de nome, o endereço velho responde 303, como na D139.25.

## 4. Como funciona hoje (fatos conferidos)

**Casca.** `base.html:8-16` define os 7 itens do menu (vagas, buscas, fontes, empresas, sugeridas, sites e configurações, este apontando para `/configuracoes/fontes`). O `header.topo` (`base.html:39`) tem `a.marca` (`:40`), o `nav.menu` com nome acessível `casca.menu` (`:41-45`), o `nav.preferencias` com o formulário de tema (POST `/preferencias/tema`, botões Sistema, Claro e Escuro com `aria-pressed`, `:46-53`) e o de idioma (`:54-60`), e a barra de execução (`:62`). Depois vêm `#aviso-versao` (`:64`), `#aviso-erro` com `role='alert'` (`:68-71`), `main#conteudo` (`:72`) e o rodapé "Apoie" (`:75-77`). O `<html>` leva `lang` e `data-tema` (`:21`).

**Tokens.** `:root` em `base.css:26-48`: `--fundo` #f5f5f7/#000000, `--superficie` #ffffff/#1c1c1e, `--texto` #1d1d1f/#f5f5f7, `--texto-2` #6e6e73/#a1a1a6, `--destaque` #0071e3, `--trilho` #e8e8ed/#2c2c2e (hex, entra no par `texto/trilho`), `--segmento` #ffffff/#48484a, `--mola` com pico de 1,08 (`:45`), `--duracao: 420ms` (`:46`), `--raio: 14px` (`:47`). O `body` tem a pilha `-apple-system, BlinkMacSystemFont, "Inter", system-ui, sans-serif` (`:75`), `font-size: 1.0625rem` (`:76`) e `letter-spacing: -0.01em` (`:78`). Foco em `:focus-visible` (`:88-92`). O `.topo` usa blur de 20px e saturação de 180% (`:128-142`). O `.painel` é cartão de conteúdo com vidro (`:322`), usado em todo `class="painel"` de `templates/` (hoje em Buscas, Empresas, Sites, na correção do detalhe e nas páginas de Programas). O movimento reduzido zera tudo (`:341-352`).

**Configurações.** `GRUPOS` em `src/jobot/painel/rotas/configuracoes.py:61-69`: fontes, funcoes, segundo-plano, aparencia, privacidade, servicos e sites-com-login (este vira `contas` pela D139.25). A página tem o `nav.config-grupos` (`templates/configuracoes/pagina.html:7-13`). O grupo Aparência (`templates/configuracoes/aparencia.html`) tem o tema (`:3-14`, `data-preferencia="tema"`), o idioma (`:15-26`) e país e moeda com botão Salvar (`:27-50`). As preferências gravam pela rota `src/jobot/painel/rotas/preferencias.py:20-42`, com `ON CONFLICT`. O interruptor `.chave` está em `static/css/configuracoes.css:141-200`, com movimento reduzido em `:487` e `forced-colors` em `:502`.

**Vagas.** `/` manda para `/primeira-execucao/1` até `primeira_execucao_concluida`, senão para `/vagas?aba=destaques` ou `todas` (`src/jobot/painel/rotas/vagas.py:448-453`). As abas saem de `leitura.ABAS` mais Destaques quando ligados (`vagas.py:32`, `:370-385`), com contagem por `contar_abas` (`src/jobot/banco/leitura.py:429`, uma consulta COUNT por aba). Os rótulos estão em `i18n/pt/vagas.json:6-13` (Destaques, Todas, Novas, Fecham logo, Salvas, Candidatei, Programas, Ocultas). O miolo tem `nav.seletor-busca` (`templates/vagas/miolo.html:8`), `nav.abas` com links `hx-get` e `aria-current` (`:14-19`), o `form.busca` (`:21`, campo `#busca-q` em `:30`) e a ordem (`:33-36`). O mesmo form leva "Mais filtros" (salário de/até, cidade, empresa, excluir) e os campos ocultos (`:21-64`); o miolo tem ainda o aviso "sem critério" (`:2-6`), os avisos de filtro (`:70-84`) e, na aba Programas, a seção de páginas (`:92-122`). A busca vai por Enter: o form tem `hx-trigger="submit, change from:#ordem"` (`:21`); não há busca enquanto digita.

A contagem de Destaques não sai de `contar_abas`, que percorre só `leitura.ABAS`: é `len(_ids_destaques(...))` (`vagas.py:232`, `:373`), calculada só com Destaques ligados. Sem `busca` na URL, `busca_efetiva` cai na primeira busca ativa (`vagas.py:84-89`), e o seletor só aparece com 2 buscas ou mais (`vagas.py:345-351`). Encaixe, nota, ocultação por regra e Destaques são calculados por busca (`encaixe` tem `busca_id` e `oculta_motivo`, `banco/migracoes/0001_inicial.sql:140-148`).

**Ações.** Vaga: `POST /vagas/{id}/status` (`vagas.py:521`), `/ocultar` (`:534`) e o inverso `/mostrar` (`:546`). Sugerida: `POST /empresas/sugeridas/{id}/descartar` (`src/jobot/painel/rotas/sugeridas.py:126`), que só troca o estado para `descartada` (`src/jobot/banco/sugeridas.py:124`), sem rota inversa. Empresa: `/remover` (`src/jobot/painel/rotas/empresas.py:307`) grava `removida_em` (`src/jobot/banco/cadastros.py:250`), sem rota inversa. Busca: `/apagar` (`src/jobot/painel/rotas/buscas.py:311`) faz `DELETE` (`src/jobot/banco/buscas.py:181`). Site acompanhado: `/remover` (`src/jobot/painel/rotas/sites.py:115`) faz `DELETE` (`src/jobot/banco/paginas.py:183`). Nenhuma tela usa `hx-confirm` nem diálogo. O "Esquecer logins" (Contas) já pergunta em dois cliques no próprio fragmento (`configuracoes.py:511-518`, `templates/configuracoes/_esquecer.html`) e apaga a pasta do perfil, o que não volta.

**Primeira execução.** Dois passos e "Tudo pronto". "Pular" no passo 1 grava `meu_pais` e segue para o passo 2 (`src/jobot/painel/rotas/primeira_execucao.py:338-346`). No passo 2, a escolha "desligar" grava `segundo_plano` falso e cria o atalho do menu mesmo sem segundo plano (DR-37, `primeira_execucao.py:396-397` e `:432`). A rota genérica `POST /{passo}` está em `primeira_execucao.py:439`. A T241 acrescenta o passo `/primeira-execucao/sites` (D139.27).

**Abrir o painel.** `abrir_navegador` usa `distrobox-host-exec xdg-open` na distrobox e `webbrowser.open` fora dela (`src/jobot/sistema/abrir.py:73-84`). `abrir_painel` recebe o abridor por parâmetro (`sistema/abrir.py:95-101`). O caminho do Chrome e do Chromium do Playwright está em `src/jobot/navegador/abrir.py:16` e `:94-104`: `caminho_do_navegador` devolve o Chrome primeiro e, sem ele, sobe o driver do Playwright para achar o Chromium.

**Andamento.** A casca de toda página traz "Buscar agora", "Sair" e a região `#andamento`, com `role="status"`, `aria-live="polite"` e `hx-trigger="load"` (`templates/execucao/barra.html:6-21`); a página de despedida a esconde com `sem_barra` (`barra.html:3`). A região pede `GET /execucao/atual` (`src/jobot/painel/rotas/execucao.py:174-186`). Enquanto a busca roda, o trecho `templates/execucao/andamento.html` se pede de novo a cada 2 s (`:8`) e mostra um ponto que pulsa (`:12`, animação `pulsar` em `static/css/execucao.css:64-78`), "Buscando vagas…" com "consultas prontas: {n}" (`andamento.html:12`, textos em `i18n/pt/execucao.json:5-6`), até 5 nomes das fontes que ainda rodam e "+N" (`andamento.html:13-17`) e, com a coleta acabada, "Completando detalhes e organizando as vagas…" (`andamento.html:18-19`). No fim, "Busca concluída. Vagas novas: {n}." ou o motivo da parada (`andamento.html:22-31`). A rota monta uma marca com as consultas prontas e as fontes que rodam e responde 204 quando nada mudou, para o leitor de tela não repetir o anúncio (`rotas/execucao.py:85-94`).

Os dados vêm de `execucao_atual` (`src/jobot/banco/execucoes.py:263-295`), que devolve `Andamento` (`execucoes.py:43-54`): `escopos_prontos` (linhas de `saude` já gravadas, `:52`), `fontes_rodando` (fontes começadas e não terminadas, `:53`) e `coleta_acabou` (`:54`). As marcas de começo e fim de fonte vêm dos chamáveis `ao_comecar_fonte` e `ao_terminar_fonte` do executor (`src/jobot/nucleo/coletores/executor.py:105-106`), ligados pela agenda com gravação de melhor esforço (`src/jobot/agenda/execucao.py:134-146`). Não há total de consultas planejadas, nem etapa depois da coleta, nem espera por site guardados. As etapas da busca são as da docstring de `agenda/execucao.py:1-9`: coleta, detalhes (só com o enriquecimento ligado), cotações, encaixe e fim. As vagas repetidas se juntam dentro da gravação de cada consulta (`agrupar`, `src/jobot/banco/gravacao.py:339`), sem passo próprio. A espera pedida por um site (429 ou 503 com `Retry-After`) e o intervalo por host acontecem no cliente HTTP e no executor (`src/jobot/nucleo/http.py:419-456`, `executor.py:283` e `:300`), e nada disso chega ao banco. A primeira execução usa o mesmo "Buscar agora" da casca na tela "Tudo pronto" (`templates/primeira_execucao/pronto.html:8`).

## 5. O como

### 5.1 Tokens

Tudo em `:root` de `base.css`. Os nomes que já existem ficam; os novos entram ao lado. Tokens com alfa ficam fora da lista de contraste, como `--borda` hoje.

**Tipografia** (https://developer.apple.com/design/human-interface-guidelines/typography)

- Família: a pilha de hoje (`base.css:75`) não muda. No Mac ela cai na fonte do sistema; fora dele, na Inter (D143.7).
- `html { font-size: 100% }`, para respeitar o tamanho que a pessoa escolheu no navegador. Os tamanhos vão em `rem`, contados sobre 16px.
- Escala do Mac, em px (tamanho/entrelinha): título grande 26/32, título 1 22/26, título 2 17/22, título 3 15/20, título de linha 13/16 em peso 700, corpo 13/16, texto secundário 12/15, rótulo pequeno 11/14, nota e legenda 10/13. Tokens `--t-large`, `--t-title1`, `--t-title2`, `--t-title3`, `--t-headline`, `--t-body`, `--t-callout`, `--t-sub`, `--t-foot`, `--t-cap1`, `--t-cap2`, no formato `peso tamanho/entrelinha` em rem.
- Corpo de controles e listas: 13px (D143.12). Descrição da vaga: 15px, entrelinha 1,5, largura máxima de 70ch (proposta, dentro dos 14 a 15px do dono).
- Nada abaixo de 10px. Pesos só 400, 500, 600 e 700.
- `letter-spacing` sai do `body` (`base.css:78`) e do título (`base.css:148`). A fonte do sistema ajusta sozinha, e somar um valor fixo erra nos outros tamanhos (D143.47). Fora do Mac, a InterVariable 4.1 embutida tem eixo de tamanho óptico (`opsz`), e o navegador o aplica sozinho (`font-optical-sizing: auto`, o padrão). Sem tracking fixo nos dois casos.

**Tamanho do texto** (D143.12, D143.23). Três opções em Configurações > Geral: Padrão (13px), Grande (15px) e Maior (17px, o de hoje). A escolha vai para a chave `tamanho_texto` (`padrao`, `grande`, `maior`) e para `<html data-texto="...">`. Como tudo está em `rem`, a troca é só o `font-size` do `html`: 100%, 115,4% (15/13) e 130,8% (17/13) (proposta). Padrão: `padrao`.

**Cores** (https://developer.apple.com/design/human-interface-guidelines/color, https://developer.apple.com/design/human-interface-guidelines/dark-mode). Todas proposta, menos as que só mantêm o valor de hoje.

| Token | Papel | Claro | Escuro |
|---|---|---|---|
| `--texto` | rótulo | #1d1d1f (mantém) | #f5f5f7 (mantém) |
| `--texto-2` | rótulo secundário e placeholder | #636366 | #a1a1a6 (mantém) |
| `--texto-3` | só texto desativado (fora da lista de contraste) | #aeaeb2 | #636366 |
| `--fundo` | fundo da janela | #ececec | #1e1e1e |
| `--superficie` | lista, detalhe, campo | #ffffff | #1e1e1e |
| `--sob-pagina` | atrás de documento | #e5e5e5 | #282828 |
| `--solido-barra` | lateral, barra e faixas sem vidro | #f6f6f6 | #282828 |
| `--solido-elevado` | menu, paleta, alerta e sheet sem vidro | #ffffff | #2c2c2e |
| `--destaque` | botão principal, seleção | #0071e3 (mantém) | #0071e3 (mantém) |
| `--trilho` | trilho de controle | #e8e8ed (mantém) | #2c2c2e (mantém) |
| `--segmento` | parte ativa do trilho | #ffffff (mantém) | #5a5a5e |
| `--separador` | linha de 1px | rgb(0 0 0 / .10) | rgb(255 255 255 / .10) |
| `--hover` | fundo no hover | rgb(0 0 0 / .06) | rgb(255 255 255 / .08) |
| `--pressionado` | fundo ao pressionar | rgb(0 0 0 / .13) | rgb(255 255 255 / .16) |
| `--selecao-inativa` | seleção fora do foco ou em janela inativa | rgb(0 0 0 / .08) | rgb(255 255 255 / .14) |
| `--veu` | atrás do alerta e do sheet | rgb(0 0 0 / .25) | rgb(0 0 0 / .50) |

- `--link`, `--alerta`, `--sucesso` e `--foco` mantêm os valores de hoje.
- O `#6e6e73` de hoje no `--texto-2` claro fica abaixo de 4,5:1 sobre os fundos cinza novos. O `#636366` passa (cálculo nosso; o teste confirma).
- `--trilho` continua em hex, porque entra no par `texto/trilho` de hoje (D143.45).
- Pares novos no comentário de contraste, nos dois temas: `texto-2/fundo`, `texto-2/sob-pagina`, `texto-2/superficie`, `texto/solido-barra`, `texto-2/solido-barra`, `texto/solido-elevado`, `texto-2/solido-elevado`. O par `texto/segmento` já existe e é conferido de novo com o #5a5a5e.
- Cor de destaque fixa em #0071e3 (D143.24). O azul do sistema (#007aff e #0a84ff) dá cerca de 4,0:1 e 3,7:1 com texto branco, abaixo dos 4,5:1 do projeto; o #0071e3 dá cerca de 4,7:1 (cálculo nosso).
- Estado nunca só por cor: selo de estado é ícone, texto e cor.

**Tema** (D143.13, D143.21). A pessoa escolhe Sistema, Claro ou Escuro, como a ADR 0008 já diz ("chave manual"). O `data-tema` do `<html>` e `color-scheme: light dark` ficam como estão. A HIG recomenda seguir só a aparência do sistema, sem seletor no app (https://developer.apple.com/design/human-interface-guidelines/dark-mode). O dono recusou tirar o seletor: é um desvio consciente, registrado aqui. O seletor sai da barra e vai para Configurações > Geral, com padrão Sistema, e também está na paleta de comandos (D143.21). Ele não fica na barra de ferramentas (era a P5; decisão da sessão, já anunciada ao dono, para confirmar).

**Vidro** (https://developer.apple.com/design/human-interface-guidelines/materials). O material translúcido atual da Apple; a D140 o chama de Liquid Glass do macOS 27. Regras (D143.25):

- Duas camadas. Conteúdo opaco: fundo, lista, detalhe, cartões e faixas de aviso. Funcional com vidro: barra lateral, barra de ferramentas, menus, paleta, alerta e sheet.
- A lista e o detalhe rolam no próprio contêiner. Nada rola por baixo da barra nem da lateral: atrás do vidro fica só o fundo da janela.
- Nunca vidro sobre vidro. O `.painel` (`base.css:322`) deixa de ter vidro e passa a `--superficie`.
- Tokens: `--vidro-blur` 24px; `--vidro-blur-grande` 40px (lateral, sheet, alerta); `--vidro-sat` 1,4; `--vidro-fundo` `color-mix(in srgb, var(--solido-barra) 72%, transparent)` e `--vidro-fundo-grande` o mesmo com 85%, porque um fundo translúcido parte de hex dentro de `light-dark` (`padroes.md («CSS e template»)`); o pior caso de contraste sobre o vidro é o par `texto-2/solido-barra`, que já entra na lista; `--vidro-borda` rgb(255 255 255 / .45) e rgb(255 255 255 / .12) (proposta). Duas classes, `.vidro` e `.vidro-grande`, usam esses tokens; nenhum outro lugar repete os números.
- Caminho sólido: com `prefers-reduced-transparency: reduce`, com `prefers-contrast: more` ou sem suporte a `backdrop-filter` (`@supports not`), o vidro some. Lateral e barra usam `--solido-barra`; menus, paleta, alerta e sheet usam `--solido-elevado`; todos ganham borda de 1px `--separador`. Com mais contraste, a borda é `--texto`.
- Janela inativa: sem vidro e com `--solido-barra` (5.2).
- Nunca animar `backdrop-filter`.

**Raios** (proposta; concêntricos: o de dentro é o de fora menos o recuo). Controle 6px (`--raio-controle`); item da lateral 6px; menu, paleta e cartão 10px (`--raio-grande`); sheet e alerta 18px; pílula 999px. `--raio` (14px) continua para quem já usa e cai para 10px.

**Espaço** (proposta). Grade de 4px: 4, 8, 12, 16, 20, 24. Folga de 12px entre controles com moldura e de 24px em volta de controle sem moldura (https://developer.apple.com/design/human-interface-guidelines/accessibility). `--espaco` continua nas margens do miolo.

**Sombra** (proposta). Só em camada que flutua; nunca no lugar de separador nem em linha de lista. Tokens de cor `--sombra-cor` rgb(0 0 0 / .25) e rgb(0 0 0 / .55), `--sombra-cor-forte` rgb(0 0 0 / .30) e rgb(0 0 0 / .60), `--borda-elevada` transparente no claro e rgb(255 255 255 / .12) no escuro. Menu e paleta: `0 8px 30px`; sheet: `0 12px 40px`; alerta: `0 20px 60px` (as duas últimas com a cor forte). `--sombra` continua.

**Foco.** O anel de hoje fica (`base.css:88-92`): 3px sólido em `--foco`, só em `:focus-visible`. O teste de tela mede esse contorno.

**Movimento** (https://developer.apple.com/design/human-interface-guidelines/motion; D143.26)

- Sem movimento em interação frequente (hover, clique, seleção, digitação). Nelas, só cor, fundo e opacidade, em 100 a 120ms, `ease-out`.
- Menu e paleta entram em 150 a 190ms; sheet e detalhe sobreposto em 280 a 300ms; saída em 120 a 150ms, `ease-in`. Teto de 410ms (proposta).
- Duas molas em `linear()`: `--mola-suave`, sem rebote (amortecimento crítico), padrão do app; `--mola-leve`, rebote de 0,6%, só no sheet e no detalhe sobreposto. Navegador sem `linear()` usa `cubic-bezier(0.22, 1, 0.36, 1)`. A mola de hoje (pico de 8%, 420ms) sai.
- `--mola` e `--duracao` continuam como nomes e passam a valer `var(--mola-suave)` e 190ms.
- O que abre a partir de um botão cresce a partir dele (`transform-origin`). Só `transform` e `opacity` animam.
- Sem escala ao pressionar no ponteiro fino; o `:active` com `scale(.96)` sai.
- Movimento reduzido: sem `transform`, sem deslocamento, sem laço. Opacidade, cor e fundo continuam com transição de 120ms. O bloco de `base.css:341-352` muda para isso.

### 5.2 Estrutura da janela

(https://developer.apple.com/design/human-interface-guidelines/windows, https://developer.apple.com/design/human-interface-guidelines/sidebars, https://developer.apple.com/design/human-interface-guidelines/toolbars, https://developer.apple.com/design/human-interface-guidelines/split-views)

```
┌────────────┬───────────────────────────────────────────┐
│ lateral    │ barra de ferramentas (vidro, fixa no alto) │
│ (vidro)    ├───────────────────────────────────────────┤
│            │ faixas de aviso                            │
│            ├──────────────────┬────────────────────────┤
│            │ lista (opaca)    │ detalhe (opaco)         │
└────────────┴──────────────────┴────────────────────────┘
```

**DOM.** `aside.lateral` vem antes do `header.topo` no DOM, com `a.marca` no alto e o `nav` de nome acessível "Principal"/"Main" (`casca.menu`). O `header.topo` continua filho direto do `body` (é o `role=banner` que o teste de "Buscar agora" procura). O `body` tem fundo `--fundo` opaco, para o teste de contraste achar um ancestral opaco atrás do vidro.

**Barra lateral** (D143.3, D143.20, D143.29, D143.32, D143.33)

- Seção "Vagas" (en "Jobs"): Destaques de hoje (só com Destaques ligados), Todas, Novas, Fecham logo, Salvas, Candidatei, Programas, Ocultas. Cada item é link para `/vagas?aba=<chave>`, levando a busca escolhida (`&busca=<id>`) quando houver. As abas de cima saem: não há controle segmentado.
- Seção "Onde buscar" (en "Where to Look"): Buscas, Empresas (com Sugeridas como segundo nível, só quando há sugestão pendente), Fontes, Sites.
- Configurações como último item, numa seção sem título, separada por espaço. Não fica presa no rodapé da janela. O ⌘, abre o mesmo lugar (D143.43).
- Lugar de Sugeridas, Sites e Configurações: decidido pelo dono em 2026-11-16 (D143.58, era a P2). Sugeridas aparece sob Empresas só quando há sugestão esperando; Sites vem depois de Fontes; Configurações fica no fim da lateral.
- No máximo dois níveis. Cabeçalho de seção em 11px (proposta) peso 600, `--texto-2`, sem caixa alta.
- Contagem em texto simples à direita, `--texto-2`, sem pílula; some quando é zero. As abas contam por `contar_abas` (`leitura.py:429`); Destaques de hoje conta por `_ids_destaques` (`vagas.py:232`), só com Destaques ligados. As duas contagens saem de um ajudante único em `painel/`, usado pela casca em toda página que mostra a lateral, renderizado no servidor. Nas respostas HTMX de Vagas, a seção vai junto por `hx-swap-oob`.
- Busca escolhida (D143.50): a busca que a pessoa escolhe em Vagas é gravada na chave `busca_escolhida` (`gravar_config`, `ON CONFLICT`). A busca da URL vence; sem ela, vale a gravada; se a gravada foi apagada ou desligada, vale a primeira ativa, como em `busca_efetiva` hoje. As contagens e os links da lateral usam essa busca em toda página.
- Medidas (proposta): largura 240px, de 180 a 320px, arrastável pelo divisor e guardada em `localStorage` com `try/catch`; duplo clique volta a 240px. Linha de 28px, ícone de 16px, texto de 13px. Item selecionado com fundo `--destaque`, texto branco, raio 6px e margem de 8px dos lados. Um tamanho só (médio); as medidas ficam em variáveis CSS.
- Ícone por `::before` com `mask-image: url(/static/icones/<nome>.svg)` e `background-color: currentColor`. O `<a>` fica só com texto, como o teste de integração exige; a CSP já aceita (`img-src 'self'`).
- `aria-current="page"` no item da rota atual. Em Vagas, no item da aba atual.

**Divisor.** Linha de 1px `--separador` com área de pega de 8px (proposta). Ponteiro `col-resize`. `role="separator"`, `aria-orientation="vertical"`, `aria-valuemin="180"`, `aria-valuemax="320"`, `aria-valuenow`, `tabindex="0"`; setas mudam 10px (proposta), Home e End vão às pontas, Enter recolhe e mostra.

**Barra de ferramentas** (proposta onde há número). Altura 52px. Três zonas: no início, o botão de recolher a lateral (ícone `panel-left`) e o título da seção ("Vagas", "Buscas"; nunca "joBot"); no fim, a busca, o botão da paleta, "Buscar agora" (o único botão principal), "Sair" e o andamento (`#andamento`), que é o componente de progresso da 5.9. Botões de 28x28px, sem moldura, ícone de 16px, hover `--hover` com raio 6px. Tema e idioma não ficam mais aqui.

**Busca** (D143.52). Na barra, só nas telas que têm busca (Vagas). 180px que crescem para 280px no foco; altura 28px; placeholder com o escopo ("Buscar em Vagas"); "/" foca, Esc limpa. A busca continua por Enter, como hoje. O elemento `<form id="busca">` fica na barra da lista, com "Mais filtros" e os campos ocultos; o campo da barra de ferramentas e o menu da ordem entram nele pelo atributo `form="busca"`, que é HTML puro e funciona sem JavaScript. O `hx-trigger="submit, change from:#ordem"` fica como está.

**Lista** (https://developer.apple.com/design/human-interface-guidelines/lists-and-tables)

- Linhas com separador sobre `--superficie`, sem cartão; recuo de 12px (proposta).
- Linha de vaga com três linhas de texto, cerca de 64px (proposta), decidida pelo dono em 2026-11-16 (D143.59, era a P4): título 13px peso 500 com o encaixe (●◐○) ao lado; empresa e local 12px `--texto-2`; salário convertido e selos de estado (ícone e texto) 12px, com a data de publicação 11px à direita (a da coleta quando não há publicação). As fontes, o motivo do encaixe e os botões ficam no detalhe e no menu de contexto. Abaixo de 640px, sem detalhe ao lado, os botões ficam na página `/vagas/{id}`.
- Texto cortado com reticências e o valor inteiro em `title`.
- `role="listbox"` de seleção única, com tabindex móvel; setas, Home, End, J e K movem; Return abre. A linha só tem texto, sem botão nem link dentro (uma `option` não pode ter controle); as ações ficam no detalhe e no menu de contexto (D143.53).
- Seleção persistente: a linha aberta no detalhe fica marcada.
- Barra da lista, logo acima das linhas (D143.34, D143.52):
  - O seletor de busca vira um menu pop-up com as buscas ativas (e a da URL), só com 2 buscas ou mais, como hoje (`vagas.py:345-351`). Não há opção "Todas as buscas": encaixe, nota e Destaques são calculados por busca.
  - A ordem vira um menu pop-up. Os chips de filtro continuam botões com `aria-pressed`.
  - "Mais filtros" vira um botão que abre os mesmos campos de hoje num `<details>` logo abaixo da barra da lista, que funciona sem JavaScript.
  - O aviso "sem critério" e os avisos de filtro ficam logo abaixo da barra da lista, dentro da coluna, no estilo das faixas de aviso (5.2), sem botão de fechar: somem quando a causa some.
- Na aba Programas, as páginas acompanhadas ficam numa seção própria abaixo das linhas de vaga, com o mesmo estilo de linha, fora do `listbox`, cada uma como link.
- Estado vazio: título, uma linha e um botão ("Buscar vagas").

**Detalhe** (D143.35, D143.51). Decidido pela largura da coluna de conteúdo (tabela de larguras abaixo). Em coluna: à direita, de 320 a 380px, atualizada sem trocar de página. Sobreposto: à direita, `min(420px, 60%)` da coluna de conteúdo, num `<dialog>` não modal com sombra de camada flutuante; Esc ou clique na lista fecha. Em página própria: a `/vagas/{id}` de hoje. Texto de leitura até 680px. Título em título 3; descrição em 15px.

**Endereço da vaga escolhida** (D143.51). Escolher uma vaga troca o endereço para `/vagas?...&vaga=<id>` (`hx-push-url`), com a aba, a busca e a ordem de antes. Com `vaga` no endereço, o servidor já manda o detalhe junto, e o CSS o mostra em coluna ou sobreposto, pela largura; assim recarregar ou voltar no navegador abre a mesma vista. Com a coluna abaixo de 640px, a linha é link para `/vagas/{id}` e não usa o parâmetro. O parâmetro é novo, mas nenhum endereço muda: `/vagas/{id}` continua sendo o link direto.

**Seleção e foco de coluna.** A coluna com o foco do teclado (`:focus-within`) mostra a seleção em `--destaque` com texto branco; as outras mostram `--selecao-inativa` com texto normal. Sem foco em coluna nenhuma, a lista conta como ativa.

**Janela inativa** (https://developer.apple.com/design/human-interface-guidelines/windows). O `app.js` ouve `focus` e `blur` da janela e põe `data-janela="inativa"` no `<html>`. Com ele, a seleção vira `--selecao-inativa` e lateral e barra perdem o vidro (fundo `--solido-barra`), com transição de cor de 150ms (proposta). Sem JavaScript, a janela fica sempre ativa.

**Larguras** (proposta). A lateral é decidida pela largura da janela, com `@media`; a lista e o detalhe, pela largura da coluna de conteúdo, com container queries nessa coluna. Container query não alcança a lateral, que é irmã da coluna, e a lateral não depende da coluna, então recolher a lateral não entra em ciclo.

| Janela (`@media`) | Lateral |
|---|---|
| 900px ou mais | visível, na largura escolhida (180 a 320px) |
| 640 a 900px | recolhida; o botão da barra a abre sobreposta, sem empurrar a lista; Esc, clique fora ou escolher um item fecha |
| abaixo de 640px (ou zoom de 200%) | uma coluna; a navegação vira uma faixa no alto, antes do conteúdo, com os links em linha que quebra; a barra deixa de ser fixa |

| Coluna de conteúdo (container query) | Lista e detalhe |
|---|---|
| 860px ou mais | lista (mínimo 300px) e detalhe em coluna |
| 640 a 860px | lista; detalhe sobreposto |
| abaixo de 640px | lista; detalhe na página própria |

Com a lateral de 240px, a coluna de 860px corresponde à janela de 1100px. Na janela de 640 a 900px a lateral está recolhida, então a coluna tem a largura da janela: o detalhe é sobreposto (ou em coluna, de 860px para cima).

A faixa de baixo de 640px funciona sem JavaScript e mantém a ordem de Tab (pular, marca, itens).

**Faixas de aviso** (D143.42). Logo abaixo da barra, nesta ordem: erro (`#aviso-erro`, que sai do rodapé e mantém `role='alert'` com aspas simples), versão (`#aviso-versao`), contas (logo depois da versão, como na D139.23) e Desfazer. Cada uma com ícone de 16px, texto de 13px e ação à direita. Erro, versão e Desfazer têm botão de fechar; a faixa de Contas não tem (D139.13): ela some sozinha quando a queda fecha. As faixas são opacas, na camada de conteúdo, sem vidro: fundo com 10 a 12% da cor do estado sobre `--fundo`. Altura mínima de 36px, raio 10px (proposta).


**Rodapé.** "Apoie" continua (`base.html:75-77`), como informação secundária.

### 5.3 Controles

(https://developer.apple.com/design/human-interface-guidelines/buttons, https://developer.apple.com/design/human-interface-guidelines/toggles)

- Tamanho regular de 28px de altura para botão, campo e menu pop-up; nenhum alvo abaixo de 20x20px; texto de controle em 13px.
- Botão principal: fundo `--destaque`, texto branco, peso 600; no máximo um por tela, raramente dois; responde a Return.
- Botão comum: fundo `--fundo-controle` (rgb(255 255 255 / .70) e rgb(255 255 255 / .12)), borda de 0,5px `--borda-controle` (rgb(0 0 0 / .15) e rgb(255 255 255 / .15)) (proposta).
- Botão simples: sem fundo; hover `--hover`.
- Destrutivo: texto `--alerta`; nunca é o botão principal; nunca responde a Return. Vale para a ação destrutiva que a pessoa não escolheu de propósito. No alerta de uma ação que ela escolheu (Apagar busca, Remover site, Esquecer logins), o botão da ação não leva `--alerta` (5.4).
- Rótulo começa por verbo no infinitivo. Reticências quando abre outra etapa ("Adicionar empresa…").
- `cursor: default` em botão; a mão só em link.
- Desativado: `opacity: .45` (proposta), sem hover; o motivo aparece ao lado. `aria-disabled` quando o controle precisa continuar focável.
- Caixa de marcar na maior parte de Configurações; interruptor só onde se quer destacar ou onde a opção comanda um grupo (D143.28). Caixa de 14px, raio 4px (proposta), visto branco sobre `--destaque`. Interruptor regular 38x22px e mini 30x18px (proposta). O `.chave` continua para os interruptores que ficam; o bloco `forced-colors` (`configuracoes.css:502`) cobre a caixa nova também.
- Menu pop-up: escolha única que mostra o valor no próprio botão (busca, ordem, tamanho do texto, tema, idioma). `<select>` nativo com aparência própria e bloco `forced-colors`.
- Campo: altura 28px, raio 6px, fundo `--superficie`, rótulo sempre visível, placeholder em `--texto-2`.
- Progresso: a barra do componente único da 5.9, com a linha da etapa. Não há indicador giratório: a espera sem total usa a barra indeterminada, porque a HIG pede não trocar o giratório pela barra no meio da espera (D143.61).
- Dica (`title`) com verbo e o atalho quando houver: "Focar a busca (/)".

**Ícones** (D143.8; https://developer.apple.com/design/human-interface-guidelines/icons). Lucide em SVG, numa versão fixada, copiados para `static/icones/`, com o arquivo de licença do projeto Lucide e um `lucide.meta.json` com versão, licença, origem e sha256 de cada arquivo, como `inter.meta.json`. Entram só os ícones usados. Traço de 1,5px; 16px em linha e botão, 18px na barra, 20px em estado vazio (proposta). Mapa (proposta; os nomes são conferidos na versão fixada):

| Onde | Ícone |
|---|---|
| Destaques de hoje, Todas, Novas, Fecham logo | `sparkles`, `inbox`, `circle-dot`, `hourglass` |
| Salvas, Candidatei, Programas, Ocultas | `bookmark`, `send`, `graduation-cap`, `eye-off` |
| Buscas, Empresas, Sugeridas, Fontes, Sites | `search`, `building-2`, `lightbulb`, `rss`, `globe` |
| Configurações, recolher lateral, paleta | `settings`, `panel-left`, `command` |
| desfazer, refazer, fechar, mais, aviso, copiar link | `undo-2`, `redo-2`, `x`, `ellipsis`, `triangle-alert`, `link` |

### 5.4 Fluxos

**Desfazer** (D143.16, D143.17, D143.36; https://developer.apple.com/design/human-interface-guidelines/undo-and-redo)

- O "descartar" do dono, na vaga, é o Ocultar de hoje. "Arquivar" não existe no joBot e não entra (D143.46).
- Ocultar vaga roda na hora, sem pergunta. A resposta HTMX tira a linha e traz, por `hx-swap-oob`, a faixa "Vaga ocultada" com o botão "Desfazer", um formulário para `POST /vagas/{id}/mostrar` (`vagas.py:546`). Nenhuma rota nova.
- A faixa fica até a pessoa fechar. Duas exceções (D143.36, para confirmar): outra ação desfazível toma o lugar dela (uma faixa por vez), e uma página nova carregada inteira a tira. As trocas por HTMX dentro de Vagas (aba, busca, ordem, filtro, carregar mais) não a tiram: a faixa mora na casca, fora do `#vagas-miolo`. `role="status"`.
- ⌘Z (Ctrl+Z fora do Mac) aciona o "Desfazer" da faixa visível, só fora de campo de texto; dentro do campo, o ⌘Z fica com o navegador. Sem faixa, não faz nada.
- Refazer: depois do Desfazer, a faixa passa a "Vaga mostrada de novo" com o botão "Refazer", um formulário para `POST /vagas/{id}/ocultar` (`vagas.py:534`), que já existe. ⇧⌘Z (Ctrl+Shift+Z fora do Mac) o aciona, também só fora de campo de texto. Refazer devolve a faixa "Vaga ocultada" com "Desfazer".
- Um nível só: a faixa guarda a última ação, sem histórico. A HIG pede vários desfazer (https://developer.apple.com/design/human-interface-guidelines/undo-and-redo); o painel guarda o estado no servidor e mostra uma faixa por vez, então um nível só é desvio consciente, para confirmar (D143.36).
- Desfazer e Refazer mostram o resultado: a linha volta ao lugar (ou sai) e, ao voltar, fica destacada por 1s (proposta), com fundo que se apaga.
- Descartar sugerida e remover empresa rodam sem pergunta e com a faixa de Desfazer, como o dono pediu na D143.16 (era a P3; decisão da sessão, para confirmar). Duas rotas novas: `POST /empresas/sugeridas/{id}/restaurar` volta o estado a `pendente`, e `POST /empresas/{id}/restaurar` limpa `removida_em`. Nada é apagado: as duas ações de hoje só marcam a linha (`banco/sugeridas.py:124`, `banco/cadastros.py:250`). As faixas dizem "Sugestão descartada" e "Empresa removida", com "Desfazer"; o Refazer é a própria ação de hoje (`/descartar`, `/remover`), como no Ocultar. Gravação por `UPDATE` da mesma linha, sem `INSERT OR REPLACE`.
- Apagar busca e remover site acompanhado apagam de verdade (`DELETE`). Esses dois pedem confirmação num alerta (D143.37).
- Esquecer logins (Contas) também não volta: apaga a pasta do perfil. A pergunta de hoje, em dois cliques no fragmento (`configuracoes.py:511-518`), vira o alerta, com "Esquecer" e "Cancelar" (D143.37).
- Trocar o estado da vaga (Salvar, Candidatei) não leva faixa: o próprio controle de estado desfaz.

**Alerta** (https://developer.apple.com/design/human-interface-guidelines/alerts). Só para o que não volta. `<dialog>` modal de 260px, padding de 20px, `.vidro .vidro-grande`, raio 18px, sombra de alerta, véu `--veu` (proposta). Título em 13px peso 600 terminado em "?"; texto em 11px (proposta) `--texto-2`. Botões em pilha, de largura toda: a ação em cima ("Apagar"), "Cancelar" embaixo. A pessoa escolheu a ação de propósito, então o botão da ação não leva o estilo destrutivo. Nenhum botão é o padrão, para a pessoa ler antes de confirmar, e "Cancelar" nunca é. Esc e ⌘. cancelam; clicar no véu não fecha; o foco fica preso dentro e volta ao botão que abriu. Exemplo: "Apagar a busca «Python remoto»?", "As vagas que ela trouxe continuam.", "Apagar" e "Cancelar". Entra com fade e `scale(.96)` em 200ms (proposta); com movimento reduzido, só o fade.

**Paleta de comandos** (D143.15, D143.38)

- ⌘K no Mac, Ctrl+K fora dele, e um botão na barra (ícone `command`) que não depende do atalho.
- `<dialog>` modal no alto da janela, 560px de largura (proposta), `.vidro .vidro-grande`, raio 10px. Um campo e uma `role="listbox"` filtrada enquanto digita; setas movem, Return executa, Esc fecha.
- Os comandos vêm renderizados no servidor, no idioma da página: ir para cada item da lateral, cada grupo de Configurações, "Buscar agora", "Sair", trocar tema e idioma, e o tamanho do texto. Cada comando é um link ou um formulário que já existe; a paleta não cria ação nova.
- Atalho escrito ao lado do comando, em `--texto-2`.

**Menu de contexto** (D143.39; https://developer.apple.com/design/human-interface-guidelines/context-menus)

- Na linha de vaga: Abrir, Abrir no site da vaga, Salvar, Ocultar, Copiar link. Em Buscas, Empresas e Sites, as ações da própria linha.
- Clique com o botão direito, a tecla de menu ou Shift+F10 abrem. Poucos itens, até três grupos, sem atalhos escritos, item indisponível escondido.
- Todo item existe também na tela: no detalhe, para a vaga (a linha só tem texto, D143.53); na própria linha, em Buscas, Empresas e Sites, que não são `listbox`. O menu é um `<dialog>` não modal ou um elemento com o atributo `popover`, posicionado no ponteiro; raio 10px, itens de 24px (proposta), item destacado em `--destaque` com texto branco.
- Sem JavaScript, não há menu; as mesmas ações estão na tela.

**Primeira execução** (D143.18, D143.40; https://developer.apple.com/design/human-interface-guidelines/onboarding)

- Três passos: "O que você procura?", "Sites com login (opcional)" (o passo da T241) e "Segundo plano". "Tudo pronto" é a tela final e não conta como passo. A primeira execução nova entra depois da T241, já com os três passos (seção 8); o contador lê a lista de passos.
- "Pular" sempre visível, em todos os passos, como botão simples. Ele vai para uma rota nova, `POST /primeira-execucao/pular`, registrada antes de `@router.post("/{passo}")` (`primeira_execucao.py:439`); senão "pular" cai em `PASSOS.get` e dá 404.
- Os padrões de quem pula: a rota grava `meu_pais` (como o pular de hoje, `primeira_execucao.py:338-346`), `segundo_plano` falso e `primeira_execucao_concluida`, cria o atalho do menu no Linux como o passo 2 faz com "desligar" (DR-37, `primeira_execucao.py:396-397`), sem prender em falha, e manda para `/vagas`. Nada é ligado em segundo plano e nenhum site com login é ligado. A busca fica sem critério, e Vagas mostra o aviso "sem critério" de hoje.
- Botões "Continuar" e, no último passo, "Concluir".
- A fileira de botões (Pular, Continuar ou Concluir) fica presa no pé da janela; só o conteúdo do passo rola. Vale também para o sheet de correção, o alerta e, na fase 3, o instalador de verdade: os botões de ação nunca saem da tela, mesmo com tudo marcado, texto Maior ou janela baixa. Em CSS: contêiner em grid ou flex com a área do conteúdo em `overflow: auto` e `min-height: 0`; nada de altura fixa que empurre os botões. Referência: (D144, E17).
- Durante o assistente, a janela não mostra a lateral nem os botões da barra, como já acontece com `sem_barra` na página de despedida (`templates/execucao/barra.html:2-3`). A tela "Tudo pronto" é a exceção: ela mostra "Buscar agora" e o andamento na barra, como hoje (`templates/primeira_execucao/pronto.html:8`), para a primeira busca usar o mesmo componente e o mesmo lugar de todas as outras (D143.69).

**Configurações** (D143.4, D143.22, D143.28, D143.43; https://developer.apple.com/design/human-interface-guidelines/settings)

- No jeito dos Ajustes do Sistema: lista de grupos à esquerda (ícone de 20px, texto de 13px, seleção em `--destaque`) e o grupo à direita. O `nav.config-grupos` e a rota `/configuracoes/{grupo}` continuam.
- No Mac, a HIG põe os ajustes numa janela própria com uma barra de painéis no alto (https://developer.apple.com/design/human-interface-guidelines/settings). A lista de grupos à esquerda, numa página do painel, é desvio consciente, decidido pelo dono (D143.4): cada grupo tem o seu endereço, e os testes dependem dele.
- Grupo Geral, primeiro da lista: tema (Sistema, Claro, Escuro; padrão Sistema), idioma (Português, English), tamanho do texto (Padrão, Grande, Maior), país e moeda. Os campos de hoje do grupo Aparência (`aparencia.html:3-50`) passam para ele. Slug `geral`, primeiro da lista (era a P1; decisão da sessão, para confirmar). `GET /configuracoes/aparencia` responde 303 para `/configuracoes/geral`, e o link velho continua funcionando. O 303 cobre só o GET: o POST de país e moeda (`aparencia.html:27`, hoje para `/configuracoes/aparencia`, que cai na rota `POST /{grupo}`) também se move para `/configuracoes/geral`, sem cópia no endereço velho, como na D139.25.
- Tema, idioma e tamanho do texto são menus pop-up que salvam ao mudar, pelas rotas `/preferencias/tema` e `/preferencias/idioma` de hoje (`preferencias.py:20-42`) e pela nova `/preferencias/texto`, gravada do mesmo jeito (`ON CONFLICT`). Sem JavaScript, cada um tem o seu botão de enviar dentro de `<noscript>`. País e moeda mantêm o botão Salvar.
- O item Configurações da lateral abre o último grupo visto, guardado em `localStorage` com `try/catch`; sem registro, e sem JavaScript, abre `/configuracoes/geral`. ⌘, (Ctrl+, fora do Mac) faz o mesmo; alguns navegadores tomam esse atalho, e por isso o item da lateral é o caminho garantido. Reabrir no último painel usado é o que a HIG pede (https://developer.apple.com/design/human-interface-guidelines/settings) (D143.43).

**Janela do modo app** (D143.6, D143.41)

- `jobot` abre o painel numa janela sem abas nem barra de endereço, com a opção `--app=<endereço>` do navegador. Ordem de busca:
  1. Chrome, Edge ou Chromium instalados no sistema (na distrobox, no sistema de fora, pelo mesmo prefixo de `abrir_navegador`). Linux: `google-chrome`, `google-chrome-stable`, `microsoft-edge`, `chromium`, `chromium-browser`. Mac: os apps Google Chrome, Microsoft Edge e Chromium, abertos com `open -na <app> --args --app=<endereço>`. Windows: `chrome.exe` e `msedge.exe` nas pastas de programas.
  2. O Chromium do Playwright que o joBot já baixa, com perfil próprio em `<dados>/janela/`. Nunca o perfil das janelas de login (D132).
  3. Uma aba comum, pelo `abrir_navegador` de hoje.
- O navegador do sistema usa o perfil da pessoa, como uma aba comum.
- Camadas: a busca do 1 e o 3 ficam em `sistema`. O `navegador` ganha uma função que devolve só `playwright.chromium.executable_path` (sem olhar o Chrome, ao contrário de `caminho_do_navegador`, `navegador/abrir.py:94-104`). O `cli` a passa a `sistema` como chamável, e `sistema` só a chama quando o passo 1 não acha navegador; assim o driver do Playwright não sobe a cada `jobot`. Isso porque `sistema` não importa `navegador` (`test_camadas.py:107-109`). `abrir_painel` já recebe o abridor por parâmetro (`sistema/abrir.py:101`).
- A janela usa a moldura do sistema até a fase 3. O painel não desenha botões de janela nem barra de título (D143.11).

### 5.5 Teclado

(https://developer.apple.com/design/human-interface-guidelines/keyboards; D143.27)

| Mac | Fora do Mac | Ação |
|---|---|---|
| ⌘, | Ctrl+, | Configurações |
| ⌘K | Ctrl+K | paleta de comandos |
| ⌘Z | Ctrl+Z | Desfazer da faixa visível, fora de campo de texto |
| ⇧⌘Z | Ctrl+Shift+Z | Refazer da faixa visível, fora de campo de texto |
| ⌘? | Ctrl+? | ajuda (a página do joBot na wiki, aberta em aba) |
| Esc, ⌘. | Esc | fecha menu, paleta, sheet ou alerta |
| / | / | foca a busca, fora de campo de texto |
| ↑ ↓, Home, End, J, K | os mesmos | movem na lista; J e K só fora de campo de texto |
| Return | Enter | abre a vaga |

- ⌘F fica com o navegador. ⌘A também: a lista é de seleção única e não há ação em lote (D143.27).
- Sem ⌘R, ⌘N, ⌘W, ⌘T, ⌘Q, ⌘L nem ⌘1 a ⌘9.
- ⌘K é conflito declarado: no Firefox (todos os sistemas) e no Chrome do Windows e do Linux ele foca a busca do navegador. Com o foco na página, o joBot o toma; o botão da paleta na barra é o caminho que não depende dele.
- Atalho escrito com os símbolos na ordem ⌃ ⌥ ⇧ ⌘, sem hífen; fora do Mac, "Ctrl+Shift+Z". O sistema vem de `navigator.userAgentData?.platform ?? navigator.platform`.
- Ordem de Tab igual à de leitura; sem `tabindex` positivo. Dentro de lista e menu, as setas movem e o Tab sai.

### 5.6 Escrita

(https://developer.apple.com/design/human-interface-guidelines/writing; D143.30)

- pt-BR: só a primeira letra maiúscula em tudo ("Nova busca"). en: Title Case em botão, item de menu, título e item da lateral; frase normal em texto, dica e mensagem.
- Botão no infinitivo ("Salvar", "Buscar vagas", "Tentar de novo"). Link diz o destino.
- "Você" ou frase sem sujeito; nunca "o usuário", "nós" ou "nosso". "Vagas", não "Minhas vagas".
- Gênero neutro: "Boas-vindas", não "Bem-vindo".
- Erro diz o que houve e o que fazer, sem humor, sem exclamação, sem código técnico: "A fonte não respondeu. Tente de novo em alguns minutos."
- "Clique" ou "Selecione"; nunca "Toque". Nunca "popover" nem "painel" no texto da tela.
- Um termo por conceito: vaga/job, busca/search, fonte/source, ocultar/hide, descartar/discard (sugerida), configurações/settings.
- Datas e números por `Intl` no idioma da página.

Textos novos (proposta; chaves em `casca.lateral.*`, `casca.desfazer.*`, `casca.paleta.*`, `configuracoes.geral.*` e `primeira_execucao.pular`):

| pt | en |
|---|---|
| Vagas · Onde buscar | Jobs · Where to Look |
| Destaques de hoje | Today's Highlights |
| Recolher barra lateral · Mostrar barra lateral | Hide Sidebar · Show Sidebar |
| Buscar em Vagas | Search Jobs |
| Vaga ocultada · Desfazer | Job hidden · Undo |
| Vaga mostrada de novo · Refazer | Job shown again · Redo |
| Sugestão descartada · Empresa removida | Suggestion discarded · Company removed |
| os textos do progresso | na tabela da 5.9 |
| Comandos · Buscar comando | Commands · Search Commands |
| Geral · Tema · Idioma · Tamanho do texto | General · Appearance · Language · Text Size |
| Sistema · Claro · Escuro | System · Light · Dark |
| Padrão · Grande · Maior | Default · Large · Larger |
| Apagar a busca «{nome}»? · As vagas que ela trouxe continuam. | Delete the Search "{nome}"? · Jobs it brought in stay. |
| Remover o site «{nome}»? · O texto guardado e as mudanças dele serão apagados. | Remove the Site "{nome}"? · Its saved text and changes will be deleted. |
| Apagar · Remover · Esquecer · Cancelar | Delete · Remove · Forget · Cancel |
| Pular | Skip |

As chaves de `configuracoes.aparencia.*` que mantêm o sentido ficam com o nome atual; só a do nome do grupo sai, como na D139.29.

### 5.7 Acessibilidade

(https://developer.apple.com/design/human-interface-guidelines/accessibility)

- 4,5:1 em todo par da lista, nos dois temas e no caminho sólido.
- 200% de zoom sem corte e sem rolagem lateral: `rem` e `min-height`, nunca altura fixa em texto.
- Mais contraste (`prefers-contrast: more`): sem vidro, borda de 1px `--texto`.
- Menos transparência e falta de `backdrop-filter`: caminho sólido (5.1).
- Cores forçadas: o bloco `forced-colors` de `configuracoes.css:502` vale também para a lateral, a barra, a caixa de marcar, os menus e o divisor.
- Não só cor: ícone, texto e cor juntos.
- Nada importante some sozinho: a faixa de Desfazer só sai quando a pessoa fecha, quando outra ação desfazível toma o lugar dela ou quando uma página nova é carregada inteira (5.4).
- Leitor de tela: HTML semântico; nome acessível igual ao texto visível; `role="status"` e `aria-live="polite"` na faixa de Desfazer e, no progresso, só no nome da etapa (5.9); `role='alert'` no erro.
- Todo arrastar tem caminho por teclado (divisor) ou botão (recolher).
- Propriedades lógicas (`margin-inline-start`, `inset-inline-end`) no CSS novo.

### 5.8 Cada tela: hoje e depois

| Tela | Hoje | Depois |
|---|---|---|
| Casca (`base.html`, `base.css`, `execucao.css`) | cabeçalho translúcido com 7 links, tema, idioma, "Buscar agora", "Sair" e andamento; aviso de erro no rodapé | lateral com vidro e os itens da 5.2; barra com título, busca, paleta, "Buscar agora", "Sair" e andamento; faixas sob a barra; sem tema e idioma na barra |
| Vagas (`vagas/*.html`, `vagas.css`) | título, seletor de busca, campo, ordem, abas em pílula, chips, cartões, "carregar mais" | abas viram itens da lateral; busca na barra; seletor de busca e ordem em menus pop-up na barra da lista; linhas sem cartão; detalhe na coluna da direita; menu de contexto; faixa de Desfazer |
| Detalhe e correção (`detalhe/*.html`, `detalhe.css`) | página própria de 48rem | inspetor à direita quando cabe; página própria por link e em tela estreita; correção num sheet (`<dialog>` de 520px no alto, raio 18px) |
| Buscas (`buscas/*.html`, `buscas.css`) | lista com ligar, desligar e apagar; formulário com `.painel` de vidro | lista agrupada opaca; interruptor mini por linha; apagar com alerta |
| Fontes (`fontes/pagina.html`, `fontes.css`) | cartões por fonte | lista agrupada; estado com ícone e texto; caixa de marcar para ligar |
| Empresas e Sugeridas (`empresas/lista.html`, `sugeridas/lista.html`) | lista; remover e descartar sem confirmação nem volta | lista agrupada; remover e descartar com Desfazer, pelas rotas novas de restaurar (5.4) |
| Sites (`sites/lista.html`) | lista com desativar e remover | lista agrupada; remover com alerta |
| Configurações (`configuracoes/*.html`, `configuracoes.css`) | 7 grupos; interruptores `.chave` em quase tudo | grupos à esquerda com Geral primeiro; caixa de marcar na maior parte; Contas da D139 entra já nesta base |
| Primeira execução (`primeira_execucao/*.html`) | 2 passos e "Tudo pronto", com o menu inteiro | 3 passos (depois da T241), "Pular" sempre visível, sem lateral |
| Erro e Saiu (`erro/pagina.html`, `execucao/saiu.html`) | página com título | estado vazio com ícone, título curto e o que fazer; Saiu sem lateral e sem botões |
| Andamento (`execucao/andamento.html`, `barra.html`, `execucao.css`) | ponto que pulsa, "consultas prontas: {n}" e até 5 fontes que rodam | componente único da 5.9: barra do Mac (indeterminada até haver total), linha da etapa com contagem, espera por site e "Ver detalhes" |
| Linha da vaga (`vagas/corpo.html`) | cartão com título, empresa, local, salário, encaixe, selos, fontes e botões (`corpo.html:14-86`) | três linhas de texto, cerca de 64px; fontes, motivo do encaixe e botões no detalhe e no menu de contexto (D143.59) |

### 5.9 Progresso e etapas

(https://developer.apple.com/design/human-interface-guidelines/progress-indicators, https://developer.apple.com/design/human-interface-guidelines/loading; D143.55 a D143.57, D143.61 a D143.70)

**Um componente só** (D143.56). Toda espera de mais de 1 s usa o mesmo componente, no mesmo lugar de cada tela:

- "Buscar agora": o andamento na barra de ferramentas (`#andamento`, 5.2).
- A primeira busca da primeira execução, na tela "Tudo pronto", que mostra a barra (5.4, D143.69).
- "Conferir agora" de Contas, quando a tela da D139 existir.
- "Esquecer logins".
- O instalador: o protótipo no Canvas agora e o instalador em Tauri na fase 3 seguem as mesmas regras.

Espera curta não mostra nada. O componente tem três partes: a barra, a linha da etapa e, quando há lista por site, "Ver detalhes".

**Barra** (D143.61). Um trilho com um preenchimento dentro, com `role="progressbar"`: barra lisa do Mac, sem blocos nem listras, preenchimento `--destaque`, trilho `--trilho-progresso`, altura de 6px e raio de pílula. Largura de 240px na barra de ferramentas e de 320px no corpo de uma tela (proposta). Na barra de ferramentas, a barra fica em cima e a linha da etapa embaixo. Determinada, o preenchimento tem `id` fixo e a largura em `style` (de 0 a 100%). Sem total, é a barra indeterminada do Mac: um trecho que corre pelo trilho. Não usamos o `<progress>` nativo: o preenchimento dele vem do atributo `value`, que o CSS não anima, e a troca por `outerHTML` põe um elemento novo já no valor novo. Com o mesmo `id` e a largura em `style`, o assentamento do HTMX copia a largura velha para o elemento novo e depois aplica a nova, e a transição do CSS anda entre as duas. Não há indicador giratório: a HIG pede não trocar o giratório pela barra no meio de uma espera, e a barra indeterminada cobre o começo. A HIG prefere o giratório em operação de fundo e em espaço apertado, como a barra de ferramentas; usar a barra ali é desvio consciente, pedido pelo dono (Q21: toda espera usa o mesmo componente). `--trilho-progresso` é um token novo, igual a `--trilho` no claro e #1e1e1e no escuro (proposta): o `--trilho` escuro (#2c2c2e) dá cerca de 2,97:1 com o `--destaque`, abaixo dos 3:1 de objeto gráfico, e o #1e1e1e dá cerca de 3,55:1 (cálculo nosso; o claro dá cerca de 3,85:1). O preenchimento por cor de fundo some em cores forçadas e pede o seu bloco `forced-colors` (`padroes.md («CSS e template»)`).

**Indeterminada, depois determinada** (D143.56). Enquanto o total não é conhecido, a barra é indeterminada e a linha diz a etapa ("Preparando as consultas"). Assim que o total aparece, ela passa a determinada, no mesmo lugar e com o mesmo tamanho. Na mesma espera, ela nunca volta a ser indeterminada. "Esquecer logins" não tem total e fica indeterminada do começo ao fim.

**Limiar de 1 s** (D143.64). O componente só aparece quando a espera passa de 1 s, contado do clique. Só a primeira renderização depois do clique (a resposta da ação, como o POST de "Buscar agora") leva a classe de entrada, com `opacity: 0`, `pointer-events: none` e o atraso de 1 s no CSS. As respostas da pergunta de 2 s nunca levam essa classe, e ela fica no envoltório, que não tem `id`, para o assentamento do HTMX não copiá-la para a resposta seguinte; assim a barra não some a cada troca. Se a espera acaba antes, nada aparece além do resultado, como hoje (`andamento.html:22-31`).

**Ritmo** (D143.55, D143.62, D143.63). A barra mostra `f(p)`, em que `p` é a fração real do trabalho.

- `p` soma as etapas com peso: coleta 80%, detalhes 12%, cotações 3% e encaixe 5% (proposta). A etapa que não roda nesta execução sai (detalhes com o enriquecimento desligado, cotações com a conversão desligada), e as outras crescem na mesma proporção. Na coleta, `p` anda pelas consultas prontas sobre o total planejado; nos detalhes, pelas vagas completadas sobre as da fila; cotações e encaixe, que não têm contagem, contam inteiras no fim de cada uma. As etapas que rodam e os pesos se fixam no começo da execução, para `p` nunca descer.
- O passo que trata de novo as vagas guardadas quando as regras mudaram (`reprocessar_se_regras_mudaram`, `agenda/execucao.py:84`) roda entre os detalhes e as cotações e só pesa depois de uma atualização. Ele conta dentro da etapa seguinte que roda (cotações, ou o encaixe com a conversão desligada), sem peso próprio, e enquanto roda a linha diz o texto dele (tabela abaixo).
- `f` segura um pouco o começo e acelera no fim: `f(p) = p^1,25` (proposta; o plano pode trocar o expoente, mantendo as regras abaixo). Ela tem `f(0) = 0`, `f(1) = 1`, cresce sempre e fica abaixo de `p` entre as pontas, então a barra nunca mostra mais do que foi feito. A escolha vem de Harrison, Amento, Kuznetsov e Bell, "Rethinking the progress bar" (UIST 2007): a barra que começa devagar e acelera no fim pareceu mais rápida às pessoas. Um estudo de 2022 achou a barra constante e a que acelera as mais rápidas. Nenhum dos dois favorece frear no fim. O dono tinha descrito o contrário (rápida no começo, freando no fim) e aceitou a curva dos estudos. A HIG sugere um ritmo uniforme; a curva é desvio consciente, pedido pelo dono (Q20), e é leve e fica sempre abaixo de `p`.
- `f` é uma função pura, testada sozinha, sem relógio próprio; o plano escolhe o módulo, respeitando as camadas. O servidor manda o valor pronto na largura do preenchimento e no `aria-valuenow`.

Garantias (https://developer.apple.com/design/human-interface-guidelines/progress-indicators: ser fiel ao andamento, manter a barra em movimento e descrever a etapa sem termo vago):

- **Tempo total igual ao real.** A curva muda só o ritmo, não o fim: a barra chega a 100% quando a execução fecha, nem antes nem depois.
- **Nunca volta.** O valor mostrado sai só do servidor, como função de `p`, do valor de partida e do tempo desde a última mudança de `p`, medido com o relógio injetado (a conta está no avanço lento, abaixo). A casca abre o andamento em toda página (`rotas/execucao.py:78`), então o valor não pode depender da página: toda página e toda aba calculam o mesmo valor, e a troca de página não faz a barra voltar. A pergunta de 2 s não leva o último valor mostrado; ela continua levando só o `visto` (`andamento.html:8`).
- **Nunca chega a 100% antes de terminar.** O teto é 99% (proposta) até a execução fechar.
- **Nunca passa da etapa.** O valor mostrado nunca passa de `L = f(B)`, em que `B` é a soma dos pesos até a etapa atual (o começo da etapa seguinte, medido em `p`). O limite fica no espaço do valor mostrado, não no de `p`: com a coleta parada em `p = 0,6`, a barra mostra cerca de 0,53 e o avanço lento chega perto de `f(0,8) ≈ 0,757`, nunca de 0,8. Assim, quando a etapa fecha, `f(B)` não fica abaixo do que já foi mostrado.
- **Nunca fica parada sem explicação.** Se `p` não muda por 3 s (proposta), a barra avança devagar dentro da etapa atual: a cada 2 s, cobre um décimo do que falta até `L` (proposta), sem nunca chegar lá. A conta é `v = max(f(p), L − (L − partida) · 0,9^n)`, com `n` o número de intervalos de 2 s passados depois dos 3 s sem mudança (zero antes disso). A cada mudança de `p`, a partida passa a ser o maior entre o `f(p)` novo e o valor que a barra mostrava logo antes, e o tempo recomeça; por isso o valor nunca desce. Ao mesmo tempo, a linha diz o que segura a etapa: a espera pedida por um site ou a nova tentativa depois de um erro, com a contagem regressiva, ou os sites que ainda leem.

Movimento: entre uma pergunta e outra, a barra anda até o valor novo numa transição linear de 2 s (proposta), o intervalo da pergunta, e por isso não fica parada entre dois valores. A barra indeterminada corre num laço de 1,5 s (proposta). Com Reduzir movimento, a determinada pula direto para o valor novo, e a indeterminada fica parada, com o trilho cheio a 40% de opacidade (proposta); a linha da etapa carrega a informação.

**Linha da etapa** (D143.57, D143.65). Uma linha, em `--t-callout` (12/15) `--texto-2`: o nome da etapa e, quando há, a contagem, separados por " · ". Cortada com reticências na barra de ferramentas, com o texto inteiro em `title` e em "Ver detalhes". Cada texto nomeia um passo real da execução (`agenda/execucao.py:1-9`), sem termo vago.

| Quando | pt | en |
|---|---|---|
| antes do total | Preparando as consultas | Preparing queries |
| coleta | Lendo {sites} · {feitas} de {total} consultas | Reading {sites} · {feitas} of {total} queries |
| {sites}, mais de dois lendo | Gupy, Lever e mais 3 | Gupy, Lever, and 3 more |
| coleta parada só por espera | Esperando o {site} liberar, {s} s · {feitas} de {total} consultas | Waiting for {site} to allow more requests, {s} s · {feitas} of {total} queries |
| coleta parada só por nova tentativa depois de erro | Tentando o {site} de novo, {s} s · {feitas} de {total} consultas | Trying {site} again, {s} s · {feitas} of {total} queries |
| detalhes | Completando os detalhes das vagas · {feitas} de {total} | Completing job details · {feitas} of {total} |
| regras novas (só depois de uma atualização) | Atualizando as vagas com as regras novas | Updating jobs with the new rules |
| cotações | Convertendo os salários | Converting salaries |
| encaixe | Comparando as vagas com as suas buscas | Matching jobs to your searches |
| fim | Pronto. Vagas novas: {n}. | Done. New jobs: {n}. |
| Conferir agora (Contas) | Conferindo {site} · {feitos} de {total} sites | Checking {site} · {feitos} of {total} sites |
| Esquecer logins | Apagando os logins guardados | Deleting saved sign-ins |
| botão | Ver detalhes · Ocultar detalhes | Show Details · Hide Details |
| estados por site | Na fila · Lendo · Pronto · Falhou · Esperando, {s} s | Queued · Reading · Done · Failed · Waiting, {s} s |

- Todos os textos são proposta, em chaves novas `execucao.etapa.*` nos catálogos `pt` e `en`. Os motivos de parada de hoje (`execucao.parada.*`) continuam.
- A linha mostra até dois nomes de site (proposta); o resto vai contado e aparece por inteiro em "Ver detalhes". Hoje são até cinco (`andamento.html:15-17`).
- A espera pedida por um site (429 ou 503, com ou sem `Retry-After`) e a nova tentativa depois de erro de rede ou 5xx tomam o lugar do nome da etapa só quando são a única coisa que segura a coleta (nenhum outro site lendo). Com outros sites lendo, elas aparecem em "Ver detalhes", no estado "Esperando". A contagem regressiva sai de "fim da espera menos agora", com o relógio injetado; acima de 60 s, vira minutos ("2 min").
- O total igual a 1 usa a chave no singular ("1 de 1 consulta"): o catálogo não tem plural automático, e as duas chaves entram em `pt` e `en`.
- Três exemplos do dono mudam de forma, para seguir os termos e o passo real: "Juntando vagas repetidas" não vira etapa, porque as vagas repetidas se juntam dentro da gravação de cada consulta (`banco/gravacao.py:339`), já contada na coleta; "Comparando as vagas com o seu perfil" diz "suas buscas", o termo do joBot (5.6); "Pronto: 18 vagas novas" segue o "Vagas novas: {n}" de hoje, que não depende de plural.

**Ver detalhes** (D143.57, D143.66). Na barra de ferramentas, o componente inteiro é o botão que abre os detalhes (nome acessível "Ver detalhes do andamento"). No corpo de uma tela, "Ver detalhes" é um botão simples abaixo da linha. Os detalhes abrem numa camada ancorada no componente (atributo `popover`, `.vidro`, raio de 10px), com uma linha por fonte (o "site" do pedido do dono é a fonte, o termo do joBot na 5.6; em Contas, é o site com login): o nome, o estado com ícone e texto e as consultas feitas sobre o total dela. "Falhou" traz o motivo da saúde, com os textos `saude.*` de hoje. Ordem: lendo e esperando primeiro, depois na fila, falhou e pronto. Esc ou clique fora fecha, e o foco volta ao botão. A lista vem no mesmo trecho renderizado no servidor e muda a cada pergunta. Ícones Lucide (proposta, conferidos na versão fixada): na fila `circle-dashed`, lendo `book-open`, pronto `circle-check`, falhou `circle-x`, esperando `clock`.

**Acessibilidade** (D143.67; https://developer.apple.com/design/human-interface-guidelines/accessibility)

- O trilho leva `role="progressbar"`, `aria-valuemin="0"`, `aria-valuemax="100"` e `aria-valuenow`; indeterminado, sem `aria-valuenow`. `aria-valuetext` traz a contagem ("12 de 40 consultas"), e o nome acessível é o "Andamento da busca" de hoje (`execucao.andamento`).
- A região viva (`role="status"`, `aria-live="polite"`) guarda só o nome da etapa. O leitor de tela anuncia a troca de etapa e o fim, nunca cada consulta nem cada segundo da espera. A etapa fica num elemento próprio, trocado só quando ela muda (por `hx-swap-oob`); a barra, a contagem e a espera ficam fora da região viva e mudam a cada pergunta. A rota continua respondendo 204 quando nada do que se vê mudou (`rotas/execucao.py:85-94`).
- Reduzir movimento: como no ritmo acima e na 5.1.
- Mais contraste: borda de 1px `--texto` na barra. Cores forçadas: preenchimento em `Highlight` e borda em `CanvasText`.
- Estado por site com ícone e texto, nunca só por cor.

**O que o lado de trás precisa guardar** (D143.57, D143.68). Aqui está o dado; o plano decide a migração e o esquema.

- **Total planejado da execução**: quantas consultas ela vai fazer, gravado no começo, antes da primeira consulta. A unidade é a de `escopos_prontos` (uma linha de `saude` por consulta, `execucoes.py:52`), para feitas e total baterem. O total é a soma de `len(escopos())` das fontes ligadas, mais 1 para cada fonte cujo `escopos()` falha (ela grava uma linha com escopo vazio, `executor.py:274-278`). Saber o que venceu não muda a conta: o escopo que não venceu, ou que passou do orçamento, ganha a sua linha "no_limite" em `saude` (`executor.py:291-294`) e entra em `escopos_prontos`. Hoje esse total não existe em momento nenhum: a lista de escopos sai por fonte, só dentro de `_Fonte.rodar` (`executor.py:269-296`), depois que o semáforo de `MAX_FONTES_JUNTAS` (`executor.py:57`, `117-119`) libera a fonte. Para gravar o total no começo, `rodar` passa a chamar `escopos()` de todas as fontes antes do semáforo e a avisar o total por um chamável injetado; isso muda o executor. Sem total, a barra é indeterminada.
- **Feitas**: hoje `escopos_prontos` conta todas as linhas de `saude` da execução (`execucoes.py:267`), inclusive as "desligada" gravadas para as fontes desligadas (`agenda/execucao.py:120-121`). A consulta de `execucao_atual` passa a excluir `estado = 'desligada'`, e essas linhas ficam fora do total e das feitas.
- **Etapa atual**: preparando, coleta, detalhes, regras novas, cotações, encaixe ou fim, com feitas e total quando a etapa tem contagem (nos detalhes, o total da fila de detalhes). Na mesma linha, o instante da última mudança de `p` e o valor de partida da barra naquele instante, para o avanço lento e o "nunca volta" saírem só do servidor (Ritmo, acima).
- **Estado por fonte na execução**: na fila, lendo, pronto, falhou ou esperando, com as consultas feitas e o total da fonte e, na espera, o instante em que ela acaba. Hoje `execucao_fonte` guarda só o começo e o fim (`execucoes.py:216-235`).
- O núcleo não importa o banco: o executor avisa o total planejado e o fim de cada consulta, e o cliente HTTP avisa toda espera, com o instante do fim e o motivo, por chamáveis injetados. O cliente chama o de espera antes de cada `relogio.dormir` de um pedido: 429 e 503, com `Retry-After` ou com as esperas de 30, 60 e 120 s (`nucleo/http.py:21`, `434-450`), e as novas tentativas depois de erro de rede ou 5xx (`http.py:389-392`, `452-456`). Os chamáveis seguem o modelo de `ao_comecar_fonte` e `ao_terminar_fonte` (`executor.py:105-106`). A agenda grava de melhor esforço, como as marcas de hoje (`agenda/execucao.py:134-146`): banco travado não derruba a busca.
- Gravação por `INSERT ... ON CONFLICT DO UPDATE`; nada é apagado. A etapa e o estado do site mudam a própria linha.
- "Conferir agora" (Contas) usa os mesmos dados, com um site por conta. "Esquecer logins" não precisa de dado novo: uma etapa só, sem total.

## 6. Riscos

- **Texto menor.** 13px é bem menor que os 17px de hoje. A opção "Maior" devolve os 17px. O padrão pode ser revisto depois do ok de Vagas.
- **Contraste dos fundos novos.** Os valores de contraste deste documento são cálculo nosso. Se `test_contraste.py` reprovar um par, o tom do texto escurece (claro) ou clareia (escuro) até passar; o fundo não muda.
- **Vidro em navegador sem suporte.** `prefers-reduced-transparency` só existe nos navegadores Chromium; o Firefox e o Safari caem no vidro sempre, menos com mais contraste. O `@supports` cobre quem não tem `backdrop-filter`.
- **Atalhos tomados pelo navegador.** ⌘, e ⌘K podem não chegar à página em alguns navegadores. Todo atalho tem um caminho na tela.
- **Contagens em toda página.** `contar_abas` faz uma consulta por aba, e Destaques soma o custo de `_ids_destaques`, que hoje roda só em Vagas e só com Destaques ligados. As duas passam a rodar em toda página com lateral. Se ficar lento, a seção de Vagas da lateral passa a vir por `hx-get` depois da carga.
- **Modo app.** Cada navegador e sistema tem o seu caminho. O que não for achado cai na aba comum, como hoje. Flatpak e Snap não estão na lista e caem na aba comum.
- **Testes de tela.** A troca da casca mexe em muitos testes de tela e de integração (seção 7). Eles rodam no Actions, numa branch `lote/`.
- **Ícones.** Os nomes do mapa são conferidos na versão fixada do Lucide; um nome que não existir é trocado por outro do mesmo sentido.
- **Pesos do progresso.** Os pesos das etapas são proposta, sem medição. Se uma etapa demorar bem mais que o peso dela, a barra anda devagar dentro da etapa e a linha explica, mas o ritmo deixa de ser uniforme. O plano pode tirar os pesos da duração média das últimas execuções (`execucao` já guarda começo e fim), desde que as garantias da 5.9 continuem.
- **Barra parada por espera longa.** Um `Retry-After` de minutos (até 600 s, `nucleo/http.py:20`) ou as esperas de 30, 60 e 120 s de um 429 ou 503 sem `Retry-After` seguram a coleta inteira quando só falta uma fonte; as novas tentativas depois de erro, de 2 e 4 s, seguram menos. A barra avança pouco (nunca até a etapa seguinte), e a linha mostra a espera com a contagem regressiva; é o comportamento certo, mas pode parecer lento.
- **Transição da barra.** A transição de 2 s depende de o assentamento do HTMX copiar a largura em `style` do preenchimento velho para o novo, pelo mesmo `id`. A versão fixada assenta `class`, `style`, `width` e `height` (`attributesToSettle` em `painel/static/vendor/htmx.min.js`), mas isso só foi lido, não visto na tela. Se não funcionar, a barra pula de valor em valor; o plano confere num teste de tela antes de construir o resto.
- **Mais escrita no banco durante a busca.** O estado por fonte muda a cada consulta e a cada espera. A gravação é de melhor esforço e muda a própria linha; se pesar, o plano junta as marcas no ritmo do batimento de 30 s (`execucoes.py:37`), sem perder a etapa nem a espera.
- **Contagem regressiva em degraus.** A pergunta é de 2 s, então a espera desce de 2 em 2 s. Contar de segundo em segundo exigiria um relógio no navegador; não vale o custo.
- **Contraste da barra.** O par `destaque/trilho-progresso` no escuro dá cerca de 3,55:1, perto do mínimo de 3:1 (cálculo nosso). A contagem em texto carrega a mesma informação. Se o teste reprovar, o trilho escurece; o `--destaque` não muda (D143.24).
- **Curva.** A curva muda a sensação de tempo, não o tempo. O expoente 1,25 é proposta; se parecer lento no começo, o plano o aproxima de 1 (a barra constante), sem passar para menos de 1, que seria frear no fim.

## 7. Testes esperados

Cada mudança segue TDD: o teste muda ou nasce primeiro e falha pelo motivo certo.

**Testes que mudam**

| Teste | Hoje | Depois |
|---|---|---|
| `tests/integracao/test_casca_menu.py:73` (`test_menu_tem_sete_links_pt_e_en`) | 7 links no nav "Principal"/"Main", texto direto no `<a>` | os itens da 5.2 (8 de Vagas com Destaques ligados, Buscas, Empresas, Fontes, Sites, Configurações; Sugeridas com sugestão pendente), texto direto no `<a>` |
| `tests/integracao/test_casca_menu.py:95` (`test_aria_current_so_no_item_da_area`) | `aria-current` no item da área | em Vagas, no item da aba; nas outras áreas, como hoje |
| `tests/tela/test_casca_menu.py:57`, `:71`, `:88` | Tab: pular, marca, 7 itens; foco de 2px; contraste de cada item | a mesma ordem com os itens novos; foco e contraste sobre a lateral |
| `tests/tela/test_casca.py:75` (`test_tema_e_idioma_ficam_depois_de_recarregar`) | botões Sistema, Claro, Escuro e English na casca | os menus de tema e idioma em Configurações > Geral; o tema e o idioma continuam depois de recarregar |
| `tests/tela/test_casca.py:54` (`test_nenhum_pedido_sai_de_127`) | clica em Escuro na casca | troca o tema em Configurações > Geral |
| `tests/tela/test_casca.py:126` (`test_painel_e_translucido`) | `.painel` com blur | a lateral e a barra com blur; `.painel` opaco; com menos transparência ou mais contraste, nenhum `backdrop-filter` ativo |
| `tests/tela/test_casca.py:178` (`test_reduced_motion_desliga_animacao`) | nenhuma transição | nenhuma transição de `transform`; as que sobram com até 150ms |
| `tests/tela/test_configuracoes.py:43`, `:135`, `:155` | menu; tema e idioma por `[data-preferencia]` em Aparência; interruptor pelo teclado | grupo Geral; caixa de marcar pelo teclado onde o interruptor saiu |
| `tests/integracao/test_rota_configuracoes.py:496-499`, `:722` | `data-preferencia` e voltar para `/configuracoes/aparencia` | voltar para `/configuracoes/geral`; o 303 de `aparencia` |
| `tests/integracao/test_rota_preferencias.py:60-144` | tema e idioma | os mesmos, mais `/preferencias/texto` |
| `tests/integracao/test_erros.py:111-136` | páginas de erro com a casca | as mesmas com a lateral |
| `tests/tela/test_primeira_execucao.py:41`, `:72` | fluxo completo; pular o passo 1 segue para o passo 2 | fluxo completo com "Continuar" e "Concluir"; "Pular" em qualquer passo cai em Vagas |
| `tests/tela/test_vagas.py:64`, `tests/integracao/test_rota_vagas.py`, `tests/unidade/test_vagas.py` | `nav.abas` com `aria-current` | as abas na lateral; o seletor de busca e a ordem como menus pop-up |
| `tests/tela/test_vagas.py:150` | "/" foca a busca | continua, com a busca na barra |
| `tests/tela/test_aviso_erro.py`, `tests/integracao/test_rota_aviso_erro.py` | aviso no rodapé; `role='alert'` com aspas simples | aviso sob a barra; aspas simples mantidas |
| `tests/tela/test_buscar_agora.py` | "Buscar agora" e "Sair" no `role=banner` | continua: a barra é o `<header>` filho do `body` |
| `tests/unidade/test_contraste.py` | pares de hoje | pares novos da 5.1 e os valores novos |
| `tests/unidade/test_estaticos.py` | sha256 da Inter e do HTMX; `forced-colors` | também os SVG do Lucide e a licença, pelo `lucide.meta.json` |
| `tests/unidade/test_i18n.py` | mesmas chaves em pt e en | inclui as chaves novas |
| `tests/integracao/test_rota_execucao.py:269-476` (os `test_execucao_atual_*`) | ponto, "consultas prontas", até 5 fontes, "Completando detalhes", 204 sem mudança | a barra (indeterminada sem total, determinada com total), a linha da etapa com a contagem, até 2 nomes e "mais N", a etapa de detalhes; o 204 continua quando nada que se vê mudou |
| `tests/integracao/test_rota_execucao.py:486-536` (fim e parada) | "Busca concluída. Vagas novas: {n}." e os motivos | "Pronto. Vagas novas: {n}." e os mesmos motivos |
| `tests/integracao/test_rota_execucao.py:552` (`test_casca_tem_buscar_agora_sair_e_regiao_aria_live`) | a região inteira é viva | a região viva guarda só o nome da etapa |
| `tests/tela/test_buscar_agora.py:65`, `:97` | o andamento e as vagas novas aparecem | a barra e a linha da etapa aparecem e terminam em "Pronto" |

**Testes novos**

- Unidade: `backdrop-filter` só nas classes `.vidro` e `.vidro-grande` (grep no CSS).
- Integração: `/preferencias/texto` grava `tamanho_texto` e o `<html>` leva `data-texto`; valor fora da lista dá 422.
- Integração: `GET /configuracoes/aparencia` responde 303 para `/configuracoes/geral`.
- Integração: `POST /empresas/sugeridas/{id}/restaurar` volta o estado a `pendente` e `POST /empresas/{id}/restaurar` limpa `removida_em`, sem apagar linha; descartar e remover devolvem a faixa com o formulário de restaurar.
- Integração: ocultar vaga devolve a faixa com o formulário para `/mostrar`; o Desfazer devolve a vaga e a faixa com o formulário para `/ocultar`; o Refazer oculta de novo.
- Integração: `POST /primeira-execucao/pular` grava `meu_pais`, `segundo_plano` falso e `primeira_execucao_concluida`, chama a criação do atalho (falha não prende) e manda para `/vagas`; a rota responde em qualquer passo, sem cair no 404 de `/{passo}`.
- Integração: a lateral leva as contagens (Destaques incluído) e a busca escolhida nos links, também fora de Vagas; a busca escolhida gravada vale quando a URL não traz `busca`.
- Integração: `/vagas?...&vaga=<id>` devolve a página com o detalhe da vaga.
- Integração: o POST de país e moeda grava por `/configuracoes/geral`.
- Tela: ⌘Z dentro do campo de busca não aciona o Desfazer da faixa; ⇧⌘Z refaz.
- Tela: o item Configurações abre o último grupo visto.
- Tela: esquecer logins abre o alerta; "Cancelar" não apaga.
- Tela: ⌘K e Ctrl+K abrem a paleta; Esc fecha; Return executa.
- Tela: o menu de contexto abre com o botão direito e com Shift+F10.
- Tela: apagar busca abre o alerta; "Cancelar" não apaga; Esc cancela.
- Tela: abaixo de 900px a lateral recolhe; a 360px não há rolagem lateral; com a coluna entre 640 e 860px o detalhe abre sobreposto.
- Tela: com `data-janela="inativa"` a seleção fica cinza.
- Unidade: a escolha do navegador do modo app, com o executor e a busca de arquivos injetados (Chrome achado; só o Chromium do joBot; nada achado cai na aba comum); o chamável do Chromium não é chamado quando o passo 1 acha navegador.
- Unidade: `sistema` continua sem importar `navegador` (o teste de camadas já cobre).
- Unidade, curva pura (5.9): `f(0) = 0` e `f(1) = 1`; numa grade de `p`, `f` cresce sempre e fica em `p` ou abaixo; o valor mostrado, calculado de `p`, da partida e do tempo com o relógio injetado, nunca é menor que o anterior, inclusive quando `p` muda depois de um avanço lento; com o avanço lento, ele nunca passa de `f(B)`, e quando a etapa fecha o valor não desce; fica em 99% ou menos até o fim e chega a 100% só com a execução fechada; tirar uma etapa redistribui os pesos e a soma continua 100%.
- Unidade: o cliente HTTP chama o chamável de espera com o instante do fim e o motivo em toda espera: 429 e 503 com `Retry-After`, 429 e 503 sem ele (30, 60 e 120 s) e as novas tentativas depois de erro de rede ou 5xx (2 e 4 s); o executor chama o de total planejado antes da primeira consulta (com uma fonte cujo `escopos()` falha contando 1 e um escopo que não venceu contando 1) e o de fim de consulta; relógio injetado, sem tempo real.
- Integração (banco): o total planejado, a etapa e o estado por fonte gravam com `ON CONFLICT` e mudam a própria linha; as linhas "desligada" ficam fora do total e das prontas (a contagem de `execucao_atual` deixa de contá-las); uma gravação que falha não derruba a busca.
- Integração: `/execucao/atual` sem total devolve a barra indeterminada, sem `aria-valuenow`, e "Preparando as consultas"; com total, a largura e o `aria-valuenow` da curva e "{feitas} de {total} consultas"; com a coleta parada só por espera, "Esperando o {fonte} liberar, {s} s", e só por nova tentativa, "Tentando o {fonte} de novo, {s} s", com `s` tirado do relógio injetado; duas páginas diferentes pedidas no mesmo instante mostram o mesmo valor, e o valor de uma pergunta nunca é menor que o da anterior; a região viva só muda quando a etapa muda.
- Tela: "Ver detalhes" abre a lista por fonte com estado em ícone e texto; Esc fecha e o foco volta ao botão.
- Tela: uma espera de menos de 1 s não mostra o componente; depois de aparecer, a barra continua visível entre duas perguntas de 2 s; entre duas perguntas, a largura do preenchimento anda numa transição; com Reduzir movimento, a barra não tem transição nem laço.

## 8. O que fica para o construtor

- **Ordem do trabalho** (D143.9, D143.10, D143.54):
  1. Base: tokens, ícones, casca nova (lateral, barra, faixas), Configurações > Geral com tema, idioma e tamanho do texto, o componente de progresso da 5.9 (ele mora na barra) e os testes da casca. A Base inclui o ajuste mínimo das telas de hoje para elas continuarem funcionando e passando nos testes dentro da casca nova, ainda sem o redesenho.
  2. Vagas: lista, detalhe, itens da lateral com contagem, Desfazer, menu de contexto e paleta.
  3. Base e Vagas ficam numa branch longa do visual, que passa pelo CI em branches `lote/`, e não entram na `dev` antes do ok do dono (D140.8: enquanto não há ok, descartar a branch desfaz tudo). O ok é o portão: as etapas 4 e 5 esperam por ele, para nada ser refeito se o dono pedir mudança na base.
  4. Depois do ok: Detalhe, Buscas, Empresas e Sugeridas (com as rotas de restaurar), Fontes, Sites, Configurações, primeira execução (depois da T241, com os três passos), erro e Saiu. Com o ok, a branch entra na `dev` do jeito de sempre.
  5. Contas (D139): a tela e a faixa entram sobre a base nova. O lado de trás segue em paralelo desde já.
  6. Janela do modo app: não muda nenhuma tela, então não espera o ok; entra na `dev` sozinha, com o CI verde.
  7. O lado de trás do progresso (os dados da 5.9: total planejado, etapa e estado por fonte, e os chamáveis do núcleo) também não muda tela: pode entrar na `dev` antes, sozinho, com o CI verde, e a tela de andamento de hoje continua igual até a Base (D143.70).
- Nada da seção 10 trava a ordem acima: todas as perguntas foram respondidas.
- O desenho exato do CSS, os pontos da curva `linear()` (pelo menos 20), os nomes das classes novas e a divisão do JavaScript em funções.
- A versão do Lucide a fixar e a lista final dos ícones usados.
- Onde ler `tamanho_texto` junto do `tema` para o `<html>` (procure `data-tema` em `base.html:21`).
- A lista de caminhos de cada navegador no Mac e no Windows, conferida na hora.
- Rodar `test_contraste.py` e ajustar o tom do texto que não passar.
- O módulo da curva do progresso e o esquema dos dados da 5.9 (com a migração e os gatilhos conferidos, `padroes.md`).

## 9. Pontos que batem com o que já existe

- Os endereços continuam; as abas viram links da lateral para os mesmos `/vagas?aba=<chave>`.
- As rotas `/preferencias/tema` e `/preferencias/idioma` continuam; `/preferencias/texto` copia o jeito delas.
- O Desfazer de Ocultar usa a rota `/mostrar` que já existe.
- O 303 de `aparencia` para `geral` segue o 303 de `sites-com-login` para `contas` (D139.25).
- O `sem_barra` da página de despedida é o modelo da janela sem lateral do assistente.
- `contar_abas` já dá as contagens das abas, e `_ids_destaques` a de Destaques.
- A rota `/ocultar` já existe e é o Refazer.
- `abrir_painel` já recebe o abridor por parâmetro; o modo app é outro abridor.
- A Inter embutida com `meta.json` é o modelo do Lucide.
- O anel de foco, os pares de contraste, o bloco `forced-colors` e o critério de movimento reduzido continuam valendo.
- A ADR 0008 já diz "modo claro/escuro seguindo o sistema, com chave manual": a recusa do dono bate com ela, e a ADR não muda.
- O progresso usa a rota `/execucao/atual`, a pergunta de 2 s, o `visto` e o 204 de hoje (`rotas/execucao.py:85-94`); o valor mostrado sai só do servidor, e a pergunta não leva parâmetro novo.
- Os chamáveis novos do núcleo seguem `ao_comecar_fonte` e `ao_terminar_fonte` (`executor.py:105-106`), e a gravação de melhor esforço segue a de `agenda/execucao.py:134-146`.
- As rotas de restaurar seguem o par `/ocultar` e `/mostrar` da vaga: uma ação e o seu inverso, sem apagar nada.

## 10. Perguntas respondidas

Todas as perguntas desta seção foram respondidas em 2026-11-16. Não sobra pergunta que trave o plano: a Base, Vagas e as telas depois do ok podem ser planejadas já. As respostas da sessão continuam "para confirmar" com o dono, como as outras escolhas da sessão, mas não travam nada; se o dono trocar uma delas, muda o texto e o teste daquele ponto.

**P1. Nome e endereço do grupo Geral.** Respondida pela sessão, para confirmar (D143.22). Slug `geral`, primeiro da lista. `GET /configuracoes/aparencia` responde 303 para `/configuracoes/geral`. O 303 cobre só o GET, então o POST de país e moeda também passa a `/configuracoes/geral` (5.4).

**P2. Lugar de Sugeridas, Sites e Configurações na lateral.** Respondida pelo dono em 2026-11-16, opção (a) (D143.58). Sugeridas sob Empresas só quando há sugestão esperando; Sites depois de Fontes; Configurações no fim da lateral e no ⌘, (5.2).

**P3. Desfazer em descartar sugerida e remover empresa.** Respondida pela sessão, para confirmar (D143.36), seguindo o pedido do dono de Desfazer no lugar de pergunta (D143.16). Rotas novas de restaurar, com a faixa de Desfazer. Apagar busca e remover site continuam com o alerta de confirmação (D143.37) (5.4).

**P4. O que a linha de vaga mostra.** Respondida pelo dono em 2026-11-16, opção (a) (D143.59). Três linhas de texto, cerca de 64px (proposta): título com o encaixe; empresa e local; salário, selos e data. Botões no detalhe e no menu de contexto (5.2).

**P5. Tema também na barra de ferramentas.** Respondida pela sessão, já anunciada ao dono, para confirmar (D143.21). O tema fica só em Configurações > Geral e na paleta ⌘K, com padrão Sistema (5.1).

**P6. Notificações do navegador e desconectar um site só.** Respondida pelo dono em 2026-11-16 (D143.60). Ele viu e aceitou: os dois ficam fora do escopo.

**Progresso (perguntas 20 a 22 da rodada).** Respondidas pelo dono em 2026-11-16 (D143.55 a D143.57). O ritmo, os lugares e a linha da etapa estão na 5.9.

**Valores marcados "(proposta)".** Continuam valendo para construir agora e são conferidos depois num Mac (D143.31). Não travam o plano.

## 11. Todas as decisões

**Do dono, primeira rodada (2026-11-15)**

1. (dono) Visual de app do Mac no painel inteiro, no assistente da primeira execução e no instalador: protótipo no Canvas agora, instalador real na fase 3 (D140.1).
2. (dono) Referência: as HIG atuais para o Mac; ideias e fatos públicos sim, nenhum arquivo da Apple (D140.2).
3. (dono) Estrutura do Mail: lateral com Destaques de hoje, Todas, Novas, Fecham logo, Salvas, Candidatei, Programas e Ocultas; depois Buscas, Empresas e Fontes; barra com a busca; lista e detalhe. Os endereços não mudam (D140.3).
4. (dono) Configurações no jeito dos Ajustes do Sistema, com a lista de grupos à esquerda e a rota `/configuracoes/{grupo}` (D140.3). É desvio consciente da HIG, que no Mac põe os ajustes numa janela com barra de painéis: cada grupo tem o seu endereço.
5. (dono) Material translúcido da Apple, sólido com "Reduzir transparência" ou "Aumentar contraste" (D140.4).
6. (dono) Janela no modo app do Chrome, Edge ou Chromium; senão o Chromium do Playwright do joBot; senão aba comum. Entra no lote visual (D140.5).
7. (dono) A fonte do sistema no Mac (SF); a Inter nos outros sistemas (D140.6).
8. (dono) Ícones Lucide embutidos, com o arquivo de licença (D140.7).
9. (dono) Construído no painel de verdade, numa branch; Vagas primeiro para o ok do dono (D140.8).
10. (dono) O lado de trás de Contas segue em paralelo; a tela e a faixa de Contas esperam a base visual (D139.15, D140.9).
11. (dono) Fase 3: app de desktop em Tauri com botões de janela (D142). Até lá, a moldura do sistema; o painel não desenha botões de janela nem barra de título.

**Do dono, segunda rodada (2026-11-15)**

12. (dono) Texto de 13px em controles e listas, de 14 a 15px na descrição da vaga, e opção de tamanho do texto em Configurações.
13. (dono) Tema: o dono recusou tirar o seletor. A pessoa escolhe Sistema, Claro ou Escuro, como a ADR 0008 já diz. É desvio consciente da recomendação da HIG.
14. (dono) O seletor de idioma pt/en sai da barra e vai para Configurações > Geral.
15. (dono) Paleta de comandos no ⌘K (Ctrl+K fora do Mac) e menu de contexto no botão direito; sem barra de menus falsa.
16. (dono) Descartar e arquivar sem pergunta de confirmação, com Desfazer.
17. (dono) O aviso do Desfazer é uma faixa que fica até ser dispensada, não um aviso que some sozinho.
18. (dono) Primeira execução com 3 passos e "Pular" sempre visível; quem pula cai em Vagas com os padrões.
19. (dono) Mesmo visual no Windows e no Linux; só a fonte muda para a Inter.
20. (dono) As abas de Vagas viram itens da lateral; sem controle segmentado.

**Da sessão, para confirmar com o dono**

21. (sessão) O seletor de tema fica em Configurações > Geral, junto do idioma e do tamanho do texto, com padrão Sistema, e na paleta de comandos; sai da barra e não fica na barra de ferramentas (era a P5, respondida pela sessão e já anunciada ao dono).
22. (sessão) Grupo Geral primeiro da lista, com tema, idioma, tamanho do texto, país e moeda; slug `geral` e 303 do `GET /configuracoes/aparencia`; o 303 cobre só o GET, e o POST de país e moeda também passa a `/configuracoes/geral` (era a P1).
23. (sessão) Tamanho do texto: Padrão 13px, Grande 15px e Maior 17px, na chave `tamanho_texto`, em `<html data-texto>`, pela rota `POST /preferencias/texto`.
24. (sessão) Cor de destaque fixa em #0071e3.
25. (sessão) Vidro só na lateral, na barra e nas camadas que flutuam (menus, paleta, alerta, sheet); conteúdo opaco, e as faixas de aviso também (o `.painel` perde o vidro); lista e detalhe rolam no próprio contêiner, sem nada por baixo do vidro; fundo do vidro por `color-mix` de `--solido-barra`; sólido com menos transparência, com mais contraste ou sem `backdrop-filter`; sem vidro na janela inativa.
26. (sessão) Molas sem rebote no app todo; rebote de 0,6% só no sheet e no detalhe sobreposto; a mola de hoje sai; movimento reduzido vira fade de 120ms.
27. (sessão) Atalhos da 5.5: ⌘, ⌘K ⌘Z ⇧⌘Z ⌘? Esc ⌘. / setas Home End J K Return; ⌘Z e ⇧⌘Z só fora de campo de texto; ⌘F e ⌘A ficam com o navegador (a lista é de seleção única, sem ação em lote; o ⌘A da rodada sai porque não teria o que selecionar); sem ⌘R, ⌘N e ⌘W; Ctrl fora do Mac; ⌘K como conflito declarado.
28. (sessão) Caixa de marcar na maior parte de Configurações; interruptor só onde se quer destacar.
29. (sessão) Um tamanho de lateral (médio), com as medidas em variáveis CSS; contagem em texto simples, sem pílula.
30. (sessão) Escrita: só a primeira maiúscula em pt-BR, Title Case em en, botão no infinitivo, "você", zero humor em erro.
31. (sessão) Valores marcados "(proposta)" aceitos agora e conferidos depois num Mac com o Medidor de Cores Digital.
32. (sessão) Sugeridas como segundo nível sob Empresas, Sites depois de Fontes e Configurações por último. Confirmado pelo dono em 2026-11-16 (D143.58, era a P2).
33. (sessão) Seções "Vagas" e "Onde buscar"; contagens renderizadas no servidor em toda página com lateral, por um ajudante único em `painel/` que junta `contar_abas` (abas) e `_ids_destaques` (Destaques de hoje); os links levam a busca escolhida (D143.50).
34. (sessão) O seletor de busca e a ordem de Vagas viram menus pop-up na barra da lista. O de busca lista só as buscas, com 2 ou mais, como hoje; não há "Todas as buscas", porque encaixe, nota e Destaques são por busca.
35. (sessão) A lateral recolhe pela largura da janela (`@media`: abaixo de 900px recolhida, abaixo de 640px faixa no alto); lista e detalhe pela largura da coluna de conteúdo (container query): detalhe em coluna com 860px ou mais, sobreposto de 640 a 860px, página própria abaixo de 640px e por link.
36. (sessão) Desfazer: Ocultar usa a rota `/mostrar`; ⌘Z aciona a faixa visível. Refazer: depois do Desfazer, a faixa passa a "Vaga mostrada de novo" com "Refazer", pela rota `/ocultar`, e ⇧⌘Z o aciona. Um nível só, sem histórico: desvio consciente da HIG, que pede vários desfazer. A faixa fica até a pessoa fechar, com duas exceções: outra ação desfazível toma o lugar dela, e uma página nova carregada inteira a tira; trocas por HTMX dentro de Vagas não a tiram. Descartar sugerida e remover empresa rodam sem pergunta e com a faixa de Desfazer, por duas rotas novas de restaurar (`POST /empresas/sugeridas/{id}/restaurar` volta a `pendente`; `POST /empresas/{id}/restaurar` limpa `removida_em`), sem apagar nada (era a P3).
37. (sessão) Apagar busca, remover site e Esquecer logins, que não voltam, pedem confirmação num alerta (a pergunta de hoje do Esquecer logins vira o alerta); o botão da ação não leva o estilo destrutivo, porque a pessoa a escolheu; nenhum botão é o padrão, e "Cancelar" nunca é.
38. (sessão) Paleta num `<dialog>` com campo e lista; comandos renderizados no servidor nos dois idiomas; botão na barra.
39. (sessão) Menu de contexto da linha de vaga: Abrir, Abrir no site da vaga, Salvar, Ocultar, Copiar link; abre também pela tecla de menu e por Shift+F10; tudo também está no detalhe.
40. (sessão) Passos da primeira execução: "O que você procura?", "Sites com login (opcional)" e "Segundo plano"; a tela nova entra depois da T241, já com os três; "Tudo pronto" não conta. Rota `POST /primeira-execucao/pular`, registrada antes de `/{passo}`: grava `meu_pais`, `segundo_plano` falso e `primeira_execucao_concluida`, cria o atalho do menu no Linux como o "desligar" do passo 2 (DR-37), sem prender em falha, e manda para Vagas. Sem lateral durante o assistente.
41. (sessão) Modo app: ordem de busca da 5.4, opção `--app=`, perfil próprio `<dados>/janela/` para o Chromium do joBot, nunca o perfil do login; o `cli` passa a `sistema` um chamável do `navegador` que devolve só o Chromium do Playwright, chamado só quando o passo 1 não acha navegador.
42. (sessão) Faixas sob a barra na ordem erro, versão, contas e Desfazer (contas logo depois da versão, como na D139.23); opacas, sem vidro; erro, versão e Desfazer com botão de fechar, contas sem (D139.13); o `#aviso-erro` sai do rodapé e mantém `role='alert'` com aspas simples.
43. (sessão) O item Configurações e o ⌘, abrem o último grupo visto (guardado em `localStorage`); sem registro, e sem JavaScript, abrem Geral.
44. (sessão) Ícones por `::before` com `mask-image`; o `<a>` fica só com texto.
45. (sessão) `--trilho` continua em hex, porque entra no par `texto/trilho`.
46. (sessão) O "descartar" do dono, na vaga, é o Ocultar de hoje; "arquivar" não existe no joBot e não entra.
47. (sessão) Sem `letter-spacing` fixo; a fonte do sistema ajusta sozinha.
48. (sessão) Fora do escopo: cor de destaque escolhida pela pessoa; tamanhos pequeno e grande da lateral e reordenar itens; barra de menus; seleção de várias vagas e ações em lote. A API de notificações do navegador e desconectar um site só também ficam de fora: o `notify-send` do agendador cobre o aviso, e "Esquecer logins" existe. O dono aceitou em 2026-11-16 (D143.60, era a P6).
49. (sessão) A ADR 0008 não muda: ela já diz "chave manual" para o tema e não diz onde ficam os seletores.
50. (sessão) A busca escolhida em Vagas é gravada na chave `busca_escolhida` (`ON CONFLICT`). A busca da URL vence; sem ela, vale a gravada; se a gravada sumiu ou foi desligada, a primeira ativa. A lateral usa essa busca em toda página.
51. (sessão) Escolher uma vaga põe `vaga=<id>` no endereço de `/vagas` (`hx-push-url`); com ele, o servidor manda o detalhe junto, e recarregar ou voltar abre a mesma vista. `/vagas/{id}` continua sendo o link direto.
52. (sessão) O `<form id="busca">` fica na barra da lista; o campo da barra de ferramentas e a ordem entram nele pelo atributo `form="busca"`; a busca continua por Enter. "Mais filtros" abre num `<details>` abaixo da barra da lista; os avisos de filtro e o "sem critério" ficam abaixo dela, sem botão de fechar; na aba Programas, as páginas ficam numa seção própria abaixo das linhas, fora do `listbox`.
53. (sessão) A linha de vaga só tem texto, sem botão nem link dentro, porque é `option` de um `listbox`; as ações ficam no detalhe e no menu de contexto. O que a linha mostra é a D143.59.
54. (sessão) Base e Vagas ficam numa branch longa do visual, que passa pelo CI em branches `lote/`, e só entram na `dev` com o ok do dono; as outras telas esperam o ok. A Base traz o ajuste mínimo das telas de hoje para elas funcionarem na casca nova. A janela do modo app não muda tela e entra na `dev` sozinha.

**Do dono, terceira rodada (2026-11-16)**

55. (dono) Ritmo da barra (Q20): a barra segue o andamento real, com uma curva que segura o começo e acelera no fim, como em Harrison, Amento, Kuznetsov e Bell, "Rethinking the progress bar" (UIST 2007). O tempo total é o real. A barra nunca volta, nunca chega a 100% antes do fim, nunca fica parada sem explicação e nunca mostra mais do que a etapa seguinte permite. É a barra lisa do Mac. A curva exata é proposta da sessão (D143.62).
56. (dono) Onde (Q21): toda espera de mais de 1 s usa o mesmo componente: "Buscar agora", a primeira busca da primeira execução, "Conferir agora" de Contas, "Esquecer logins" e o instalador (Canvas agora, Tauri na fase 3). Espera curta não mostra nada. Sem total, a barra é indeterminada e passa a determinada quando o total aparece.
57. (dono) Linha da etapa (Q22): uma linha com a etapa e a contagem, a espera de cada site com contagem regressiva e "Ver detalhes" com a lista por site. O lado de trás guarda o total planejado, a etapa atual e o estado de cada site.
58. (dono) Lateral (Q23): opção (a), a da 5.2: Sugeridas como segundo nível sob Empresas, Sites depois de Fontes e Configurações por último (era a P2).
59. (dono) Linha da vaga (Q24): opção (a), três linhas de texto e cerca de 64px: título com o encaixe; empresa e local; salário, selos de estado e data. Botões no detalhe e no menu de contexto (5.2, 5.8; era a P4).
60. (dono) Notificações do navegador e desconectar um site só ficam fora deste lote (era a P6).

**Da sessão, terceira rodada, para confirmar com o dono**

61. (sessão) O componente é um trilho com `role="progressbar"` e um preenchimento de `id` fixo com a largura em `style`, para o assentamento do HTMX animar a troca (o `<progress>` nativo não anima o `value`); 6px de altura, sem indicador giratório; a barra indeterminada cobre o começo. A barra na barra de ferramentas é desvio consciente da HIG, que ali prefere o giratório, pedido pelo dono (Q21). Token novo `--trilho-progresso`, igual a `--trilho` no claro e #1e1e1e no escuro, pelo contraste de 3:1 com o `--destaque` (5.9).
62. (sessão) Curva `f(p) = p^1,25`, função pura testada sozinha; é desvio consciente da HIG, que sugere ritmo uniforme, pedido pelo dono (Q20), e é leve e fica abaixo de `p`. O valor mostrado sai só do servidor, de `p`, do valor de partida e do tempo desde a última mudança de `p` (relógio injetado), e por isso é o mesmo em toda página e nunca volta; a pergunta de 2 s não leva parâmetro novo. Teto de 99% até a execução fechar; nunca passa de `f(B)`, com `B` a soma dos pesos até a etapa atual; parado por 3 s, avança um décimo do que falta até `f(B)` a cada 2 s. Transição linear de 2 s entre perguntas.
63. (sessão) Pesos das etapas: coleta 80%, detalhes 12%, cotações 3% e encaixe 5%; a etapa que não roda sai, e as outras crescem na mesma proporção; etapas e pesos se fixam no começo da execução. O passo das regras novas (`reprocessar_se_regras_mudaram`) conta dentro da etapa seguinte que roda, sem peso próprio, com texto próprio na linha.
64. (sessão) Limiar de 1 s contado do clique, por atraso no CSS só na primeira renderização depois do clique, nunca nas respostas da pergunta de 2 s; espera mais curta mostra só o resultado, como hoje.
65. (sessão) Textos da tabela da 5.9, em chaves `execucao.etapa.*` nos dois catálogos, com chave no singular para total 1; até dois nomes de site na linha. Três exemplos do dono mudam de forma: "Juntando vagas repetidas" não vira etapa (acontece dentro da gravação de cada consulta), "seu perfil" vira "suas buscas" e "Pronto: 18 vagas novas" vira "Pronto. Vagas novas: {n}.".
66. (sessão) "Ver detalhes" abre uma camada `popover` ancorada no componente, com uma linha por fonte: nome, estado com ícone e texto, consultas feitas sobre o total e, em "Falhou", o motivo da saúde. Esc ou clique fora fecha e devolve o foco.
67. (sessão) A região viva guarda só o nome da etapa, trocado por `hx-swap-oob`; barra, contagem e espera ficam fora dela. A rota continua com o `visto` e o 204. Mais contraste e cores forçadas como na 5.9.
68. (sessão) O lado de trás guarda o total planejado, a etapa atual com a sua contagem, o instante da última mudança de andamento e o valor de partida da barra, e o estado por fonte com o fim da espera. O total é a soma de `len(escopos())` das fontes ligadas, mais 1 para cada fonte cujo `escopos()` falha (`executor.py:269-296`); para tê-lo no começo, `rodar` chama `escopos()` de todas as fontes antes do semáforo, o que muda o executor. As feitas e o total ficam na unidade de `escopos_prontos`, e a consulta de `execucao_atual` passa a excluir as linhas "desligada". O núcleo avisa por chamáveis injetados, e o cliente HTTP avisa toda espera (429 e 503, com ou sem `Retry-After`, e as novas tentativas depois de erro); a agenda grava de melhor esforço, por `INSERT ... ON CONFLICT DO UPDATE`, sem apagar nada. O plano decide a migração e o esquema.
69. (sessão) A tela "Tudo pronto" da primeira execução é exceção ao assistente sem barra: mostra "Buscar agora" e o andamento na barra.
70. (sessão) O lado de trás do progresso pode entrar na `dev` sozinho, antes da casca, mostrando o componente na barra de hoje; o componente visual entra na Base.
71. (sessão) Parar uma busca no meio pelo progresso fica fora deste lote. A HIG sugere deixar parar quando é seguro; parar no meio pede desenho próprio (o que fica gravado da consulta em curso e como a execução fecha), e o dono não pediu.

**Valores que são proposta** (D143.31)

- Cores: `--texto-2` claro #636366; `--texto-3`; `--fundo` #ececec e #1e1e1e; `--superficie` escuro #1e1e1e; `--sob-pagina`; `--solido-barra`; `--solido-elevado`; `--segmento` escuro #5a5a5e; `--separador`; `--hover`; `--pressionado`; `--selecao-inativa`; `--veu`; `--fundo-controle`; `--borda-controle`; fundo das faixas com 10 a 12% da cor do estado; desativado com `opacity` .45.
- Vidro: blur de 24 e 40px, saturação de 1,4, fundos de 72% e 85% de `--solido-barra`, borda de .45 e .12.
- Raios: 6px em controle e item da lateral, 4px na caixa de marcar, 10px em menu, paleta, cartão e faixa, 18px em sheet e alerta.
- Espaço: grade de 4px.
- Sombras: `0 8px 30px`, `0 12px 40px`, `0 20px 60px` e as cores de .25, .30, .55 e .60.
- Tipo: 15px na descrição, 70ch, escala do tamanho do texto (115,4% e 130,8%), cabeçalho de seção da lateral em 11px, texto do alerta em 11px.
- Movimento: 100 a 120ms, 150 a 190ms, 280 a 300ms, 120 a 150ms, teto de 410ms, `--duracao` 190ms, rebote de 0,6%, fade de 120ms no movimento reduzido, 150ms na troca para janela inativa, alerta em 200ms com `scale(.96)`, destaque de 1s na linha que volta.
- Medidas: lateral 240px (180 a 320px), margem de 8px do item da lateral, pega de 8px e passo de 10px do divisor, linha da lateral 28px, barra 52px, linha da lista cerca de 64px (D143.59), itens de 24px no menu de contexto, degraus de coluna de 640 e 860px, detalhe 320 a 380px, sobreposto `min(420px, 60%)`, leitura 680px, degraus de janela de 640 e 900px, busca 180 a 280px, faixa de 36px, alerta de 260px, sheet de 520px, paleta de 560px, interruptor 38x22 e 30x18px, caixa de 14px, ícones de 16, 18 e 20px com traço de 1,5px.
- Progresso: pesos de 80, 12, 3 e 5%; expoente 1,25; teto de 99%; 3 s sem mudança e avanço de um décimo a cada 2 s; transição de 2 s; laço de 1,5 s; trilho a 40% com movimento reduzido; altura de 6px, larguras de 240 e 320px; `--trilho-progresso` escuro #1e1e1e; até dois nomes de site; limiar de 1 s; os ícones dos estados.
- Mapa de ícones do Lucide.
- Textos novos da 5.6 e os da tabela da 5.9.
