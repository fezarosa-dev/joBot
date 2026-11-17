# Fase 3: app de desktop e instalador (desenho)

Data: 2026-11-17. Decisões de origem: ADR 0003, 0017, 0018, 0023; D138 (instalador), D140 e D143 (visual de app do Mac), D142 (app de desktop e botões da janela) e a D171 (respostas do dono de 2026-11-17 e escolhas da sessão). Versão alvo: **0.4.0**.

Fatos sobre o código vêm com `arquivo:linha`, conferidos na `dev` em 2026-11-17. As linhas podem andar: quando não bater, procure o símbolo. Valores marcados "(proposta)" foram escolhidos pela sessão e valem para construir; o dono pode trocar.

## 1. Intenção

Quem usa baixa um arquivo, abre e tem o joBot numa janela própria, com ícone, sem terminal e sem saber o que é Python. A tela que instala tem o mesmo visual de app do Mac do painel (D140) e mostra uma lista de ferramentas para marcar (ADR 0023). Depois disso a janela é só uma moldura em volta do painel, que continua em `127.0.0.1` e não é reescrito (D142.1).

## 2. Objetivos, não objetivos, anti-objetivos

**Objetivos**

- Casca Tauri 2 na pasta `desktop/` (D171.4), com janela própria em volta do painel (D142.1).
- Instaladores de 64 bits gerados pelo mesmo projeto: NSIS no Windows (por usuário, sem admin), AppImage, `.deb` e `.rpm` no Linux (D171.2), e `.dmg` experimental no Mac (D171.3).
- Tela de instalação na primeira abertura da casca: lista de ferramentas com as essenciais travadas, progresso com o componente único (D143.56) e fileira de botões presa ao pé (D144, E17).
- O joBot instalado pelo `uv` embutido, a partir da wheel da release da mesma versão, com sha256 conferido (D171.1).
- Botões da janela: no Mac, os do sistema com a barra sobreposta; no Windows e no Linux, janela sem moldura e três círculos desenhados por nós (D142.3).
- O joBot passa a rodar no Windows (hoje quebra no import de `fcntl`, `src/jobot/sistema/instancia.py:3`) e no Mac (pasta de dados própria).
- Segundo plano no Windows e no Mac, para que fechar a janela siga o segundo plano em todo sistema (D171.7, D171.12).
- Os botões "Atualizar o joBot" e "Encerrar" no painel (ADR 0023, ainda não construídos) e o aviso de versão sem mandar abrir o terminal.
- Workflow de release que publica wheel, restrições com hash, instaladores e `SHA256SUMS`, só com o `GITHUB_TOKEN`.

**Não objetivos**

- IA, Claude Code, Codex e o modelo local no instalador: fase 4 (D139.10).
- Assinatura de código: sem selo na 0.4.0; o pedido ao SignPath Foundation é do dono, quando quiser, e entra depois sem mexer no desenho (D171.5).
- Ícone na bandeja (D171.7).
- Atualização automática da casca: ela avisa e abre a release (D171.8).
- Loja de apps (Microsoft Store, Flathub, Snap).

**Anti-objetivos**

- Reescrever o painel em Rust ou em outro framework de interface.
- Copiar imagem, fonte ou símbolo da Apple (ADR 0016). Os círculos são desenho nosso em CSS.
- npm, bundler ou `node_modules`: a casca usa `withGlobalTauri` e HTML/CSS/JS puros (D171.13).
- Segredo no CI de PR (ADR 0018).
- Apagar dados da pessoa ao desinstalar (regra do projeto: nada é apagado).

## 3. Restrições

- O painel escuta só em `127.0.0.1` e não carrega recurso externo; a CSP é `default-src 'self'`, `connect-src 'self'`, `frame-ancestors 'none'` (`src/jobot/painel/app.py:18-28`). A janela Tauri navega direto para `http://127.0.0.1:<porta>`; nada de iframe.
- O cabeçalho Host aceito é só `127.0.0.1:<porta>` e `localhost:<porta>` (`app.py:48-60`).
- Todo POST exige o token CSRF da página (`src/jobot/painel/seguranca.py:110-124`).
- Dependências fixadas: `==` no `pyproject.toml`; no Rust, `=x.y.z` no `Cargo.toml` e `Cargo.lock` versionado; Actions por hash de 40 dígitos com `# vX.Y.Z` (`tests/unidade/test_repositorio.py:51-64`); atualização à mão no fim da fase (ADR 0021).
- Licenças compatíveis com MIT: Tauri e plugins oficiais são MIT/Apache-2.0; o `uv` é MIT/Apache-2.0.
- Documentos de quem usa e contribui são bilíngues; ADR e `duvidas.md` só em português.
- `tests/unidade/test_ci.py:36-73` trava os jobs do `ci.yml` em `{lint, comuns, tela, ok}`: o Rust ganha workflow próprio (seção 9).

