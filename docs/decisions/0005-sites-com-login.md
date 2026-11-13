# 0005. Sites que exigem login

- **Status:** aceita
- **Data:** 2026-11-13

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
- O joBot nunca tenta contornar CAPTCHA.

### Mapeamento de cada site

- Feito no navegador do próprio joBot, com a pessoa logada.
- Captura do HTML e das respostas JSON da rede; dados pessoais removidos das fixtures (amostras de teste).
- Testes offline com TDD.

## Consequências

- Mesmo com cuidado existe risco de restrição de conta; a pessoa decide se liga cada site.
- Sem o login manual feito, o site fica parado e o painel avisa.

## Ver também

- [0004. Fontes públicas de vagas e coleta educada](0004-fontes-publicas.md)
- [0006. Agenda das buscas e segundo plano](0006-agenda-e-segundo-plano.md)
- [0014. Segurança e privacidade](0014-seguranca-e-privacidade.md)
