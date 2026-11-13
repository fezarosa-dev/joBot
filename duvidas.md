# Dúvidas

Decisões que ainda dependem do dono do projeto.

## D1. Manter a opção "sessão do Claude Code"

**Status:** para confirmar

**Assunto:** manter a opção em que o joBot chama, de forma automática e agendada, o Claude Code que a própria pessoa instalou e logou.

**Contexto:** as regras da Anthropic proíbem que um app de terceiro ofereça login do Claude.ai, encaminhe pedidos pelas credenciais de planos em nome dos usuários ou intermedeie credenciais. Elas também colocam produtos que rodam o Claude Code sob os Termos Comerciais, com cada pessoa autenticada na própria conta. O joBot não toca em credenciais e não empacota o Claude Code, mas o uso automático e agendado é uma zona cinzenta.

**Decisão provisória:** manter como opção, com os cuidados da ADR 0010 e um aviso no README. Reler a política antes da publicação (fase 8). Se ficar proibido, o padrão passa a ser a chave da API ou um modelo local.

**Link:** [ADR 0010](docs/decisions/0010-claude-code-da-pessoa.md)

Claude e Claude Code são marcas da Anthropic. O joBot não é afiliado à Anthropic.

## D2. Titular do copyright no arquivo LICENSE

**Status:** decidir antes da fase 8

**Contexto:** a licença MIT pede uma linha `Copyright (c) <ano> <titular>`.

**Recomendação:** usar o nome público ou o apelido que vai aparecer no GitHub.

**Link:** [ADR 0016](docs/decisions/0016-licenca-clean-room-e-processo.md)
