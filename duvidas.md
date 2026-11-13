# Dúvidas

Decisões que dependem do dono do projeto. As resolvidas ficam registradas aqui, com a data.

## D1. Manter a opção "sessão do Claude Code"

**Status:** resolvida em 2026-11-13

**Assunto:** manter a opção em que o joBot chama, de forma automática e agendada, o Claude Code que a própria pessoa instalou e logou.

**Contexto:** as regras da Anthropic proíbem que um app de terceiro ofereça login do Claude.ai, encaminhe pedidos pelas credenciais de planos em nome dos usuários ou intermedeie credenciais. Elas também colocam produtos que rodam o Claude Code sob os Termos Comerciais, com cada pessoa autenticada na própria conta. O joBot não toca em credenciais e não empacota o Claude Code.

**Decisão:** manter a opção. O dono do projeto leu as regras da Anthropic e decidiu que esse uso está dentro delas: cada pessoa roda o próprio Claude Code, no próprio computador, com a própria assinatura e dentro do próprio limite. Nada é compartilhado entre pessoas. Os cuidados técnicos da ADR 0010 continuam valendo.

**Link:** [ADR 0010](docs/decisions/0010-claude-code-da-pessoa.md)

Claude e Claude Code são marcas da Anthropic. O joBot não é afiliado à Anthropic.

## D2. Titular do copyright no arquivo LICENSE

**Status:** resolvida em 2026-11-13

**Contexto:** a licença MIT pede uma linha `Copyright (c) <ano> <titular>`.

**Decisão:** o titular é o apelido público do dono do projeto no GitHub. O arquivo [`LICENSE`](LICENSE) já está no repositório.

**Link:** [ADR 0016](docs/decisions/0016-licenca-clean-room-e-processo.md)

## D3. Contato para denúncias do Código de Conduta

**Status:** resolvida em 2026-11-13

**Contexto:** o Código de Conduta pede um contato privado para denúncias.

**Decisão:** o contato é o e-mail fezarosa@gmail.com, escolhido pelo dono do projeto. Ele está no Código de Conduta, em português e em inglês.

**Link:** [`.github/CODE_OF_CONDUCT.md`](.github/CODE_OF_CONDUCT.md)

## D4. Botão de patrocínio (FUNDING.yml)

**Status:** para confirmar

**Contexto:** o arquivo `.github/FUNDING.yml` mostra o botão Sponsor, mas precisa de uma conta de patrocínio, como GitHub Sponsors ou Ko-fi, que o projeto ainda não tem.

**Decisão provisória:** sem `FUNDING.yml` até o dono criar a conta e dizer qual usar.
