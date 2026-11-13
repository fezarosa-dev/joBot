# 0013. Gmail e avisos

- **Status:** aceita
- **Data:** 2026-11-13

## Contexto

Muitas vagas e respostas de recrutadores chegam por e-mail. O escopo (tipo de permissão) de leitura do Gmail é restrito: um projeto Google único para todos exigiria a verificação do Google. O projeto ainda não tem código; isto é o plano.

## Decisão

- Login do Google com OAuth (forma padrão de dar permissão sem passar a senha), escopo `gmail.readonly` (só leitura), só para contas @gmail.com. A pessoa escolhe a conta no app.
- Cada pessoa cria o próprio projeto no Google Cloud, com um assistente guiado (cerca de 15 minutos), no modo "Em produção", sem verificação. O modo de teste não serve: os tokens expiram em 7 dias.
- Cliente público de desktop, com PKCE (proteção extra do login) e redirecionamento local (loopback).
- É opcional.
- Usos:
  - ler e-mails de alerta de vagas e trazer as vagas para o painel;
  - ler respostas de recrutadores e sugerir a mudança de status, confirmada com um clique.
- Sem senha de app do Google.
- Sem notificações push e sem ntfy no app. Única exceção: resumo diário opcional no Telegram, com um bot da própria pessoa, desligado por padrão. Sem canal público e sem assinantes.

## Consequências

- Configurar o Gmail dá algum trabalho, mas cada pessoa controla o próprio acesso.

## Ver também

- [0009. Inteligência artificial: opções, modelos e pacote offline](0009-ia-backends-e-modelos.md)
- [0011. Perfil, currículo, primeira execução e áudio](0011-perfil-e-primeira-execucao.md)
- [0014. Segurança e privacidade](0014-seguranca-e-privacidade.md)
