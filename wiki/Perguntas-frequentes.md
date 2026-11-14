English: [Frequently asked questions](Frequently-asked-questions)

<details>
<summary><strong>Por que não usar Docker?</strong></summary>

O público é leigo e usa computadores comuns. O Docker Desktop é pesado e, no Windows e no macOS, roda dentro de uma máquina virtual.
O joBot precisa abrir um Chrome visível para você fazer login e resolver CAPTCHA, usar o microfone, iniciar com o sistema e criar atalhos. Tudo isso é difícil dentro de um container.
E o login do Claude Code teria de ser feito de novo lá dentro (no macOS ele fica no Keychain, que o container não enxerga). Veja a [ADR 0003](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0003-stack-e-instalacao-nativa.md).
</details>

<details>
<summary><strong>Preciso fazer login do Claude dentro do joBot?</strong></summary>

Não. Você entra uma vez no Claude Code, pelo terminal, no fluxo da própria Anthropic. O joBot só detecta que está pronto e usa.
Ele nunca vê a sua senha nem o seu token. Veja [Usando o Claude Code que você já tem](https://github.com/fezarosa-dev/joBot#usando-o-claude-code) e a [ADR 0010](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0010-claude-code-da-pessoa.md).
</details>

<details>
<summary><strong>Preciso pagar alguma coisa?</strong></summary>

O joBot é grátis e de código aberto. O Claude é opcional e pago, por assinatura ou pela API.
O modelo local, as palavras-chave e a IA manual são grátis.
</details>

<details>
<summary><strong>Funciona sem IA? E sem internet?</strong></summary>

Sem IA, sim: o joBot usa regras e palavras-chave.
Sem internet, vagas novas não chegam. Mas o painel continua funcionando, e o modelo local também.
</details>

<details>
<summary><strong>O joBot se candidata sozinho?</strong></summary>

Não. Ele prepara a candidatura e ajuda a preencher formulários, mas quem revisa e envia é sempre você.
</details>

<details>
<summary><strong>Minha conta do LinkedIn pode ser restringida?</strong></summary>

Pode. O risco existe, e não dá para zerar.
O joBot reduz o risco: você faz o login com as próprias mãos, ele só lê, visita poucas vezes por dia, vai devagar e nunca contorna CAPTCHA.
Cada site com login tem uma chave. Você decide se liga.
</details>

<details>
<summary><strong>E se aparecer um CAPTCHA?</strong></summary>

O painel mostra um aviso vermelho e o computador mostra uma notificação. A janela do navegador fica parada na página, esperando você resolver.
As outras fontes continuam normalmente. O joBot nunca tenta passar pelo CAPTCHA sozinho.
</details>

<details>
<summary><strong>Meus dados vão para algum servidor?</strong></summary>

Não existe servidor do joBot. Seus dados ficam no seu computador.
Eles só vão para os serviços que você ligar: Anthropic (se usar o Claude), Google (se ligar o Gmail) e Telegram (se ligar o resumo diário). Também podem ir para o Jev (se escolher essa opção na classificação de e-mail) e para o RunPod (só no treino da fase 6). Na IA manual, vão para a IA de chat onde você colar.
</details>

<details>
<summary><strong>Roda no meu computador?</strong></summary>

A ideia é rodar em computadores comuns, com 8 a 16 GB de RAM e sem placa de vídeo dedicada, com Linux, Windows ou macOS.
</details>