## 4. Como funciona hoje (fatos)

- `jobot serve` sobe painel e agenda num processo, em `127.0.0.1:47615` ou `JOBOT_PORTA` (`src/jobot/cli/servir.py:59`, `src/jobot/sistema/instancia.py:8, 89-94`). Sem porta livre alternativa: porta ocupada sai com código 1 (`servir.py:243-272`).
- Instância única por `<dados>/jobot.lock` com `fcntl.flock`, conteúdo `<pid>\n<porta>\n` (`instancia.py:12-46`); leitura em `pid_e_porta_do_servidor` (`instancia.py:97-106`).
- `GET /saude-local` responde `{"app":"jobot","versao":...}` (`src/jobot/painel/rotas/saude_local.py:13-15`).
- `jobot abrir` sobe o servidor destacado (`Popen(... start_new_session=True)`, DEVNULL; `src/jobot/sistema/abrir.py:269-277`), espera `/saude-local` até 15 s e abre o modo app do navegador (`abrir.py:110-237`).
- `jobot sair` manda SIGTERM ao PID da trava (`abrir.py:240-266`). `POST /sair` faz a parada limpa por HTTP, mas pede CSRF (`src/jobot/painel/rotas/execucao.py:231-245`).
- Pasta de dados: só a regra do Linux (`src/jobot/sistema/pastas.py:14-21`). Planejado na fase 1 (DR-07): `%LOCALAPPDATA%\joBot` e `~/Library/Application Support/joBot`.
- Segundo plano: só systemd (`src/jobot/sistema/segundo_plano_linux.py`). Fora do Linux o passo aparece desativado.
- `jobot atualizar` conhece `clone_git` e `uv_tool`; no `uv_tool` roda `uv tool upgrade jobot` pelo PATH (`src/jobot/sistema/atualizar.py:46-59, 124-130`). O joBot não está no PyPI, então esse upgrade não acha versão nova.
- Aviso de versão: `laco_versao` consulta `api.github.com/.../releases/latest` uma vez por dia, grava `versao_nova` (`src/jobot/agenda/versao.py:33-142`); a faixa `#aviso-versao` manda rodar `jobot atualizar` no terminal (`src/jobot/painel/i18n/pt/aviso_versao.json:2`), o que fere a ADR 0023.
- Tela Ferramentas: só o navegador, com Baixar e Remover (`src/jobot/painel/rotas/configuracoes.py:259-305, 808-895`; `src/jobot/navegador/instalador.py`). Usa `os.killpg` e `start_new_session` (só POSIX, `instalador.py:55-72`).
- Não há workflow de release: as releases foram criadas à mão; tags `vN.N.N` (`git for-each-ref refs/tags`).

## 5. Arquitetura

```
desktop/                     projeto Tauri 2 (Rust), fora do pacote Python
  Cargo.toml, Cargo.lock     versões com =
  tauri.conf.json            + tauri.windows/linux/macos.conf.json
  src/main.rs                arranque, janela, eventos
  src/servidor.rs            achar, subir e parar o joBot (puro, testado)
  src/instalar.rs            baixar, conferir sha256, rodar o uv (puro onde dá)
  ui/                        tela de instalação: index.html, instalador.js, i18n/{pt,en}.json
  ui/painel/                 gerado no build (gitignored): css, fontes e ícones do painel
  binaries/                  uv por alvo (baixado no build, sha256 em uv.meta.json)
  capabilities/*.json        permissões mínimas
```

**Quem fala com quem.** A casca é um processo externo ao joBot: só fala HTTP com o painel e chama o executável `jobot` (e o `uv` embutido). O pacote Python não importa nada da casca. O `test_camadas.py` não alcança Rust; a regra entra na `wiki/Arquitetura.md` (e `Architecture.md`) como nó `desktop/`.

