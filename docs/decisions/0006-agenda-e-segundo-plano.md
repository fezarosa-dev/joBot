# 0006. Agenda das buscas e segundo plano

- **Status:** aceita
- **Data:** 2026-11-13
- **Atualizada:** 2026-11-13

## Contexto

Vagas boas fecham rápido, mas visitar sites com login com frequência aumenta o risco de bloqueio. E nem todo mundo quer um programa rodando o tempo todo.

## Decisão

### Frequência das buscas

- Fontes públicas: a cada 3 horas.
- Sites com login: duas vezes por dia (padrão 9h e 18h, ajustável).
- Botão "buscar agora": busca tudo na hora, sem esperar o intervalo da agenda. Só respeita as fontes com intervalo mínimo (ADR 0004), inclusive as de intervalo prático.
- As 3 horas contam a partir da última busca completa, feita pela agenda ou pelo "buscar agora".

### Segundo plano

- Rodar em segundo plano é escolha da pessoa: oferecido no assistente de primeira execução e mudável nas configurações.
- Na fase 1, o segundo plano é o passo 2 da primeira execução. O assistente da fase 1 só tem preferências de busca e segundo plano; os outros passos chegam com as fases deles.
- Com o segundo plano ligado: o joBot inicia com o computador, sem janela, e um atalho "joBot" abre o painel.
- Se o joBot roda dentro de uma distrobox, o serviço do segundo plano e o atalho passam pelo distrobox-enter. O systemd do sistema principal não enxerga programas dentro do container.
- Se o computador estava desligado no horário, a execução perdida acontece quando ele liga.

## Consequências

- Com o segundo plano desligado, as buscas agendadas dependem de o joBot estar aberto.

## Ver também

- [0005. Sites que exigem login](0005-sites-com-login.md)
- [0011. Perfil, currículo, primeira execução e áudio](0011-perfil-e-primeira-execucao.md)
