# Fase 3: app de desktop e instalador (desenho)

Data: 2026-11-17. Decisões de origem: ADR 0003, 0017, 0018, 0023; D138 (instalador), D140 e D143 (visual de app do Mac), D142 (app de desktop e botões da janela) a D171 (respostas do dono de 2026-11-17 e escolhas da sessão), a D173 (hash de cada dependência) e a D174 (instalador completo e sem rede, também de 2026-11-17). Versão alvo: **0.4.0**.

Fatos sobre o código vêm com `arquivo:linha`, conferidos na `dev` em 2026-11-17. As linhas podem andar: quando não bater, procure o símbolo. Valores marcados "(proposta)" foram escolhidos pela sessão e valem para construir; o dono pode trocar.

## 1. Intenção

Quem usa baixa um arquivo, abre e tem o joBot numa janela própria, com ícone, sem terminal e sem saber o que é Python. A tela que instala tem o mesmo visual de app do Mac do painel (D140) e mostra uma lista de ferramentas para marcar (ADR 0023). Depois disso a janela é só uma moldura em volta do painel, que continua em `127.0.0.1` e não é reescrito (D142.1).

## 2. Objetivos, não objetivos, anti-objetivos

**Objetivos**

- Casca Tauri 2 na pasta `desktop/` (D171.4), com janela própria em volta do painel (D142.1).
- Instaladores de 64 bits gerados pelo mesmo projeto: NSIS no Windows (por usuário, sem admin), AppImage, `.deb` e `.rpm` no Linux (D171.2), e `.dmg` experimental no Mac (D171.3).
- Tela de instalação na primeira abertura da casca: lista de ferramentas com as essenciais travadas, progresso com o componente único (D143.56) e fileira de botões presa ao pé (D144, E17).
- ~~O joBot instalado pelo `uv` embutido, a partir da wheel da release da mesma versão, com sha256 conferido (D171.1).~~ (superado em 2026-11-17 pela D174.1) Instalador completo por sistema: casca, `uv`, Python 3.14, a wheel do joBot, as wheels de todas as dependências daquela plataforma e o Chromium da versão fixada, tudo com sha256 conferido no build e de novo na instalação; nada é baixado na instalação (D174.1). O joBot fica num venv da casca, com o hash de cada dependência conferido (D173).
- Botões da janela: no Mac, os do sistema com a barra sobreposta; no Windows e no Linux, janela sem moldura e três círculos desenhados por nós (D142.3).
- O joBot passa a rodar no Windows (hoje quebra no import de `fcntl`, `src/jobot/sistema/instancia.py:3`) e no Mac (pasta de dados própria).
- Segundo plano no Windows e no Mac, para que fechar a janela siga o segundo plano em todo sistema (D171.7, D171.12).
- Os botões "Atualizar o joBot" e "Encerrar" no painel (ADR 0023, ainda não construídos) e o aviso de versão sem mandar abrir o terminal.
- Workflow de release que publica wheel, restrições com hash, instaladores, pacotes de atualização e arquivos do Chromium por plataforma e o `SHA256SUMS`, só com o `GITHUB_TOKEN`.

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
- Licenças compatíveis com MIT: Tauri e plugins oficiais são MIT/Apache-2.0; o `uv` é MIT/Apache-2.0. O Python (licença PSF) e o Chromium (BSD e as de terceiros dele) vão dentro do instalador (D174.1) com os arquivos de licença deles.
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
  src/instalar.rs            conferir sha256, preparar o Python, montar o venv pelo uv (puro onde dá)
  ui/                        tela de instalação: index.html, instalador.js, i18n/{pt,en}.json
  ui/painel/                 gerado no build (gitignored): css, fontes e ícones do painel
  binaries/                  uv por alvo (baixado no build, sha256 em uv.meta.json)
  recursos/                  gerado no build (gitignored): python, wheels, joBot, chromium e manifesto.json (D174.1)
  capabilities/*.json        permissões mínimas
```

**Quem fala com quem.** A casca é um processo externo ao joBot: só fala HTTP com o painel e chama o executável `jobot` (e o `uv` embutido). O pacote Python não importa nada da casca. O `test_camadas.py` não alcança Rust; a regra entra na `wiki/Arquitetura.md` (e `Architecture.md`) como nó `desktop/`.

### 5.1 Arranque da casca

1. Plugin `single-instance` (o primeiro registrado): uma segunda abertura só traz a janela existente para a frente.
2. Procura o joBot instalado: lê `<dados>/instalacao.json` e o executável `jobot` do venv apontado por ele (`<venv>/bin/jobot`; no Windows `<venv>\Scripts\jobot.exe`; seção 6.2). Sem o arquivo ou sem o executável: tela de instalação (5.2).
3. Achou: procura o servidor. Lê `<dados>/jobot.lock` com a mesma regra de pasta do Python (seção 7.1); com PID e porta, confirma `GET http://127.0.0.1:<porta>/saude-local` com `app == "jobot"`. Sem servidor, sobe `jobot serve` destacado, como o `subir_servidor` faz (nunca como filho da casca), e espera `/saude-local` até 15 s, de 200 em 200 ms (mesmo prazo de `abrir.py:198-237`).
4. Confere a janela (5.4). Passou: navega para `http://127.0.0.1:<porta>/`. Não passou (WebKitGTK velho): roda `jobot abrir`, que abre o modo app de hoje, mostra uma tela curta dizendo por quê e fecha a própria janela.
5. Falhas: porta ocupada por outro programa, servidor que não responde em 15 s ou `jobot serve` que sai com erro levam a uma tela de erro da casca, com o que fazer, o fim de `<dados>/logs/jobot.log` (últimas 20 linhas) e o botão "Tentar de novo". Texto pt e en.

### 5.2 Tela de instalação (primeira abertura)

Mora na própria casca (`desktop/ui/`), não no NSIS nem no `postinst`: assim é uma tela só nos três sistemas, roda como a pessoa (os `.deb`/`.rpm` instalam como root, mas o venv é por usuário) e dispensa template NSIS. ~~O NSIS, o AppImage, o `.deb`, o `.rpm` e o `.dmg` levam só a casca e o `uv`.~~ (superado em 2026-11-17 pela D174.1) O NSIS, o AppImage, o `.deb`, o `.rpm` e o `.dmg` levam a casca, o `uv` e os recursos daquela plataforma (Python, wheels, joBot, Chromium e `manifesto.json`, seção 6.2): a instalação não usa a rede.

**Passos** (cada um com o pé preso, D144):

1. **Boas-vindas.** Ícone, "joBot", uma frase do que ele faz, idioma (pt/en, pelo idioma do sistema; troca ali mesmo) e "Continuar".
2. **Ferramentas.** Lista com caixas de marcar:
   - joBot e Python 3.14 (marcados e travados, com "necessário" ao lado; tamanho estimado).
   - Navegador para sites com login (marcado, dá para desmarcar; ~210 MB; frase: "Para o LinkedIn e outros sites em que você entra. Dá para baixar depois em Configurações › Ferramentas.").
   - Se a pessoa desmarca o navegador, os sites com login ficam desligados até ela baixar pela tela Ferramentas (D138.15).
   - A lista mostra só o que esta versão usa (D138.6). O grupo de IA chega na fase 4.
   - Rodapé: "Onde fica" (pasta de dados) e o espaço em disco que a instalação vai usar (nada é baixado, D174.1).
3. **Instalando.** Componente de progresso (barra determinada, nunca volta, teto de 99% até o fim; linha da etapa; D143.56-61). Etapas (sem "Baixando", D174.1): "Conferindo os arquivos", "Preparando o Python", "Instalando o joBot", "Instalando o navegador" (se marcado), "Abrindo". Cada etapa tem uma fatia fixa da barra (proposta). Nas que medem bytes (conferência, cópia e extração do navegador), a barra anda dentro da fatia pelos bytes feitos sobre o total, que já se sabe pelo `manifesto.json`. Nas do `uv` ("Preparando o Python" e "Instalando o joBot"), que não dão progresso em bytes, a fatia se completa de uma vez quando a etapa termina, e a linha da etapa mostra que ela segue em curso; a barra nunca volta e fica no teto de 99% até o fim. Sem botão de cancelar no meio (D143.71); fechar a janela pede confirmação num alerta (D143.37) e, se confirmado, para o `uv`, apaga o venv e o Python pela metade e não grava o `instalacao.json`: tudo fica como estava antes.
4. **Falha.** Diz o que deu errado com o que fazer (arquivo não confere: "um arquivo do instalador não é o esperado, nada foi instalado; baixe o instalador de novo"; pouco espaço; a prova do joBot instalado falhou) e "Tentar de novo". Sem internet não é falha: a instalação não usa a rede.
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

- A casca roda o `uv` com `UV_PYTHON_INSTALL_DIR`, `UV_CACHE_DIR` e `UV_OFFLINE=1` dentro de uma pasta da casca por usuário (Linux `~/.local/share/jobot-app/`, Windows `%LOCALAPPDATA%\joBot\app\`, Mac `~/Library/Application Support/joBot/app/`) (proposta). Assim a instalação da casca não briga com um `uv` que a pessoa já tenha.
- ~~Comando: `uv tool install --python 3.14 --constraints <restricoes.txt> <wheel local>`. A casca baixa a wheel e o `restricoes.txt` da release da mesma versão e confere o sha256 dos dois em Rust contra as constantes gravadas no build (env `JOBOT_WHEEL_SHA256`, `JOBOT_RESTRICOES_SHA256`) antes de chamar o `uv`.~~ (superado em 2026-11-17 pela D173 e pela D174.1)
- **Recursos no instalador (D174.1).** O build põe em `desktop/recursos/` (gitignored), para a plataforma do alvo: o Python 3.14 do python-build-standalone que o `uv` gerencia (versão e sha256 fixos em `desktop/uv.meta.json`), a wheel do joBot, as wheels de todas as dependências (exportadas do `uv.lock` com hashes para o `restricoes.txt`), o arquivo compactado do Chromium da versão do Playwright fixada e o `manifesto.json` (nome, tamanho e sha256 de cada arquivo, e a versão). O sha256 do `manifesto.json` entra no binário no build (env `JOBOT_MANIFESTO_SHA256`).
- **Ordem da instalação.** (1) A casca confere em Rust o sha256 do `manifesto.json` contra a constante e o de cada arquivo contra o manifesto; qualquer diferença para tudo antes de gravar. (2) Copia o `uv` e o Python para a pasta da casca (`bin/` e `python/`; o caminho de dentro do AppImage muda a cada abertura). (3) `uv venv --python <python da pasta da casca> <pasta da casca>/venvs/venv-<versão>`. (4) `uv pip install --python <venv> --offline --no-index --find-links <wheels> --require-hashes -r restricoes.txt <wheel do joBot>` (se o `--require-hashes` recusar a wheel solta, o joBot entra na lista como `jobot==<versão> --hash=sha256:...`, achado pelo `--find-links`; a T336 prova qual das duas). (5) Navegador marcado: instala o Chromium do arquivo local (abaixo). (6) Prova rápida: `<venv>/bin/jobot --version` sai com 0 e a versão certa. (7) Só então grava o `instalacao.json` e copia o `manifesto.json` para a pasta da casca (`manifesto-<versão>.json`).
- Nada é baixado na instalação (D174.1): sem rede, a instalação funciona igual. O CI prova isso (seção 10).
- `restricoes.txt` sai do `uv.lock` (`uv export --no-dev --no-emit-project --format requirements-txt`, com hashes). **Risco 2 (T322 prova):** se o `uv tool install` não exigir os hashes das dependências pelas restrições, a garantia fica só na wheel do joBot e nos pinos `==`; a T322 mede e registra o limite em `docs/decisions/` e no README.
  - **Medido (T322, `uv 0.12.3`):** o `uv tool install` não confere hash de dependência, nem por `--constraints` nem por `--with-requirements` com `UV_REQUIRE_HASHES=1` (ele não tem `--require-hashes`). A garantia fica no sha256 da wheel e do `restricoes.txt` conferidos em Rust e nos pinos `==`; o hash de cada dependência não é checado. Saída que conferiria: `uv venv` + `uv pip install --require-hashes -r restricoes.txt` (esse recusa hash adulterado); ~~o dono escolhe na D173, antes da T336.~~ o dono escolheu essa saída em 2026-11-17 (D173, opção 2).
- A casca grava `<dados>/instalacao.json` (`{"canal":"casca","pasta":"<pasta da casca>","uv":"<pasta>/bin/uv","venv":"<pasta>/venvs/venv-<versão>","anterior":null,"manifesto":"<pasta>/manifesto-<versão>.json"}`, com `bin\uv.exe` no lugar de `bin/uv` no Windows, 0600, escrita atômica) (proposta). A casca o grava na instalação; depois, só o canal `casca` do `atualizar.py` o reescreve (6.3), também de forma atômica.
- **Navegador (D174.2).** Marcado: depois do joBot, a casca roda `jobot ferramentas baixar navegador --arquivo <chromium.tar.gz> --sha256 <hex>` (subcomando novo da CLI) com o arquivo dos recursos, lendo o progresso por linhas JSON no stdout (`{"etapa":...,"feito":...,"total":...}`), para o componente de progresso. O subcomando confere o sha256 e extrai o arquivo com `tarfile` e `filter="data"` (guarda o bit de execução e os symlinks e recusa caminho para fora da pasta) na pasta padrão que o Playwright já usa em cada sistema (Linux `~/.cache/ms-playwright`, Windows `%LOCALAPPDATA%\ms-playwright`, Mac `~/Library/Caches/ms-playwright`), sem env nova. Desmarcado: o arquivo não é copiado. Depois, a tela Ferramentas (canal `casca`) baixa o mesmo arquivo da release do joBot da versão instalada (não do CDN do Playwright) e confere o sha256 contra o `manifesto-<versão>.json` gravado na instalação. Quem instalou sem a casca (clone ou `uv tool`) segue com `playwright install` (`baixar_chromium`, já existente).
- **Arquivo do Chromium.** No build, `playwright install chromium` da versão fixada roda com `PLAYWRIGHT_BROWSERS_PATH` numa pasta temporária, e o que ele põe lá vira `chromium-<alvo>.tar.gz`, gerado com `tarfile` a partir dessa pasta (proposta). ~~`.zip` extraído com `zipfile`~~ (superado em 2026-11-17: o `zipfile` não restaura o modo Unix nem os symlinks, então o `chrome`/`headless_shell` sairia sem `+x` e os symlinks do `Chromium.app` se perderiam no Mac; D174.12).

### 6.3 Atualizar pelo painel

- ~~`atualizar.py` ganha o canal `casca` (lido de `instalacao.json`): baixa da release `latest` a wheel, o `restricoes.txt` e o `SHA256SUMS`; confere o sha256 da wheel e das restrições contra o `SHA256SUMS`; para o servidor como hoje; roda `<uv> tool install --force --python 3.14 --constraints ... <wheel>` com as pastas de 6.2; religa.~~ (superado em 2026-11-17 pela D174.3)
- **Canal `casca` (D174.3).** `atualizar.py` lê o `instalacao.json` e baixa da release `latest` o `SHA256SUMS` e o pacote de atualização da plataforma (`jobot-atualizacao-<versão>-<alvo>.zip`, proposta: Python, wheels, joBot e `manifesto.json`; sem o Chromium, que só muda quando o Playwright muda). O `manifesto.json` do pacote lista também o `chromium-<alvo>.tar.gz` (nome, tamanho e sha256), mesmo ele não estando dentro, para o caminho (b) da tela Ferramentas seguir funcionando depois da troca. Confere o pacote contra o `SHA256SUMS` e cada arquivo de dentro contra o manifesto; entrada listada que não está no pacote (o Chromium) é aceita. **Navegador desatualizado** (D174.13, proposta): com o Chromium instalado na pasta padrão do Playwright e o sha256 dele diferente entre o manifesto antigo e o novo, a atualização baixa o arquivo novo pelo caminho (b) antes da troca; se esse download falhar, a troca segue e a tela Ferramentas marca "navegador desatualizado" com o botão Baixar. Monta ao lado um venv novo (`venvs/venv-<versão nova>`, com o Python novo em `python/` se a versão mudou) pelos mesmos passos de 6.2, offline a partir do pacote. Roda o `jobot --version` do venv novo; só se passar: para o servidor como hoje, troca `venv` e `anterior` no `instalacao.json` (escrita atômica), grava o `manifesto-<versão nova>.json`, refaz o segundo plano se estiver ligado (o serviço aponta para o executável do venv), religa e apaga os venvs e Pythons mais velhos que o anterior. Falhou em qualquer passo antes da troca: apaga o venv novo, nada mais muda e a mensagem diz o que fazer. Voltar à anterior é trocar o ponteiro de volta (a T331 deixa a função pronta; o botão no painel não entra na 0.4.0). **Banco ao voltar** (D174.14, proposta): o joBot novo migra o SQLite ao abrir (`banco/migrar.py`, `PRAGMA user_version`). Por isso (a) a troca grava no `instalacao.json` o `user_version` de antes dela, e voltar só acontece se o `user_version` atual for o mesmo; se mudou, voltar recusa e diz por quê (a cópia `.antes-vN` fica, mas restaurá-la perderia as vagas coletadas depois); e (c) o `migrar.py` recusa abrir um esquema maior que a última migração que conhece, com mensagem, em vez de rodar código velho sobre esquema novo.
- **Como a T331 fez** (D174.15 a D174.21, propostas): formato do pacote e `<alvo>` como a tripla do Rust; a versão sai do `SHA256SUMS` da `latest` e o resto vem da tag `v<versão>`; o Python do pacote vai para `python/<nome>/`; o `uv` recebe `--offline` e `--cache-dir` como opções; o Chromium novo entra pelo caminho (a) da T330 com o `jobot` do venv novo; a marca é o campo `navegador_desatualizado` do `instalacao.json`.
- **Limite conhecido:** o `SHA256SUMS` vem da mesma release (mesma origem), então protege de arquivo corrompido, não de release adulterada. A assinatura de código (SignPath) é que cobre isso depois.
- O `uv_tool` de hoje continua para quem instalou à mão. O `clone_git` também.
- Painel: botão "Atualizar agora" na faixa de versão e em Configurações › Geral ("Atualizar o joBot", com a versão atual e a última conhecida). `POST /atualizar` (CSRF) dispara o `jobot atualizar` destacado, que para e religa o servidor; o painel mostra o progresso indeterminado e recarrega quando `/saude-local` voltar com a versão nova (espera até 120 s, depois explica e oferece tentar de novo). Sem JavaScript: 303 para uma página "Atualizando…" com `<meta http-equiv="refresh">` de 5 s.

### 6.4 Encerrar pelo painel

Botão "Encerrar o joBot" em Configurações › Geral e na paleta de comandos, com o alerta "Encerrar o joBot?" e o texto "As buscas param até você abrir o joBot de novo." (D143.37: ação que não se desfaz pelo painel). Usa o `POST /sair` que já existe. Na casca, a janela fecha junto (o painel chama `window.__TAURI__` para fechar a janela, se existir); fora dela, a página mostra "O joBot foi encerrado. Pode fechar esta janela."

### 6.5 Segundo plano no Windows e no Mac

- Windows (`sistema/segundo_plano_windows.py`): tarefa do Agendador de Tarefas por usuário, "ao fazer logon", rodando o `pythonw` do joBot (no canal `casca`, o do venv atual, refeito a cada atualização, 6.3) com `-m jobot serve` (sem janela de console); `schtasks /Create /SC ONLOGON /TN joBot /TR ... /F`, `/Delete`, `/Query`. Atalho no Menu Iniciar: o NSIS da casca já cria.
- Mac (`sistema/segundo_plano_mac.py`): LaunchAgent em `~/Library/LaunchAgents/io.github.fezarosa-dev.jobot.plist` com `RunAtLoad` e `KeepAlive` para falha; `launchctl bootstrap gui/<uid>` e `bootout`. Experimental como o `.dmg`.
- A tela Configurações › Segundo plano e o passo 2 do assistente passam a usar uma função só (`sistema.segundo_plano.ligar/desligar/status`) que escolhe pelo sistema; fora dos três sistemas, segue desativado com "chega numa próxima versão".
- Os testes desses dois arquivos são de unidade, com o executor de comandos injetado (como o do systemd). A prova real é do dono e do CI (seção 10).

## 7. Pastas e arquivos

### 7.1 Regra de pasta compartilhada

A casca calcula a pasta de dados com a mesma regra de `pastas.py` (6.1). Para não haver duas regras, `pastas.py` vira a fonte, e um teste Python lê `desktop/src/servidor.rs` como texto e confere que os três caminhos e o `JOBOT_DADOS` aparecem iguais (ponytail: conferência por texto; se divergir muito, a casca passa a perguntar `jobot dados --json`, um subcomando de uma linha).

### 7.2 O que a casca grava

`<dados>/instalacao.json`, a pasta da casca (6.2: `bin/` com o `uv`, `python/`, `venvs/` e os `manifesto-<versão>.json`) e, com o navegador marcado, o Chromium na pasta padrão do Playwright. ~~Desinstalar (NSIS `NSIS_HOOK_PREUNINSTALL`) roda `uv tool uninstall jobot` com as mesmas pastas e apaga a pasta do `uv` da casca~~ (superado em 2026-11-17 pela D173 e pela D174) Desinstalar (NSIS `NSIS_HOOK_PREUNINSTALL`) desliga o segundo plano se estiver ligado (`jobot` do venv atual), para o servidor e apaga a pasta da casca inteira (venvs, Python, `uv` e manifestos) e o `instalacao.json`, **nunca** a pasta de dados. O Chromium fica: a pasta padrão do Playwright pode servir a outro programa; quem quiser tira antes pela tela Ferramentas (Remover) (D174, para confirmar). No Linux, `.deb`/`.rpm` não alcançam a pasta do usuário: o README explica como remover (`~/.local/share/jobot-app/`) e que os dados ficam em `~/.local/share/jobot/`.

## 8. Versões e release

- Versão única: `pyproject.toml`, `desktop/Cargo.toml` e `desktop/tauri.conf.json` com o mesmo número; `tests/unidade/test_documentos.py` passa a conferir os três.
- Tag `vN.N.N` dispara `.github/workflows/release.yml`:
  1. `wheel`: `uv build --wheel`, `uv export ...` → `restricoes.txt`, sha256 dos dois como saída.
  2. `casca` (matriz `ubuntu-22.04`, `windows-latest`, `macos-latest` para `aarch64` e o runner Intel do Mac `macos-15-intel` para `x86_64`, proposta: o Chromium e as wheels saem da máquina do alvo; quando o GitHub tirar o último runner Intel, o `.dmg` `x86_64`, que já é experimental, sai da release, D174.11): baixa o `uv` da versão fixada em `desktop/uv.meta.json` e confere o sha256; baixa o Python da versão fixada lá e confere o sha256; baixa as wheels das dependências daquela plataforma com `--require-hashes` contra o `restricoes.txt` (só wheels, nenhuma sdist); gera o `chromium-<alvo>.tar.gz` (6.2); escreve o `manifesto.json` em `desktop/recursos/`; `cargo install tauri-cli --version =2.x.y --locked`; `cargo tauri build` com `JOBOT_MANIFESTO_SHA256` no env. Monta também o `jobot-atualizacao-<versão>-<alvo>.zip` (6.3). Mac com assinatura ad-hoc (`signingIdentity: "-"`).
  3. `publicar`: uma GitHub Release (não rascunho, não prerelease, para virar `latest` e casar com `versao.py:122-124`) com os instaladores, os pacotes de atualização, os `chromium-<alvo>.tar.gz`, a wheel, o `restricoes.txt` e o `SHA256SUMS` (todos esses arquivos); corpo tirado da seção da versão no `CHANGELOG.md` e no `CHANGELOG.en.md`.
- `permissions: contents: write` só no `release.yml`; só `GITHUB_TOKEN`; sem `pull_request`. Teste próprio por texto no molde do `test_wiki.py:104-108` (ADR 0018 continua: CI de PR sem segredo).
- O `.dmg` e os `.deb`/`.rpm`/AppImage levam no nome a versão e a arquitetura; o README lista qual baixar.
- Tamanho aceito (D174.5): cerca de 350 MB por instalador, porque cada um leva o próprio Python, as wheels e o Chromium (como apps que levam o próprio motor). Os pacotes de atualização são menores (sem o Chromium).

## 9. CI do Rust

- Workflow novo `.github/workflows/casca.yml`, com os mesmos gatilhos do `ci.yml` (`pull_request`, push em `lote/**`, `workflow_dispatch`), `contents: read`, sem segredo.
- Job `casca` em `ubuntu-22.04`: dependências do apt (`libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf`), `cargo fmt --check`, `cargo clippy -- -D warnings`, `cargo test` (as partes puras: achar servidor, ler a trava, conferir sha256, montar comandos do `uv`, montar URLs).
- Job `windows` em `windows-latest`: os testes de `sistema` (seção 10).
- Job `uv` (só no `workflow_dispatch`; matriz `ubuntu-latest`, `windows-latest`, `macos-latest`): roda `scripts/provar_uv.py` (T322) e a prova do caminho escolhido na D173 (`uv venv` + `uv pip install --offline --no-index --find-links --require-hashes`, com o hash adulterado recusado).
- `cargo tauri build` completo nos três sistemas só no `release.yml` e por `workflow_dispatch` do `casca.yml` (entrada `pacotes: true`), para não pesar todo PR.
- Teste Python `tests/unidade/test_casca_ci.py` trava gatilhos, permissões e segredos do `casca.yml`, por texto.
- A toolchain Rust fixada em `desktop/rust-toolchain.toml` (versão exata, ≥ 1.90 pedida pelos plugins).

## 10. Testes e provas

- **Rust**: `cargo test` nas partes puras (CI de PR).
- **Python**: unidade para `pastas`, `instancia` (com `msvcrt` simulado), `processo`, `segundo_plano_windows/mac` (executor injetado), canal `casca` do `atualizar`, `sair.token`, `/saude-local` com `segundo_plano`, `POST /atualizar`, `POST /abrir-release`, i18n da casca, versões sincronizadas, sem cópia do CSS em `desktop/ui/`.
- **Tela (Playwright, no CI)**: o painel com o user agent da casca desenha os círculos (Windows/Linux) ou reserva o espaço (Mac), nomes acessíveis, teclado, forced-colors e janela inativa; chama a ponte num `window.__TAURI__` falso (gravando as chamadas). A tela de instalação (`desktop/ui/index.html`) servida por arquivo local no Playwright, com o `__TAURI__` falso: passos, essencial travado, progresso que não volta, pé preso com janela baixa e texto Maior, alerta ao fechar no meio.
- **CI Windows**: o job `comuns` não muda; um job `windows` no `casca.yml` roda só os testes de `sistema` (`pytest tests/unidade -k "pastas or instancia or processo or segundo_plano or atualizar"`) no `windows-latest`, para provar o import e a trava. (O `ci.yml` fica como está.)
- **Fumaça do pacote, sem rede** (`release.yml` e `workflow_dispatch`; D174.4): `jobot-app --verificar` é o modo sem janela da casca: instala dos recursos (com o navegador), sobe o servidor, confere `/saude-local`, abre o Chromium de verdade (`chromium.launch()` headless, pelo Python do venv) e fecha, sai com 0; só conferir que a pasta existe não prova o bit de execução. No Linux, um contêiner limpo `ubuntu:22.04` recebe antes só as bibliotecas do sistema que o `.deb` declara e as que o Chromium pede (`playwright install-deps chromium`) (passo com rede, numa imagem salva) e então `docker run --network none` instala o `.deb` (`dpkg -i`) e roda o `--verificar`. No Windows, regras de firewall (`New-NetFirewallRule -Direction Outbound -Action Block -Program <caminho>`) bloqueiam a saída de cada executável que a instalação vai ter (não a máquina toda, que derrubaria o runner), criadas antes do `.exe` em modo silencioso (`/S`): a regra aceita caminho que ainda não existe, então a lista sai do desenho 6.2 (a casca, `bin\uv.exe`, o `python.exe` e o `pythonw.exe` de `python\`, e no `venvs\venv-<versão>\Scripts\` o `python.exe`, o `pythonw.exe` e o `jobot.exe`, mais o `node.exe` do driver do Playwright dentro do venv). Depois do `/S` e antes do `--verificar`, a fumaça procura todo `.exe` na pasta da casca e falha se algum não tiver regra (lista a completar). A fumaça falha se algum passo tentar a rede.
- **Dono (portão)**: instalar o AppImage e o `.rpm` na Fedora, abrir, passar pela tela de instalação, mexer na janela (arrastar, maximizar, fechar com e sem segundo plano) e, se tiver acesso a um Windows, o `.exe`. Fica em "Espera o dono" e não trava as outras tarefas.

## 11. Riscos

1. IPC do Tauri em origem `http://127.0.0.1` (5.3): prova primeiro (T321).
2. ~~`uv tool install` sem hash nas dependências (6.2): T322 mede e registra.~~ Resolvido pela D173: `uv pip install --require-hashes` num venv.
3. WebKitGTK velho (5.4): cai no modo app; não trava ninguém.
4. Gerenciadores de janela do Linux (D142.4): o dono confere; Wayland/GNOME podem ignorar o redimensionamento sem moldura. Se o GNOME não deixar redimensionar, a casca no Linux usa `decorations: true` e a fileira some no Linux (mudança da D142.3 só no Linux, volta ao dono).
5. Antivírus e SmartScreen com instalador sem selo: README explica; o pedido ao SignPath resolve depois (D171.5).
6. Dois donos do servidor no Linux (systemd e casca): a casca nunca mata o servidor que não subiu; só chama `jobot sair` com o segundo plano desligado. A trava continua garantindo uma instância.
7. Python fora do caminho de sempre (D174.1): o `uv venv --python <caminho>` precisa de um Python já extraído. A T336 prova se o `uv python install` aceita o arquivo local sem rede; se não aceitar, a casca extrai o `.tar.gz` com crates `tar` e `flate2` (MIT/Apache-2.0, `=x.y.z`), dependência nova que volta ao dono antes.
8. Dependência sem wheel para Python 3.14 em alguma plataforma: o build falha (só wheels, sem sdist), e a release não sai até a dependência ganhar wheel ou ser trocada. Falha alta, nunca instalação pela metade.
9. Caminho do venv no segundo plano: systemd, Agendador de Tarefas e LaunchAgent apontam para o executável do venv; venv apagado deixaria o serviço quebrado. O canal `casca` refaz o segundo plano a cada troca (6.3) e só apaga venvs mais velhos que o anterior.
10. Tamanho (~350 MB por instalador, D174.5) e o Chromium do Playwright mudando de layout de pasta: o arquivo sai do próprio `playwright install` da versão fixada, então o layout casa com o que o Playwright espera.

## 12. Documentos que mudam

- ADR 0003 (o projeto Tauri fica em `desktop/` no mesmo repositório), ADR 0017 (status da fase 3), ADR 0018 (o canal para o público, antes na fase 9, chega na fase 3 pelo instalador; `jobot atualizar` passa a aceitar o canal `casca`), ADR nova **0025. App de desktop e instalador**.
- `README.md`/`README.en.md`: instalação pelo instalador (o que baixar por sistema, o aviso do Windows e o "Abrir Mesmo Assim" do Mac, onde ficam os dados, como desinstalar), roteiro com a fase 3.
- `CHANGELOG`/`CHANGELOG.en.md` 0.4.0; `CONTRIBUTING`: como compilar a casca (Rust, `cargo tauri dev`).
- `wiki/` (pt e en): Arquitetura com o nó `desktop/`; página "Instalar".
- `.gitignore`: `desktop/target/`, `desktop/ui/painel/`, `desktop/binaries/`, `desktop/recursos/`.

## 13. Decisões (D171)

Do dono (2026-11-17):

1. ~~Distribuição: `uv` embutido; o joBot vem da release do GitHub da mesma versão, com sha256 conferido.~~ (superado em 2026-11-17 pela D174.1: tudo vem dentro do instalador)
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

Depois (dono, 2026-11-17):

- D173: venv + `uv pip install --require-hashes` (hash de cada dependência conferido) (6.2).
- D174: "o menos quebrável possível": instalador completo e sem rede por sistema (6.2), navegador desmarcado vem depois pela release da versão instalada (6.2), atualização em venv novo ao lado com volta à anterior (6.3), fumaça sem rede no CI (10), ~350 MB por instalador aceitos (8).