### 5.1 Arranque da casca

1. Plugin `single-instance` (o primeiro registrado): uma segunda abertura só traz a janela existente para a frente.
2. Procura o joBot instalado: o executável `jobot` no diretório de ferramentas do `uv` desta casca (`UV_TOOL_BIN_DIR`, seção 6.2). Não achou: tela de instalação (5.2).
3. Achou: procura o servidor. Lê `<dados>/jobot.lock` com a mesma regra de pasta do Python (seção 7.1); com PID e porta, confirma `GET http://127.0.0.1:<porta>/saude-local` com `app == "jobot"`. Sem servidor, sobe `jobot serve` destacado, como o `subir_servidor` faz (nunca como filho da casca), e espera `/saude-local` até 15 s, de 200 em 200 ms (mesmo prazo de `abrir.py:198-237`).
4. Confere a janela (5.4). Passou: navega para `http://127.0.0.1:<porta>/`. Não passou (WebKitGTK velho): roda `jobot abrir`, que abre o modo app de hoje, mostra uma tela curta dizendo por quê e fecha a própria janela.
5. Falhas: porta ocupada por outro programa, servidor que não responde em 15 s ou `jobot serve` que sai com erro levam a uma tela de erro da casca, com o que fazer, o fim de `<dados>/logs/jobot.log` (últimas 20 linhas) e o botão "Tentar de novo". Texto pt e en.

### 5.2 Tela de instalação (primeira abertura)

Mora na própria casca (`desktop/ui/`), não no NSIS nem no `postinst`: assim é uma tela só nos três sistemas, roda como a pessoa (os `.deb`/`.rpm` instalam como root, mas o `uv tool` é por usuário) e dispensa template NSIS. O NSIS, o AppImage, o `.deb`, o `.rpm` e o `.dmg` levam só a casca e o `uv`.

**Passos** (cada um com o pé preso, D144):

1. **Boas-vindas.** Ícone, "joBot", uma frase do que ele faz, idioma (pt/en, pelo idioma do sistema; troca ali mesmo) e "Continuar".
2. **Ferramentas.** Lista com caixas de marcar:
   - joBot e Python 3.14 (marcados e travados, com "necessário" ao lado; tamanho estimado).
   - Navegador para sites com login (marcado, dá para desmarcar; ~210 MB; frase: "Para o LinkedIn e outros sites em que você entra. Dá para baixar depois em Configurações › Ferramentas.").
   - Se a pessoa desmarca o navegador, os sites com login ficam desligados até ela baixar pela tela Ferramentas (D138.15).
   - A lista mostra só o que esta versão usa (D138.6). O grupo de IA chega na fase 4.
   - Rodapé: "Onde fica" (pasta de dados) e o total a baixar.
3. **Instalando.** Componente de progresso (barra indeterminada até haver total, depois determinada, nunca volta, teto de 99% até o fim; linha da etapa; D143.56-61). Etapas: "Baixando o joBot", "Conferindo o arquivo", "Baixando o Python", "Instalando", "Baixando o navegador" (se marcado), "Abrindo". Sem botão de cancelar no meio (D143.71); fechar a janela pede confirmação num alerta (D143.37) e, se confirmado, para o `uv` e deixa tudo como estava antes (o `uv tool install` é atômico por ferramenta).
4. **Falha.** Diz o que deu errado com o que fazer (sem internet; arquivo não confere: "o arquivo baixado não é o esperado, nada foi instalado"; pouco espaço) e "Tentar de novo".
5. **Pronto.** Sobe o servidor e navega para o painel, que abre o assistente da primeira execução que já existe (`src/jobot/painel/rotas/primeira_execucao.py`). A escolha do navegador não se repete: o passo "Sites com login" do assistente já mostra o estado.

**Visual.** Reaproveita, sem copiar no repositório, o CSS do painel: `base.css` (tokens, vidro, botões, caixa de marcar, alerta, forced-colors, movimento reduzido), `execucao.css` (progresso), o padrão do pé preso de `primeira_execucao.css`, a Inter e os ícones Lucide com as licenças. O `build.rs` da casca copia esses arquivos de `src/jobot/painel/static/` para `desktop/ui/painel/` no build (pasta ignorada pelo git). Um teste Python garante que `desktop/ui/` não tem cópia versionada deles. O markup do progresso segue o de `src/jobot/painel/templates/execucao/_progresso.html` (mesmas classes, papéis e atributos ARIA); a lógica de largura é a do trecho `app.js:1177-1215`, refeita em `instalador.js` (sem Jinja, sem servidor).

