# 0003. Tecnologias e instalação nativa (sem Docker)

- **Status:** aceita
- **Data:** 2026-11-13
- **Atualizada:** 2026-11-15 (o Ollama volta como opção pelo backend compatível com OpenAI; Tauri na fase 3, D142); 2026-11-17 (o projeto Tauri fica em `desktop/` no mesmo repositório, D171)

## Contexto

O público é leigo e usa computadores médios. O app precisa abrir um Chrome visível para login manual, usar o microfone, rodar em segundo plano e usar o Claude Code já instalado na máquina. Nada disso existe ainda: o projeto está em desenvolvimento e a instalação descrita aqui é planejada.

## Decisão

### Tecnologias

- Python 3.14.
- FastAPI + Jinja2 + HTMX no painel.
- SQLite como banco.
- Playwright para controlar o navegador.
- uv para instalar e rodar.
- ruff para estilo, mypy --strict para tipos e pytest com TDD (teste escrito antes do código).
- O pacote não traz Ollama nem PyTorch; quem usa Ollama liga pelo backend compatível com OpenAI (ver 0009).
- Dependência nova só com justificativa e com licença compatível com MIT; evitar GPL e AGPL.

### Instalação

- Instalação nativa, planejada para um comando, via uv. Sem Docker.
- Multiplataforma: Linux, Windows e macOS. O desenvolvimento acontece no Linux; os instaladores chegam na fase 3 (64 bits; Windows e Linux primeiro, macOS depois, testado só no GitHub Actions).

### Por que sem Docker

- O Docker Desktop é pesado e, no Windows e no macOS, roda dentro de uma máquina virtual.
- Um Chrome visível para login manual e CAPTCHA fica difícil dentro de container.
- Microfone, início com o sistema e atalho são coisas do sistema operacional.
- O login do Claude Code teria de ser feito de novo dentro do container (no macOS ele fica no Keychain, que o container não enxerga).

## Tauri na fase 3 (2026-11-15)

- Na fase 3 entra o Tauri (Rust e HTML) como casca do app de desktop e como tela do instalador (D138, decisão 16; D142). A casca dá ao joBot ícone e janela própria em volta do mesmo painel, que continua em 127.0.0.1 e não é reescrito. A janela usa o navegador embutido do sistema (WebKitGTK, WebView2 ou WKWebView).
- O joBot em si continua instalado ~~pelo `uv tool install`, chamado pelo instalador~~ (superado em 2026-11-17: num venv montado pelo `uv` com `uv pip install --require-hashes`, a partir dos arquivos que vêm no instalador; D173 e D174). A lista de tecnologias acima não muda: o Rust fica só na casca, ~~num projeto à parte~~ na pasta `desktop/` do mesmo repositório (superado em 2026-11-17, ver abaixo).
- Como toda dependência, o Tauri entra com a licença conferida (regra acima).

## Pasta `desktop/` no mesmo repositório (2026-11-17)

- O projeto Tauri fica na pasta `desktop/` deste repositório, não num projeto à parte (D171.4). O pacote Python não importa nada dele; a casca só fala HTTP com o painel e chama o `jobot` e o `uv`. Ver [0025](0025-app-de-desktop-e-instalador.md).

## Consequências

- Cada sistema operacional precisa ser testado na fase 3.
- O instalador baixa só o necessário; o pacote de IA offline é opcional.
- Claude e Claude Code são marcas da Anthropic. O joBot não é afiliado à Anthropic.

## Ver também

- [0009. Inteligência artificial: opções, modelos e pacote offline](0009-ia-backends-e-modelos.md)
- [0010. Usar o Claude Code que a pessoa já tem (sem login dentro do joBot)](0010-claude-code-da-pessoa.md)
- [0016. Licença, sala limpa e processo de trabalho](0016-licenca-clean-room-e-processo.md)
- [0025. App de desktop e instalador](0025-app-de-desktop-e-instalador.md)
- [duvidas.md: D138 (instalador), D142 (app de desktop) e D171 (fase 3)](../../duvidas.md)
