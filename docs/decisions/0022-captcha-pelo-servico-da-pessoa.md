# 0022. CAPTCHA resolvido pelo serviço que a pessoa liga

- **Status:** aceita
- **Data:** 2026-11-15

## Contexto

Nos sites que exigem login (ADR 0005), um CAPTCHA (desafio para provar que não é robô) para a busca: a janela fica parada até a pessoa resolver. Quem deixa o joBot rodar sozinho, duas vezes por dia, só vê a busca andar quando volta ao computador.

O dono pediu uma opção: a pessoa que tem conta no 2Captcha (serviço pago que resolve CAPTCHA) põe a chave dele no joBot, liga um interruptor, e o joBot usa o serviço quando um desafio aparecer. O pedido ficou em `duvidas.md` (D124), com a decisão da sessão para o dono confirmar.

Três fatos pesaram:

- A fase 1 não tem navegador. Só a fase 2 abre o Chrome visível pelo Playwright (ADR 0017).
- O token que o 2Captcha devolve não basta sozinho para passar pela tela "Just a moment" do Cloudflare num cliente HTTP: a documentação do serviço só descreve o uso dentro de um navegador.
- As fontes públicas (ADR 0004) são mantidas pela comunidade e seguem uma regra simples e educada: se a fonte mostra CAPTCHA, ela não quer robô, e o joBot para.

## Decisão

### Onde vale

- O 2Captcha só age na navegação com login da fase 2 (Chrome visível, perfil do joBot, ADR 0005).
- Fontes públicas seguem a [0004](0004-fontes-publicas.md) sem mudança: CAPTCHA, 401, 403 ou bloqueio é "a fonte falhou".
- Nenhum outro serviço de CAPTCHA entra. Tipos aceitos: reCAPTCHA v2 (inclusive invisível), reCAPTCHA v3 e Cloudflare Turnstile, pelas tarefas sem proxy da API do 2Captcha. hCaptcha fica fora, porque a documentação pública não o traz.

### Quando age

- Só com a chave salva e o interruptor ligado. O interruptor nasce desligado e fica travado enquanto não houver chave.
- Uma tentativa por página por rodada, com tempo-limite total de 180 segundos.
- No máximo 30 resoluções por dia (valor fixo no código, não é configuração).
- Falha, tempo esgotado, saldo zero ou chave errada: volta ao comportamento da [0005](0005-sites-com-login.md) (aviso vermelho e janela parada para a pessoa resolver).

### O que vai ao serviço

- O endereço da página, a `sitekey` (código público do desafio) e o user agent do navegador, mais a chave da pessoa.
- Nenhum dado pessoal, nenhum cookie e nenhum conteúdo de vaga.
- A chave fica no cofre de senhas do sistema (ADR 0014) e nunca aparece no painel, no log, em mensagem de erro ou em teste. Cada resolução vai para o `jobot.log` com o custo, sem a chave.

### Aviso à pessoa

O painel diz com franqueza, ao lado do interruptor:

- vale só para a navegação com login, que chega numa versão futura;
- resolver CAPTCHA pode ir contra os termos de alguns sites, e a conta pode ser restringida;
- cada resolução custa dinheiro da conta da pessoa no 2Captcha;
- o que vai ao serviço (acima).

### O que muda nas ADRs anteriores

- A [0005](0005-sites-com-login.md) troca "o joBot nunca tenta contornar CAPTCHA" por: o joBot só resolve CAPTCHA pelo serviço da pessoa, se ela pôs a chave e ligou; sem isso, não tenta.
- A [0014](0014-seguranca-e-privacidade.md) troca "nunca contorna CAPTCHA" pelo mesmo texto, e passa a listar o 2Captcha entre os serviços que a pessoa liga.
- A [0004](0004-fontes-publicas.md) não muda.
- Continua valendo: o joBot nunca digita senha, só lê e não muda nada na conta.

### Desenho

O desenho completo (parte do 2Captcha e a parte da IA pela sessão, que fica registrada para a fase 3) está em `docs/superpowers/specs/2026-11-15-captcha-design.md`.

## Consequências

- Quem quer o recurso tem de criar conta no 2Captcha, pôr saldo e guardar a chave aqui. Quem não quer não vê nenhuma mudança: o padrão é desligado.
- O joBot passa a falar com um serviço de terceiro, só quando a pessoa liga. A lista de pedidos de rede dos textos de privacidade (README em português e inglês e a tela de Configurações, Privacidade) ganha o 2Captcha na mesma entrega do código.
- Risco que fica com a pessoa: o site pode restringir a conta, e o gasto sai do saldo dela. Por isso o teto de 30 por dia e o log de cada resolução.
- A regra "nunca contorna CAPTCHA" continua valendo nas fontes públicas, no `README.md`, na wiki e no `CLAUDE.md` do projeto. Esses textos mudam junto com o código da fase 2, não antes.
- Antes de construir, o dono confirma esta decisão (D124). Se não confirmar, a 0005 e a 0014 voltam ao texto anterior.
- Desfazer: tirar a aba e o cliente da API e apagar a chave do cofre.

## Ver também

- [0004. Fontes públicas de vagas e coleta educada](0004-fontes-publicas.md)
- [0005. Sites que exigem login](0005-sites-com-login.md)
- [0009. Inteligência artificial: opções, modelos e pacote offline](0009-ia-backends-e-modelos.md)
- [0014. Segurança e privacidade](0014-seguranca-e-privacidade.md)
- [0017. Fases do projeto](0017-fases.md)