**Textos.** `desktop/ui/i18n/pt.json` e `en.json`, com as mesmas chaves (teste Python no molde do `test_i18n.py`). A frase de cada ferramenta diz "baixa X se você marcar", nunca "vem com" (D139.2).

### 5.3 Janela e botões

- **Mac** (`tauri.macos.conf.json`): `titleBarStyle: "Overlay"`, `hiddenTitle: true`, botões do sistema. O painel reserva o espaço deles à esquerda da barra de ferramentas.
- **Windows e Linux**: `decorations: false`. O painel desenha a fileira de três círculos à esquerda da barra lateral (D142.3), em CSS: 12px de diâmetro, 8px entre eles (proposta); vermelho fechar, amarelo minimizar, verde maximizar/restaurar; o símbolo (×, −, +) aparece no hover da fileira; janela inativa deixa os três cinza (`:root[data-janela=inativa]`, que já existe para o vidro). Cores como tokens novos em `base.css`, com o par de contraste gráfico 3:1 contra a barra no comentário `/* contraste-grafico: ... */`. Botões `<button>` com nome acessível (pt/en: "Fechar", "Minimizar", "Maximizar"/"Restaurar"), alcançáveis por teclado, bloco `forced-colors` próprio.
- **Arrastar e maximizar**: a barra de ferramentas e o topo da lateral chamam `startDragging()` no `mousedown` com o botão principal fora de controles, e `toggleMaximize()` no duplo clique. Redimensionar pela borda: o Tauri trata em janela sem moldura no Windows; no Linux depende do gerenciador de janelas (custo aceito na D142.4, conferido na fase 3).
- **Como o painel sabe que está na casca**: a casca acrescenta ` joBot-casca/<versão> (<so>)` ao user agent (`userAgent` da janela). Um middleware lê isso e põe `data-casca="<so>"` no `<html>`. Sem a marca, nada muda: moldura do sistema (D143.11).
- **Ponte**: os círculos e o arraste chamam a IPC do Tauri (`window.__TAURI__`) com uma capability de `remote.urls` só para `http://127.0.0.1:*`, que libera só `core:window:allow-start-dragging`, `allow-toggle-maximize`, `allow-minimize`, `allow-close` e `allow-is-maximized`. O `app.js` só chama a ponte se `window.__TAURI__` existir.
- **Risco 1 (T321 prova primeiro):** a IPC numa origem `http://127.0.0.1` remota. Se a CSP do painel barrar o canal da IPC, a CSP ganha só a origem da IPC do Tauri, e só nas respostas a pedidos com a marca da casca. Se nem assim funcionar, a fileira desenhada não entra e a janela usa a moldura do sistema nos três sistemas; isso muda a D142.3 e volta ao dono antes de seguir.

### 5.4 WebKitGTK no Linux

O painel usa `light-dark()`, `popover`, `@starting-style`, `anchor-name`, container queries e `:has` (`base.css:30-65`, `execucao.css`, `vagas.css`). O WebKitGTK do Ubuntu 22.04 (2.36) não tem vários deles; sem `light-dark()` as cores ficam inválidas e o painel quebra.

Regra: antes de navegar ao painel, a casca carrega uma página local que confere `CSS.supports("color","light-dark(#000,#fff)")`, `"popover" in HTMLElement.prototype`, `CSS.supports("anchor-name","--a")` e `CSS.supports("container-type","inline-size")`. Faltou algum: cai no modo app (5.1, passo 4), com a frase "Seu sistema tem uma versão antiga do componente de janelas; o joBot abriu no navegador." Isso cobre também WebView2 e WKWebView antigos. O CI do Linux gera os pacotes no runner `ubuntu-22.04` (glibc mais antiga para rodar em mais distros); a conferência acontece na máquina de quem usa.

### 5.5 Fechar a janela

