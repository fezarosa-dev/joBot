# Como contribuir com o joBot

**Português** · [English](CONTRIBUTING.en.md)

Obrigado pelo interesse! Este guia explica como ajudar com o joBot, agora e depois da publicação.

## Estado do projeto

As fases 1, 2 e 3 (base, navegador com login e instalador) estão concluídas: o joBot 0.4.0 já dá para instalar e usar ([como instalar](../README.md#requisitos-e-instalacao)). A fase 4 (IA local) está sendo construída, rumo à 0.5.0; as fases 5 a 9 estão planejadas. As decisões já tomadas estão em [`docs/decisions/`](../docs/decisions/README.md) (só em português por enquanto). Para saber o que o projeto é e para onde ele vai, leia o [README](../README.md).

## Como ajudar agora

- **Sugestões e fontes de vagas** são bem-vindas desde já. Abra uma issue pelos formulários: Bug, Sugestão ou Fonte de vagas.
- **Uma fonte de vagas quebrou?** O guia [Como consertar uma fonte que quebrou](../docs/consertar-fonte.md) mostra como achar o que mudou e consertar. Hoje ele serve para você entender o caminho e relatar o que achou numa issue; o PR com o conserto segue a regra abaixo.
- **Quer acrescentar um site de vagas novo?** O guia [Como acrescentar um site novo](../docs/site-novo.md) leva do site ao PR, com um molde que já roda para o site público e outro para o site com login. Hoje serve para você se preparar e abrir a issue "Fonte de vagas"; o PR segue a regra abaixo.
- **Pull requests de código** só serão aceitos depois da publicação (fase 9). Até lá, o código ainda está mudando muito.
- Issues e PRs podem ser escritos em **português ou inglês**.
- Achou uma falha de segurança? **Não abra issue pública.** Veja a [Política de Segurança](SECURITY.md).
- Precisa de ajuda ou tem uma dúvida? Veja o [Suporte](SUPPORT.md).
- Ao participar, você aceita o [Código de Conduta](CODE_OF_CONDUCT.md).

## Regras do projeto

- **TDD em todo código.** Escreva o teste primeiro, veja ele falhar, escreva o código e veja o teste passar.
- **Commits em português**, no formato `tipo(escopo): descrição`. Os tipos são: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `chore`, `style` e `revert`.
- **Ramos:** use `feat/`, `fix/`, `docs/` ou `ci/` no começo do nome, saindo da `dev`. A `main` só recebe PR vindo da `dev`.
- **Qualidade:** o `ruff` cuida do estilo, o `mypy` no modo estrito (`--strict`) cuida dos tipos e o `pytest` roda os testes.
- **Dependência nova** só com justificativa e com licença compatível com a MIT.

## Compilar a janela (casca)

A janela do joBot é um app Tauri 2, em Rust, na pasta `desktop/` ([ADR 0025](../docs/decisions/0025-app-de-desktop-e-instalador.md)). Ela fica fora do pacote Python: só fala HTTP com o painel e chama o `jobot` e o `uv`. Para mexer nela:

1. Instale o Rust pelo [rustup](https://rustup.rs/). A versão fica fixada em `desktop/rust-toolchain.toml`, e o rustup a escolhe sozinho dentro de `desktop/`.
2. No Linux, instale as bibliotecas do WebKitGTK. No Debian e no Ubuntu: `sudo apt install libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf`. Em outras distros os nomes mudam; veja os pré-requisitos do [Tauri](https://v2.tauri.app/start/prerequisites/).
3. Instale a CLI do Tauri na mesma versão do build da release: `cargo install tauri-cli --version =2.12.4 --locked`.
4. Dentro de `desktop/`, `cargo tauri dev` abre a janela em modo de desenvolvimento. Antes do PR, rode lá `cargo fmt --check`, `cargo clippy --locked --all-targets -- -D warnings` e `cargo test --locked`, os mesmos do CI ([`casca.yml`](workflows/casca.yml)).

**Recursos.** No build, o `desktop/build.rs` copia o CSS, as fontes e o ícone do painel para `desktop/ui/painel/` e cria `desktop/recursos/` vazia; as duas pastas são ignoradas pelo git. Com os recursos vazios, a janela diz que o instalador está incompleto: em desenvolvimento, é o esperado. Se o joBot já estiver instalado pela janela, ela abre direto no controle (Ligar, Parar e Abrir joBot); para ver a tela de instalação sem tocar nos seus dados, aponte `JOBOT_DADOS` para uma pasta vazia.

Os recursos de verdade (o `uv`, o Python, as wheels, o joBot e o `manifesto.json`; o navegador não vai nos recursos, vem do `playwright install`) saem do `scripts/montar_recursos.py recursos`, que confere o sha256 de cada download e imprime o do manifesto; esse valor entra no build pela variável `JOBOT_MANIFESTO_SHA256`. A receita inteira, passo a passo, é o job `casca` de [`pacotes.yml`](workflows/pacotes.yml), que a release roda e que o `casca.yml` roda à mão com a entrada `pacotes`. Cada instalador pesa de uns 100 a 200 MB: para provar uma mudança no pacote, prefira o CI.

## Fluxo para código (depois da fase 9)

1. Faça um fork do repositório.
2. Crie um ramo a partir da `dev` atualizada, com o prefixo certo (`feat/`, `fix/`, `docs/` ou `ci/`).
3. Escreva o teste, veja ele falhar, implemente e veja ele passar (TDD).
4. Confira que `ruff`, `mypy --strict` e `pytest` passam.
5. Faça commits pequenos, em português, no formato `tipo(escopo): descrição`.
6. Abra um PR para a `dev` usando o [modelo de PR](pull_request_template.md).
7. Espere: os testes do seu PR só rodam depois que o responsável pelo projeto liberar, e o PR só entra com a aprovação dele.

## Wiki

- O texto da wiki mora na pasta [`wiki/`](../wiki/) do repositório.
- Mudança na wiki é por PR nessa pasta, como qualquer outro arquivo.
- Quando o PR entra na `main`, um robô copia a pasta para a wiki do GitHub.
- A edição direta na wiki do GitHub fica só com quem mantém o projeto. Ela é sobrescrita na próxima cópia, então toda mudança vai pela pasta `wiki/`.
- Página nova precisa da versão nas duas línguas (português e inglês). O teste confere.

## Sala limpa

Você pode usar ideias e fatos públicos de outros projetos. Nunca copie código nem dados de teste de terceiros.

## Licença

O joBot usa a [licença MIT](../LICENSE). Ao contribuir, você aceita que sua contribuição entre no projeto sob a mesma licença.
