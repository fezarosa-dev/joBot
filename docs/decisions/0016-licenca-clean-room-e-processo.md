# 0016. Licença, sala limpa e processo de trabalho

- **Status:** aceita
- **Data:** 2026-11-13

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
- Testes no GitHub só em PR para a `main`, quando o repositório estiver no GitHub.
- O repositório fica no GitHub, público. A publicação de verdade (instaladores e versão para uso) é a fase 8.

## Consequências

- O arquivo LICENSE entra na publicação (fase 8). O titular do copyright está em `duvidas.md` (D2).

## Ver também

- [0001. Escopo: o que o joBot é e o que não é](0001-escopo-do-jobot.md)
- [0004. Fontes públicas de vagas e coleta educada](0004-fontes-publicas.md)
- [0017. Fases do projeto](0017-fases.md)
