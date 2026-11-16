🌐 **Português** · [English](Gmail-app-password)

# 🔑 Gmail com senha de app

**Como deixar o joBot ler o seu Gmail, passo a passo, sem criar projeto no Google.**

---

> [!NOTE]
> O cartão do Gmail está em Configurações, Contas. A leitura dos e-mails de alerta e das respostas de recrutadores continua na fase 6; por enquanto o cartão só confere o login.

## 🤔 O que é e por que o joBot usa

Uma **senha de app** é uma senha de 16 letras que o Google cria só para um programa. Ela não é a senha da sua conta. Você a cola no joBot, e ele a usa para entrar na sua caixa de entrada pelo IMAP (o jeito padrão de programas de e-mail lerem mensagens).

Assim você não precisa criar um projeto no Google Cloud, nem esperar aprovação do Google. Leva poucos minutos.

## ✅ Antes de começar

- Você precisa de uma conta Google pessoal (Gmail). Por enquanto o joBot só trabalha com Gmail.
- A senha de app **não está disponível** em contas de trabalho ou escola (Google Workspace gerenciado), para quem usa a Proteção Avançada do Google e para quem tem a verificação em duas etapas só com chaves de segurança. Nesses casos o Gmail fica indisponível por enquanto. O caminho de um projeto próprio no Google Cloud é uma tarefa futura.
- O IMAP já vem ligado nas contas pessoais desde janeiro de 2025. Não há nada para ligar.

## 1️⃣ Ligue a verificação em duas etapas

1. Abra a [verificação em duas etapas](https://myaccount.google.com/signinoptions/two-step-verification) da sua conta Google.
2. Se ela já estiver ligada, pule para o passo 2. Se não, siga as telas do Google para ligar.

Ajuda do Google: [verificação em duas etapas](https://support.google.com/accounts/answer/185839).

## 2️⃣ Crie a senha de app

1. Abra a página de [senhas de app](https://myaccount.google.com/apppasswords).
2. Dê um nome para a senha, por exemplo `joBot`.
3. Clique em criar. O Google mostra 16 letras, em 4 grupos separados por espaço.
4. Copie as 16 letras. **O Google só mostra a senha uma vez.** Se fechar a janela sem copiar, apague essa senha e crie outra.

Ajuda do Google: [senhas de app](https://support.google.com/accounts/answer/185833).

## 3️⃣ Cole no joBot

1. No painel do joBot, abra Configurações, Contas, e vá ao cartão do Gmail.
2. Digite o seu endereço do Gmail e cole a senha de app. Pode colar com os espaços: o joBot os tira.
3. Clique em **Conferir agora**. O joBot entra na caixa de entrada só para ler, sem mexer em nada.

O cartão mostra o estado:

- **Conectado**: deu certo.
- **Precisa entrar de novo**: o Google recusou a senha. Crie outra senha de app e cole de novo.
- **Não deu para conferir**: não foi possível falar com o Google, por exemplo sem internet. Tente de novo daqui a pouco.

## 🔄 Troquei a senha da conta Google. E agora?

O Google apaga todas as senhas de app quando você troca a senha da conta. O cartão do Gmail passa a **Precisa entrar de novo**. Faça o passo 2 outra vez e cole a nova senha de app.

## 🗑️ Como apagar a senha de app

Abra de novo a página de [senhas de app](https://myaccount.google.com/apppasswords) e apague a senha chamada `joBot`. O joBot perde o acesso na hora.

## 🔒 O que o joBot faz com a senha

- Guarda o endereço e a senha de app só no seu computador, no cofre de senhas do sistema. Sem cofre, vão para um arquivo que só o seu usuário lê, e o painel avisa.
- Usa a senha só para entrar na caixa de entrada e ler. O joBot só abre a caixa para leitura. Lembre que a senha de app em si dá acesso total ao seu e-mail (ler, apagar e enviar) a quem a tiver; só o joBot se limita a ler.
- Nunca digita a senha da sua conta Google.

Quer saber o porquê da escolha? Veja a [ADR 0024](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0024-gmail-por-senha-de-app.md) e as [perguntas frequentes](Perguntas-frequentes).
