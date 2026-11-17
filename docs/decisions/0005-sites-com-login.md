# 0005. Sites que exigem login

- **Status:** aceita
- **Data:** 2026-11-13
- **Atualizada:** 2026-11-15 (CAPTCHA pode ser resolvido pelo serviço que a pessoa liga; ver [0022](0022-captcha-pelo-servico-da-pessoa.md); o login acontece numa janela comum e a ordem de mapeamento mudou, ver a nota abaixo)

## Contexto

LinkedIn, Indeed e outros só mostram vagas completas para quem está logado. Automatizar o acesso é arriscado e pode ir contra os termos de uso desses sites.

## Decisão

### Quais sites e em que ordem

- Primeiro LinkedIn, Indeed, Catho e Vagas.com; depois, um de cada vez: InfoJobs, Glassdoor, Programathor, GeekHunter, Remotar, Trampos, Revelo e Coodesh.
- Ordem de mapeamento na fase 2: Gupy → LinkedIn → Vagas.com → Catho → Indeed → os demais.
- Cada site tem chave liga/desliga e um botão "faça login agora".

### Como acessar

- Chrome visível controlado pelo Playwright, com perfil próprio e persistente do joBot.
- A pessoa faz o login com as próprias mãos; o joBot nunca digita senha.
- Só leitura: o joBot não clica em "candidatar", não envia mensagem e não muda nada na conta.
- Ritmo lento e poucas visitas: duas vezes por dia por padrão (9h e 18h, ajustável), para reduzir o risco de o site restringir a conta.

### CAPTCHA

- Aviso vermelho no painel e aviso no computador.
- A janela fica parada na página bloqueada para a pessoa resolver; as outras fontes continuam.
- Sem chave de serviço de CAPTCHA ligada, o joBot não tenta contornar CAPTCHA. Foi a regra original desta decisão e continua valendo para as fontes públicas ([0004](0004-fontes-publicas.md)).
- Com a chave do 2Captcha salva e o interruptor ligado (decisão de 2026-11-15, ver [0022](0022-captcha-pelo-servico-da-pessoa.md)), o joBot manda o desafio ao serviço e segue com o token que voltar. Se o serviço falhar, acabar o saldo ou passar de 180 segundos, vale o aviso e a janela parada acima.

### Mapeamento de cada site

- Feito no navegador do próprio joBot, com a pessoa logada.
- Captura do HTML e das respostas JSON da rede; dados pessoais removidos das fixtures (amostras de teste).
- Testes offline com TDD.

## Nota de 2026-11-15: janela comum e nova ordem (D136)

- O login passa a acontecer numa janela comum do navegador, sem automação: o joBot só abre o navegador no endereço de login, a pessoa entra como quiser (Google, e-mail e senha) e fecha a janela, e o joBot confere a sessão sozinho. Isto vale no lugar de "Chrome visível controlado pelo Playwright" na seção "Como acessar" para o login; a leitura das vagas segue como está. O joBot continua sem digitar senha.
- A ordem de mapeamento passa a ser LinkedIn, Gupy, Vagas.com, Catho, Indeed, com os sites só de tecnologia por último. Isto troca a ordem "Gupy → LinkedIn → ..." de "Quais sites e em que ordem".
- A regra de não disfarçar a automação não vem desta ADR (que trata de senha e CAPTCHA): vem do desenho da fase 2, seção 2 (`docs/superpowers/specs/2026-11-15-fase-2-design.md:45`), e da D132.15.

## Consequências

- Mesmo com cuidado existe risco de restrição de conta; a pessoa decide se liga cada site.
- Sem o login manual feito, o site fica parado e o painel avisa.

## Ver também

- [0004. Fontes públicas de vagas e coleta educada](0004-fontes-publicas.md)
- [0006. Agenda das buscas e segundo plano](0006-agenda-e-segundo-plano.md)
- [0014. Segurança e privacidade](0014-seguranca-e-privacidade.md)
- [0022. CAPTCHA resolvido pelo serviço que a pessoa liga](0022-captcha-pelo-servico-da-pessoa.md)
