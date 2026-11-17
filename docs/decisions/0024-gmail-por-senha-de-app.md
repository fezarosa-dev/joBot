# 0024. Gmail por senha de app

- **Status:** aceita
- **Data:** 2026-11-16

## Contexto

A [0013](0013-gmail-e-avisos.md) pedia que cada pessoa criasse o próprio projeto no Google Cloud, com um assistente de cerca de 15 minutos, para o joBot ler o Gmail por OAuth. O motivo era o escopo `gmail.readonly`, que o Google trata como restrito: um projeto único para todos exigiria a verificação do Google.

Esse caminho é trabalhoso, e muita gente não consegue fazê-lo. O dono do projeto, em 2026-11-16, trocou-o por IMAP com uma senha de app do Google, que a pessoa cria na própria conta e cola no painel. As decisões do dono e as escolhas da sessão que ainda esperam confirmação estão na D145 do `duvidas.md`.

## Decisão

### Acesso por IMAP com senha de app

- O joBot lê o Gmail por IMAP, com uma senha de app do Google que a pessoa cola no painel. Isto substitui o projeto no Google Cloud por pessoa da 0013 (login com OAuth, escopo `gmail.readonly`, PKCE e redirecionamento local).
- Servidor `imap.gmail.com`, porta 993, SSL. Biblioteca padrão `imaplib`: sem dependência nova.
- A conferência de login abre a caixa de entrada só para leitura (`EXAMINE`).
- A senha de app tem 16 letras, mostradas em 4 grupos separados por espaço. O joBot tira os espaços. Ela exige a verificação em duas etapas ligada na conta Google.
- Desde janeiro de 2025 o IMAP fica sempre ligado nas contas pessoais do Google. Não há passo para ligá-lo.
- Só contas Google (Gmail). Outros provedores de e-mail ficam fora.

### Senha guardada no cofre

- A pessoa cola o endereço e a senha de app no painel. O joBot guarda os dois no cofre local ([0014](0014-seguranca-e-privacidade.md): keyring, com arquivo só do usuário como plano B), com os nomes `gmail_conta` e `gmail_senha_de_app`.
- O joBot continua sem digitar a senha da conta Google em lugar nenhum. A senha de app é outra credencial: nasce na conta Google, por escolha da pessoa, e só vale para esse uso. A pessoa a apaga quando quiser, no mesmo lugar onde a criou.

### Onde aparece

- O cartão do Gmail entra na aba Contas, já no lote de Contas (`docs/superpowers/specs/2026-11-15-contas-design.md`): campos de endereço e de senha de app, o botão "Conferir agora" com login só de leitura e os estados "Conectado" e "Precisa entrar de novo".
- A leitura dos e-mails (alertas de vagas e respostas de recrutadores) continua na fase 6 ([0017](0017-fases.md)).
- O tutorial de como criar a senha de app é uma página da wiki, em português e em inglês, com os links oficiais do Google. O painel linka para ela.

### O que fica de fora

- O projeto do Google Cloud por pessoa vira tarefa futura, só para quem não consegue a senha de app (contas de trabalho ou escola, Proteção Avançada, verificação em duas etapas só com chaves de segurança).
- Um cliente OAuth único e verificado, do projeto, fica descartado por ora. A revisão de escopo restrito leva semanas e pede avaliação de segurança anual (CASA); não confirmamos se um app que só guarda os dados no aparelho fica isento. Um cliente não verificado tem teto de 100 usuários no total.

### O que continua valendo da 0013

- O Gmail é opcional.
- Os usos: ler e-mails de alerta de vagas e trazer as vagas para o painel; ler respostas de recrutadores e sugerir a mudança de status, confirmada com um clique.
- Sem notificações push e sem ntfy no app. A única exceção é o resumo diário opcional no Telegram, com um bot da própria pessoa, desligado por padrão.
- A frase "Sem senha de app do Google" da 0013 deixa de valer.

## Consequências

- Sem projeto no Google Cloud e sem espera de verificação do Google: a pessoa leva poucos minutos.
- O joBot passa a guardar uma credencial que dá acesso à caixa de e-mail. A senha de app dá acesso total ao e-mail (ler, apagar e enviar) a quem a tiver; só o joBot se limita a ler (`EXAMINE`, só leitura). O limite "só leitura" deixa de ser do Google (o escopo do OAuth) e passa a ser do próprio joBot, que só abre a caixa para leitura. Se a senha vazar, ela serve até a pessoa apagá-la na conta Google.
- Não serve para contas de trabalho ou escola (Google Workspace gerenciado), para quem usa a Proteção Avançada nem para quem tem a verificação em duas etapas só com chaves de segurança. Para essas pessoas o Gmail fica indisponível até a tarefa futura do projeto próprio.
- O Google revoga todas as senhas de app quando a pessoa troca a senha da conta. O cartão passa a "Precisa entrar de novo", e a pessoa cria outra senha de app.
- A 0013 ganha uma nota de que foi substituída em parte (acesso ao Gmail). A 0014 passa a falar em "senha de app do Gmail" onde falava em "token do Gmail". README e wiki trocam "projeto Google criado por você" por "senha de app".
- Texto novo do painel entra nos catálogos `pt` e `en`.
- Desfazer: tirar o cartão do Gmail e a nota da 0013. Quem já colou a senha a apaga na conta Google.

## Ver também

- [0005. Sites que exigem login](0005-sites-com-login.md)
- [0013. Gmail e avisos](0013-gmail-e-avisos.md)
- [0014. Segurança e privacidade](0014-seguranca-e-privacidade.md)
- [0017. Fases do projeto](0017-fases.md)
- [0023. Tudo pelo painel](0023-tudo-pelo-painel.md)