Fecha só a janela (D171.7). Se o segundo plano está ligado (configuração `segundo_plano` do banco), o servidor segue. Se está desligado, a casca roda `jobot sair` antes de sair. A casca descobre o estado em `GET /saude-local`, que passa a responder também `"segundo_plano": true|false` (campo novo, sem dado pessoal). O botão "Encerrar" do painel (6.4) para tudo nos dois casos.

### 5.6 Versão nova

Uma checagem só, a do painel (`laco_versao`): a casca não consulta o GitHub (ADR 0014:24, ADR 0018:32 e o interruptor de Privacidade continuam valendo).

- A faixa `#aviso-versao` deixa de mandar abrir o terminal. Texto novo: "Há uma versão nova do joBot: {versao}." com o botão "Atualizar agora" (6.3).
- Na casca, se a versão da casca (pelo user agent) for menor que `versao_nova`, a faixa diz também "A janela do joBot também tem versão nova." e o botão "Baixar a janela nova" faz `POST /abrir-release`, que abre `https://github.com/fezarosa-dev/joBot/releases/latest` no navegador da pessoa pelo Python (mesma abertura de aba comum de `abrir.py`). O painel continua sem carregar nada de fora.

## 6. Mudanças no joBot (Python)

### 6.1 Rodar no Windows e no Mac

- `pastas.py`: `JOBOT_DADOS` vence; Windows `%LOCALAPPDATA%\joBot`; Mac `~/Library/Application Support/joBot`; Linux como hoje. Sem `platformdirs` (DR-07).
- `instancia.py`: a mesma interface (`Trava`, `pid_e_porta_do_servidor`, `porta`) com `msvcrt.locking` no Windows e `fcntl` no resto; import condicional por `sys.platform`. O formato do arquivo não muda.
- Parada no Windows: o `serve` grava `<dados>/sair.token` (0600, `.tmp` + `os.replace`, apagado no fim) com um segredo novo a cada subida; `POST /sair` aceita, além do CSRF, o cabeçalho `X-Jobot-Sair` com esse segredo e só de `127.0.0.1`. `sair_do_servidor` usa esse caminho no Windows; no Linux e no Mac continua o SIGTERM (sem mudança de comportamento).
- Processos: `start_new_session` e `os.killpg` ganham o ramo Windows (`CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS`, `terminate()` e `kill()` no processo) em `abrir.py` e `navegador/instalador.py`, atrás de uma função só em `sistema` (ex.: `sistema/processo.py`). O `navegador` já importa `sistema`.
- Modo app no Windows e no Mac: já existe a busca (`abrir.py:27-36, 114-139`).

### 6.2 Instalação pela casca

