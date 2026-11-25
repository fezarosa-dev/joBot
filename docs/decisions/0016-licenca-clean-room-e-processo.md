# 0016. Licença, sala limpa e processo de trabalho

- **Status:** aceita
- **Data:** 2026-11-13
- **Atualizada:** 2026-11-14; 2026-11-24 (exceção da reescrita do histórico, D221.4)

## Contexto

O projeto vai ser público e quer poder reaproveitar ideias de outros projetos sem herdar obrigações de licença. Também precisa de um jeito de trabalhar que mantenha o histórico limpo e o código testado.

## Decisão

### Licença

- Licença MIT.
- Dependências com licença compatível; evitar GPL e AGPL.

### Sala limpa (clean-room)

- Ideias e fatos públicos podem ser usados: endereços de API, formato dos campos, identificadores de quadros de vagas.
- Código e fixtures (dados de exemplo para teste) de terceiros nunca são copiados.
- Todas as fixtures são capturadas por nós.

### Processo

- Git: ramos `main` e `dev`. O trabalho é feito em ramos `feat/`, `fix/`, `docs/` e `ci/` saindo da `dev`. A `main` só recebe PR (pedido de integração) vindo da `dev`.
- Commits em português, no formato `tipo(escopo): descrição`.
- TDD em todo código: escrever o teste, ver falhar, implementar, ver passar.
- Testes no GitHub rodam em todo PR, inclusive de fork e para a `dev` (ver [0018](0018-manutencao-pela-comunidade.md)).
- O repositório fica no GitHub, público. A publicação de verdade (versão para uso) é a fase 9; os instaladores vêm antes, na fase 3.

### Idiomas e arquivos da comunidade

- Desde 2026-11-13, a documentação para quem usa e contribui (README e arquivos de comunidade) existe em português e em inglês. O arquivo principal é em português e a versão em inglês fica ao lado, com final `.en.md`. As ADRs e o `duvidas.md` ficam só em português.
- O repositório tem os arquivos de comunidade do GitHub em `.github/`: Código de Conduta (Contributor Covenant), política de segurança, guia de contribuição, suporte, modelos de issue e de PR e CODEOWNERS. Na raiz ficam o `CHANGELOG.md` e o `CITATION.cff`.
- Falhas de segurança chegam pelo relato privado de vulnerabilidade do GitHub.
- A `main` só recebe mudanças por PR vindo da `dev`. Histórico que já subiu não é reescrito. Única exceção até hoje: em 2026-11-24 o dono decidiu reescrever o histórico para tirar um dado pessoal de duas fixtures de teste (`git filter-repo`, force push com as regras desligadas por cerca de 1 minuto e religadas logo depois; ver `duvidas.md`, D221.4 e D221.5, e o aviso a quem clonou no CHANGELOG da 0.6.0).
- No GitHub, regras de proteção garantem isso: a `main` só aceita mudança por PR e não pode ser reescrita nem apagada; a `dev` não pode ser reescrita nem apagada.
- Todo PR para a `main` ou para a `dev` só entra com a aprovação do responsável (`.github/CODEOWNERS`): uma aprovação, que cai se entrar commit novo, e o último push também precisa ser aprovado. A única exceção é o papel de administrador do repositório (o dono): na `main`, só por dentro de um PR, para juntar o próprio PR da `dev` (o GitHub não deixa aprovar o próprio PR); na `dev`, sempre, para o fluxo de lotes. Configurado nas regras `proteger-main` e `proteger-dev` em 2026-11-17 (D172).

## Consequências

- O arquivo [`LICENSE`](../../LICENSE) (MIT) está no repositório desde 2026-11-13. O titular é o apelido público do dono do projeto no GitHub (ver `duvidas.md`, D2).

## Ver também

- [0001. Escopo: o que o joBot é e o que não é](0001-escopo-do-jobot.md)
- [0004. Fontes públicas de vagas e coleta educada](0004-fontes-publicas.md)
- [0017. Fases do projeto](0017-fases.md)
- [duvidas.md: D221 (a reescrita do histórico de 2026-11-24)](../../duvidas.md)
