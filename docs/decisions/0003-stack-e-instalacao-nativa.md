# 0003. Tecnologias e instalação nativa (sem Docker)

- **Status:** aceita
- **Data:** 2026-11-13

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
- Sem Ollama e sem PyTorch (ver 0009).
- Dependência nova só com justificativa e com licença compatível com MIT; evitar GPL e AGPL.

### Instalação

- Instalação nativa, planejada para um comando, via uv. Sem Docker.
- Multiplataforma: Linux, Windows e macOS. O desenvolvimento acontece no Linux; os instaladores de Windows e macOS chegam na fase 8.

### Por que sem Docker

- O Docker Desktop é pesado e, no Windows e no macOS, roda dentro de uma máquina virtual.
- Um Chrome visível para login manual e CAPTCHA fica difícil dentro de container.
- Microfone, início com o sistema e atalho são coisas do sistema operacional.
- O login do Claude Code teria de ser feito de novo dentro do container (no macOS ele fica no Keychain, que o container não enxerga).

## Consequências

- Cada sistema operacional precisa ser testado na fase 8.
- O instalador baixa só o necessário; o pacote de IA offline é opcional.
- Claude e Claude Code são marcas da Anthropic. O joBot não é afiliado à Anthropic.

## Ver também

- [0009. Inteligência artificial: opções, modelos e pacote offline](0009-ia-backends-e-modelos.md)
- [0010. Usar o Claude Code que a pessoa já tem (sem login dentro do joBot)](0010-claude-code-da-pessoa.md)
- [0016. Licença, sala limpa e processo de trabalho](0016-licenca-clean-room-e-processo.md)
