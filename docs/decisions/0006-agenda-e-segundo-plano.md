# 0006. Agenda das buscas e segundo plano

- **Status:** aceita
- **Data:** 2026-11-13

## Contexto

Vagas boas fecham rápido, mas visitar sites com login com frequência aumenta o risco de bloqueio. E nem todo mundo quer um programa rodando o tempo todo.

## Decisão

### Frequência das buscas

- Fontes públicas: a cada 3 horas.
- Sites com login: duas vezes por dia (padrão 9h e 18h, ajustável).
- Botão "buscar agora" para tudo.

### Segundo plano

- Rodar em segundo plano é escolha da pessoa: oferecido no passo 5 do assistente de primeira execução e mudável nas configurações.
- Com o segundo plano ligado: o joBot inicia com o computador, sem janela, e um atalho "joBot" abre o painel.
- Se o computador estava desligado no horário, a execução perdida acontece quando ele liga.

## Consequências

- Com o segundo plano desligado, as buscas agendadas dependem de o joBot estar aberto.

## Ver também

- [0005. Sites que exigem login](0005-sites-com-login.md)
- [0011. Perfil, currículo, primeira execução e áudio](0011-perfil-e-primeira-execucao.md)
