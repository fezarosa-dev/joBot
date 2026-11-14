# Como contribuir com o joBot

**Português** · [English](CONTRIBUTING.en.md)

Obrigado pelo interesse! Este guia explica como ajudar com o joBot, agora e depois da publicação.

## Estado do projeto

O joBot ainda não tem código e ainda não há nada para instalar. A fase 1 (base) está em desenho. As decisões já tomadas estão em [`docs/decisions/`](../docs/decisions/README.md) (só em português por enquanto). Para saber o que o projeto é e para onde ele vai, leia o [README](../README.md).

## Como ajudar agora

- **Sugestões e fontes de vagas** são bem-vindas desde já. Abra uma issue pelos formulários: Bug, Sugestão ou Fonte de vagas.
- **Pull requests de código** só serão aceitos depois da publicação (fase 8). Até lá, o código ainda está mudando muito.
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

## Fluxo para código (depois da fase 8)

1. Faça um fork do repositório.
2. Crie um ramo a partir da `dev` atualizada, com o prefixo certo (`feat/`, `fix/`, `docs/` ou `ci/`).
3. Escreva o teste, veja ele falhar, implemente e veja ele passar (TDD).
4. Confira que `ruff`, `mypy --strict` e `pytest` passam.
5. Faça commits pequenos, em português, no formato `tipo(escopo): descrição`.
6. Abra um PR para a `dev` usando o [modelo de PR](pull_request_template.md).

Os comandos exatos para rodar tudo serão documentados quando o código existir.

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
