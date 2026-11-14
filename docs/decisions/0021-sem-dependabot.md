# 0021. Sem Dependabot: atualização de dependência à mão

- **Status:** aceita
- **Data:** 2026-11-14

## Contexto

O Dependabot abria pull requests sozinho para subir versões. Esses PRs atrapalhavam o dono do projeto, que é iniciante e trabalha por fase: chegavam fora de hora e cada um pedia atenção.

## Decisão

- O projeto não usa o Dependabot de versão nem o de segurança. Não existe `.github/dependabot.yml`, e as "Dependabot security updates" ficam desligadas no GitHub.
- Os alertas de vulnerabilidade (aba Security) continuam ligados. Eles só avisam; não abrem PR.
- A atualização é manual, no fim de cada fase, e entra no PR de fim de fase:
  1. `uv lock --upgrade`;
  2. versões das GitHub Actions nos workflows (`.github/workflows/*.yml`). As Actions ficam fixadas pelo hash do commit, com a versão em comentário; a atualização troca o hash e o comentário juntos;
  3. HTMX e fonte Inter vendorizados conferidos (versão e sha256);
  4. bateria verde: pytest de unidade e de tela, ruff e mypy.
- Na fase 1, isso inclui subir `actions/checkout` para a v7 e `astral-sh/setup-uv` para a v7, e o requisito `uv-build` para `<0.14` se o lock aceitar.
- Um teste de guarda (`test_sem_dependabot`) falha se o `dependabot.yml` voltar.

## Consequências

- Uma dependência pode ficar velha dentro da fase.
- Alerta crítico de segurança é tratado na hora, em uma branch `fix/`, sem esperar o fim da fase.

## Ver também

- [0016. Licença, sala limpa e processo de trabalho](0016-licenca-clean-room-e-processo.md)
- [0018. Manutenção pela comunidade e CI aberto a todo PR](0018-manutencao-pela-comunidade.md)
