🌐 **Português** · [English](Frequently-asked-questions)

# ❓ Perguntas frequentes

**As dúvidas mais comuns sobre o joBot. Clique numa pergunta para ver a resposta.**

---

<details>
<summary><strong>Por que não usar Docker?</strong></summary>

O público é leigo e usa computadores comuns. O Docker Desktop é pesado e, no Windows e no macOS, roda dentro de uma máquina virtual.
O joBot precisa abrir uma janela do navegador para você fazer login, usar o microfone, iniciar com o sistema e criar atalhos. Tudo isso é difícil dentro de um container.
E o login do Claude Code teria de ser feito de novo lá dentro (no macOS ele fica no Keychain, que o container não enxerga). Veja a [ADR 0003](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0003-stack-e-instalacao-nativa.md).
</details>

<details>
<summary><strong>Preciso fazer login do Claude dentro do joBot?</strong></summary>

Não. Você entra uma vez no Claude Code, pelo terminal, no fluxo da própria Anthropic. O joBot só detecta que está pronto e usa.
Ele nunca vê a sua senha nem o seu token. Essa sessão ainda espera a decisão do dono sobre os termos de uso; na 0.5.0, o Claude entra pela chave da API da Anthropic, posta em Configurações › Serviços. Veja [Usando o Claude Code que você já tem](https://github.com/fezarosa-dev/joBot#usando-o-claude-code) e a [ADR 0010](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0010-claude-code-da-pessoa.md).
</details>

<details>
<summary><strong>Preciso pagar alguma coisa?</strong></summary>

O joBot é grátis e de código aberto. O Claude, a OpenAI e o Gemini são opcionais, com a sua chave: o Claude e a OpenAI são pagos por uso, e o Gemini pode ser cobrado por uso, conforme o plano da sua conta no Google AI Studio.
O modelo local, as palavras-chave e a IA manual são grátis.
</details>

<details>
<summary><strong>Funciona sem IA? E sem internet?</strong></summary>

Sem IA, sim: o joBot usa regras e palavras-chave.
Sem internet, vagas novas não chegam. Mas o painel continua funcionando, e o modelo local também, depois de baixado. O README tem a [tabela do que funciona sem internet](https://github.com/fezarosa-dev/joBot#o-que-funciona-sem-internet).
</details>

<details>
<summary><strong>O joBot se candidata sozinho?</strong></summary>

Não. Ele prepara a candidatura e ajuda a preencher formulários, mas quem revisa e envia é sempre você.
</details>

<details>
<summary><strong>Minha conta do LinkedIn pode ser restringida?</strong></summary>

Pode. O risco existe, e não dá para zerar.
O joBot reduz o risco: você faz o login com as próprias mãos, numa janela comum do navegador, ele só lê, visita poucas vezes por dia, vai devagar e não contorna CAPTCHA sozinho (só o seu 2Captcha, se você ligar).
Cada site com login tem uma chave. Você decide se liga.
</details>

<details>
<summary><strong>O que quer dizer "fechada" para uma vaga do LinkedIn?</strong></summary>

A busca do LinkedIn ordena por relevância, e o joBot lê só a última semana. Por isso uma vaga aberta pode sumir da lista sem ter fechado.
Para o LinkedIn, "fechada" quer dizer "não vista há 30 dias". Se uma vaga fechada por engano voltar à lista, ela reabre sozinha.
</details>

<details>
<summary><strong>E se aparecer um CAPTCHA?</strong></summary>

O painel mostra um aviso vermelho e o computador mostra uma notificação. A janela do navegador fica parada na página, esperando você resolver.
As outras fontes continuam normalmente. O joBot nunca tenta passar pelo CAPTCHA sozinho.
Na navegação com login, se você puser a chave do seu 2Captcha e ligar o interruptor em Configurações, Serviços (vem desligado), o joBot manda o desafio para o 2Captcha antes. Se ele não resolver, vale o aviso acima.
</details>

<details>
<summary><strong>Como deixo o joBot ler o meu Gmail?</strong></summary>

Com uma senha de app do Google, que você cria na sua conta e cola no joBot. Não precisa criar projeto no Google Cloud.
Funciona com contas Google pessoais. Não funciona com contas de trabalho ou escola, com a Proteção Avançada nem com a verificação em duas etapas só por chaves de segurança.
O cartão do Gmail está em Configurações, Contas, e a leitura dos e-mails continua na fase 6. Veja o [passo a passo](Gmail-senha-de-app) e a [ADR 0024](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0024-gmail-por-senha-de-app.md).
</details>

<details>
<summary><strong>Meus dados vão para algum servidor?</strong></summary>

Não existe servidor do joBot. Seus dados ficam no seu computador.
Eles só vão para os serviços que você ligar: Anthropic, OpenAI ou Google (se ligar uma tarefa de IA num deles; vai só o texto da vaga, nunca o seu perfil), o endereço de IA que você digitar, Google (se ligar o Gmail) e Telegram (se ligar o resumo diário). Também podem ir para o Jev (se escolher essa opção na classificação de e-mail). O RunPod nunca recebe dado seu: o treino do Laya roda fora do app, só com vagas de fontes públicas. Na IA manual, vão para a IA de chat onde você colar.
</details>

<details>
<summary><strong>Roda no meu computador?</strong></summary>

A ideia é rodar em computadores comuns, com 8 a 16 GB de RAM e sem placa de vídeo dedicada, com Linux, Windows ou macOS.
</details>