- A casca roda o `uv` com `UV_TOOL_DIR`, `UV_TOOL_BIN_DIR`, `UV_PYTHON_INSTALL_DIR` e `UV_CACHE_DIR` dentro de uma pasta da casca por usuário (Linux `~/.local/share/jobot-app/`, Windows `%LOCALAPPDATA%\joBot\app\`, Mac `~/Library/Application Support/joBot/app/`) (proposta). Assim a instalação da casca não briga com um `uv` que a pessoa já tenha.
- Comando: `uv tool install --python 3.14 --constraints <restricoes.txt> <wheel local>`. A casca baixa a wheel e o `restricoes.txt` da release da mesma versão e confere o sha256 dos dois em Rust contra as constantes gravadas no build (env `JOBOT_WHEEL_SHA256`, `JOBOT_RESTRICOES_SHA256`) antes de chamar o `uv`.
- `restricoes.txt` sai do `uv.lock` (`uv export --no-dev --no-emit-project --format requirements-txt`, com hashes). **Risco 2 (T322 prova):** se o `uv tool install` não exigir os hashes das dependências pelas restrições, a garantia fica só na wheel do joBot e nos pinos `==`; a T322 mede e registra o limite em `docs/decisions/` e no README.
  - **Medido (T322, `uv 0.12.3`):** o `uv tool install` não confere hash de dependência, nem por `--constraints` nem por `--with-requirements` com `UV_REQUIRE_HASHES=1` (ele não tem `--require-hashes`). A garantia fica no sha256 da wheel e do `restricoes.txt` conferidos em Rust e nos pinos `==`; o hash de cada dependência não é checado. Saída que conferiria: `uv venv` + `uv pip install --require-hashes -r restricoes.txt` (esse recusa hash adulterado); o dono escolhe na D173, antes da T336.
- A casca grava `<dados>/instalacao.json` (`{"canal":"casca","uv":"<caminho do uv>","pasta_uv":"<pasta>"}`, 0600, escrita atômica). É só leitura para o Python.
- Navegador marcado: depois do joBot, a casca roda `jobot ferramentas baixar navegador` (subcomando novo da CLI que chama `baixar_chromium`, já existente), lendo o progresso por linhas JSON no stdout (`{"etapa":...,"feito":...,"total":...}`), para o componente de progresso.

### 6.3 Atualizar pelo painel

- `atualizar.py` ganha o canal `casca` (lido de `instalacao.json`): baixa da release `latest` a wheel, o `restricoes.txt` e o `SHA256SUMS`; confere o sha256 da wheel e das restrições contra o `SHA256SUMS`; para o servidor como hoje; roda `<uv> tool install --force --python 3.14 --constraints ... <wheel>` com as pastas de 6.2; religa. Falhou: nada muda e a mensagem diz o que fazer.
- **Limite conhecido:** o `SHA256SUMS` vem da mesma release (mesma origem), então protege de arquivo corrompido, não de release adulterada. A assinatura de código (SignPath) é que cobre isso depois.
- O `uv_tool` de hoje continua para quem instalou à mão. O `clone_git` também.
- Painel: botão "Atualizar agora" na faixa de versão e em Configurações › Geral ("Atualizar o joBot", com a versão atual e a última conhecida). `POST /atualizar` (CSRF) dispara o `jobot atualizar` destacado, que para e religa o servidor; o painel mostra o progresso indeterminado e recarrega quando `/saude-local` voltar com a versão nova (espera até 120 s, depois explica e oferece tentar de novo). Sem JavaScript: 303 para uma página "Atualizando…" com `<meta http-equiv="refresh">` de 5 s.

### 6.4 Encerrar pelo painel

Botão "Encerrar o joBot" em Configurações › Geral e na paleta de comandos, com o alerta "Encerrar o joBot?" e o texto "As buscas param até você abrir o joBot de novo." (D143.37: ação que não se desfaz pelo painel). Usa o `POST /sair` que já existe. Na casca, a janela fecha junto (o painel chama `window.__TAURI__` para fechar a janela, se existir); fora dela, a página mostra "O joBot foi encerrado. Pode fechar esta janela."

### 6.5 Segundo plano no Windows e no Mac

- Windows (`sistema/segundo_plano_windows.py`): tarefa do Agendador de Tarefas por usuário, "ao fazer logon", rodando o `pythonw` do joBot com `-m jobot serve` (sem janela de console); `schtasks /Create /TN joBot /XML <arquivo> /F` (gatilho ao entrar do usuário atual, sem os padrões de bateria e de 72 h; D174 item 1), `/Delete`, `/Query`. Atalho no Menu Iniciar: o NSIS da casca já cria.
- Mac (`sistema/segundo_plano_mac.py`): LaunchAgent em `~/Library/LaunchAgents/io.github.fezarosa-dev.jobot.plist` com `RunAtLoad` e `KeepAlive` para falha; `launchctl bootstrap gui/<uid>` e `bootout`. Experimental como o `.dmg`.
- A tela Configurações › Segundo plano e o passo 2 do assistente passam a usar uma função só (`sistema.segundo_plano.ligar/desligar/status`) que escolhe pelo sistema; fora dos três sistemas, segue desativado com "chega numa próxima versão".
- Os testes desses dois arquivos são de unidade, com o executor de comandos injetado (como o do systemd). A prova real é do dono e do CI (seção 10).

## 7. Pastas e arquivos

### 7.1 Regra de pasta compartilhada

A casca calcula a pasta de dados com a mesma regra de `pastas.py` (6.1). Para não haver duas regras, `pastas.py` vira a fonte, e um teste Python lê `desktop/src/servidor.rs` como texto e confere que os três caminhos e o `JOBOT_DADOS` aparecem iguais (ponytail: conferência por texto; se divergir muito, a casca passa a perguntar `jobot dados --json`, um subcomando de uma linha).

### 7.2 O que a casca grava

Só `<dados>/instalacao.json` e as pastas do `uv` (6.2). Desinstalar (NSIS `NSIS_HOOK_PREUNINSTALL`) roda `uv tool uninstall jobot` com as mesmas pastas e apaga a pasta do `uv` da casca, **nunca** a pasta de dados. No Linux, `.deb`/`.rpm` não alcançam a pasta do usuário: o README explica como remover (`~/.local/share/jobot-app/`) e que os dados ficam em `~/.local/share/jobot/`.

## 8. Versões e release

- Versão única: `pyproject.toml`, `desktop/Cargo.toml` e `desktop/tauri.conf.json` com o mesmo número; `tests/unidade/test_documentos.py` passa a conferir os três.
- Tag `vN.N.N` dispara `.github/workflows/release.yml`:
  1. `wheel`: `uv build --wheel`, `uv export ...` → `restricoes.txt`, sha256 dos dois como saída.
  2. `casca` (matriz `ubuntu-22.04`, `windows-latest`, `macos-latest` com `aarch64` e `x86_64`): baixa o `uv` da versão fixada em `desktop/uv.meta.json` e confere o sha256; `cargo install tauri-cli --version =2.x.y --locked`; `cargo tauri build` com `JOBOT_WHEEL_SHA256` e `JOBOT_RESTRICOES_SHA256` no env. Mac com assinatura ad-hoc (`signingIdentity: "-"`).
  3. `publicar`: uma GitHub Release (não rascunho, não prerelease, para virar `latest` e casar com `versao.py:122-124`) com os instaladores, a wheel, o `restricoes.txt` e o `SHA256SUMS`; corpo tirado da seção da versão no `CHANGELOG.md` e no `CHANGELOG.en.md`.
- `permissions: contents: write` só no `release.yml`; só `GITHUB_TOKEN`; sem `pull_request`. Teste próprio por texto no molde do `test_wiki.py:104-108` (ADR 0018 continua: CI de PR sem segredo).
- O `.dmg` e os `.deb`/`.rpm`/AppImage levam no nome a versão e a arquitetura; o README lista qual baixar.

## 9. CI do Rust

- Workflow novo `.github/workflows/casca.yml`, com os mesmos gatilhos do `ci.yml` (`pull_request`, push em `lote/**`, `workflow_dispatch`), `contents: read`, sem segredo.
- Job `casca` em `ubuntu-22.04`: dependências do apt (`libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf`), `cargo fmt --check`, `cargo clippy -- -D warnings`, `cargo test` (as partes puras: achar servidor, ler a trava, conferir sha256, montar comandos do `uv`, montar URLs).
- `cargo tauri build` completo nos três sistemas só no `release.yml` e por `workflow_dispatch` do `casca.yml` (entrada `pacotes: true`), para não pesar todo PR.
- Teste Python `tests/unidade/test_casca_ci.py` trava gatilhos, permissões e segredos do `casca.yml`, por texto.
- A toolchain Rust fixada em `desktop/rust-toolchain.toml` (versão exata, ≥ 1.90 pedida pelos plugins).

## 10. Testes e provas

- **Rust**: `cargo test` nas partes puras (CI de PR).
- **Python**: unidade para `pastas`, `instancia` (com `msvcrt` simulado), `processo`, `segundo_plano_windows/mac` (executor injetado), canal `casca` do `atualizar`, `sair.token`, `/saude-local` com `segundo_plano`, `POST /atualizar`, `POST /abrir-release`, i18n da casca, versões sincronizadas, sem cópia do CSS em `desktop/ui/`.
- **Tela (Playwright, no CI)**: o painel com o user agent da casca desenha os círculos (Windows/Linux) ou reserva o espaço (Mac), nomes acessíveis, teclado, forced-colors e janela inativa; chama a ponte num `window.__TAURI__` falso (gravando as chamadas). A tela de instalação (`desktop/ui/index.html`) servida por arquivo local no Playwright, com o `__TAURI__` falso: passos, essencial travado, progresso que não volta, pé preso com janela baixa e texto Maior, alerta ao fechar no meio.
- **CI Windows**: o job `comuns` não muda; um job `windows` no `casca.yml` roda só os testes de `sistema` (`pytest tests/unidade -k "pastas or instancia or processo or segundo_plano or atualizar"`) no `windows-latest`, para provar o import e a trava. (O `ci.yml` fica como está.)
- **Fumaça do pacote** (`release.yml` e `workflow_dispatch`): no Linux, instala o `.deb` num contêiner limpo e roda `jobot-app --verificar` (modo sem janela da casca: instala pelo `uv`, sobe o servidor, confere `/saude-local`, sai com 0). No Windows, o mesmo com o `.exe` em modo silencioso (`/S`) e `--verificar`.
- **Dono (portão)**: instalar o AppImage e o `.rpm` na Fedora, abrir, passar pela tela de instalação, mexer na janela (arrastar, maximizar, fechar com e sem segundo plano) e, se tiver acesso a um Windows, o `.exe`. Fica em "Espera o dono" e não trava as outras tarefas.

## 11. Riscos

1. IPC do Tauri em origem `http://127.0.0.1` (5.3): prova primeiro (T321).
2. `uv tool install` sem hash nas dependências (6.2): T322 mede e registra.
3. WebKitGTK velho (5.4): cai no modo app; não trava ninguém.
4. Gerenciadores de janela do Linux (D142.4): o dono confere; Wayland/GNOME podem ignorar o redimensionamento sem moldura. Se o GNOME não deixar redimensionar, a casca no Linux usa `decorations: true` e a fileira some no Linux (mudança da D142.3 só no Linux, volta ao dono).
5. Antivírus e SmartScreen com instalador sem selo: README explica; o pedido ao SignPath resolve depois (D171.5).
6. Dois donos do servidor no Linux (systemd e casca): a casca nunca mata o servidor que não subiu; só chama `jobot sair` com o segundo plano desligado. A trava continua garantindo uma instância.

## 12. Documentos que mudam

- ADR 0003 (o projeto Tauri fica em `desktop/` no mesmo repositório), ADR 0017 (status da fase 3), ADR 0018 (o canal para o público, antes na fase 9, chega na fase 3 pelo instalador; `jobot atualizar` passa a aceitar o canal `casca`), ADR nova **0025. App de desktop e instalador**.
- `README.md`/`README.en.md`: instalação pelo instalador (o que baixar por sistema, o aviso do Windows e o "Abrir Mesmo Assim" do Mac, onde ficam os dados, como desinstalar), roteiro com a fase 3.
- `CHANGELOG`/`CHANGELOG.en.md` 0.4.0; `CONTRIBUTING`: como compilar a casca (Rust, `cargo tauri dev`).
- `wiki/` (pt e en): Arquitetura com o nó `desktop/`; página "Instalar".
- `.gitignore`: `desktop/target/`, `desktop/ui/painel/`, `desktop/binaries/`.

## 13. Decisões (D171)

Do dono (2026-11-17):

1. Distribuição: `uv` embutido; o joBot vem da release do GitHub da mesma versão, com sha256 conferido.
2. Linux: AppImage, `.deb` e `.rpm`.
3. Mac: `.dmg` experimental, gerado e testado só no CI.
4. O projeto Tauri fica em `desktop/` no mesmo repositório.
5. Assinatura: sem selo por enquanto, custo zero; o dono pede o SignPath Foundation (grátis) quando quiser.
6. (D138.16 respondida) Não comprar certificado.
7. Fechar a janela fecha só a janela; o servidor segue se o segundo plano estiver ligado; sem bandeja.
8. A casca não se atualiza sozinha: avisa e abre a release.

Da sessão (para confirmar):

9. A tela de instalação é a primeira abertura da própria casca, não página do NSIS (5.2).
10. Essenciais travadas: joBot e Python; navegador marcado e opcional (confirma a D138.15).
11. Uma checagem de versão só, a do painel; a casca não consulta o GitHub (5.6).
12. Segundo plano no Windows (Agendador de Tarefas) e no Mac (LaunchAgent, experimental) entram na fase 3 (6.5).
13. Sem npm: `withGlobalTauri` e HTML/CSS/JS puros (D171.13).
14. Parada no Windows por `sair.token` local (6.1).
15. WebKitGTK sem os recursos do painel cai no modo app (5.4).
16. Círculos: 12px, 8px de espaço, símbolos no hover, cinza com a janela inativa (5.3).
17. Pastas do `uv` da casca separadas do `uv` da pessoa (6.2).
18. Desinstalar nunca apaga a pasta de dados (7.2).
