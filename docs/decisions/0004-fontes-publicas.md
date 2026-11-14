# 0004. Fontes públicas de vagas e coleta educada

- **Status:** aceita
- **Data:** 2026-11-13
- **Atualizada:** 2026-11-13

## Contexto

Muitas vagas estão em fontes abertas, sem login: APIs públicas (endereços que entregam dados para programas), quadros de vagas de empresas e repositórios no GitHub. É preciso decidir quais fontes entram e como coletar sem incomodar os sites.

## Decisão

### Fontes

- Cada fonte tem uma chave liga/desliga.
- Repositórios de vagas em issues do GitHub: backend-br, frontendbr, soujava, remotejobsbr e developersRJ.
- Sites e APIs internacionais: Jobicy, Hacker News "Who is hiring" (via Algolia), Remotive, RemoteOK, Himalayas e We Work Remotely.
- Quadros de vagas de sistemas de recrutamento (ATS): Greenhouse, Lever, Ashby, SmartRecruiters, Workday, Eightfold, Oracle HCM, InHire, Quickin e Recrutei.
- Portais brasileiros: Gupy, CIEE, Sólides, IEL, Super Estágios, Cia de Talentos, Eureca e Abler.
- Sites de carreira de grandes empresas: Google, Amazon, Microsoft e NVIDIA.
- Murais públicos de estágio, como o da USP.

### Termos de uso

Decisão do dono, em 2026-11-13:

- A Meta fica fora. Os termos dela proíbem coleta automática sem permissão por escrito.
- Eureca, Abler e Gupy entram, mesmo com termos restritivos. Cada uma tem chave liga/desliga, ritmo educado, link para a vaga original e aviso no README.
- O README avisa que o joBot é de uso pessoal e que cada pessoa responde pelos termos das fontes que deixar ligadas.

### Lista de empresas

- Lista própria, feita só de fatos públicos (nome da empresa e identificador do quadro de vagas), cada um conferido no endereço ao vivo e guardado no nosso formato.
- Descoberta semanal de novos quadros de vagas pelo Common Crawl (pode desligar).
- Acompanhar mudanças em páginas de programas (por exemplo, trainee e escola de verão), dentro da função "adicionar site".

### Coleta educada

- O robots.txt (arquivo em que o site diz o que robôs podem acessar) não bloqueia a coleta. Foi decisão do dono, em 2026-11-13.
- A coleta continua educada: identificação clara do robô (user agent), intervalo entre pedidos, espera maior quando o site responde 429 (pedidos demais) e limites documentados.
- Nunca contorna login, CAPTCHA ou bloqueio anti-robô.
- Sete fontes têm intervalo mínimo entre uma busca e outra:
  - porque os termos ou os limites pedem: Remotive (360 minutos), Jobicy (60) e We Work Remotely (60);
  - por escolha prática da sessão, em 2026-11-13, sem exigência dos termos: Google (1440; o feed é grande e muda uma vez por dia), Himalayas (1440; os dados mudam uma vez por dia), RemoteOK (360) e Amazon (360).
- O botão "buscar agora" também respeita esse intervalo.
- Saúde de cada fonte a cada execução: ok, sem mudança (304), parcial, falhou, no limite ou desligada. A falha de uma fonte nunca para as outras.
- Todo endereço (por exemplo, o JSON público da Gupy) é confirmado com uma captura nossa antes de virar coletor. Os testes usam só fixtures (amostras de dados de teste) feitas por nós.

### Atribuição

- Fontes cujos termos pedem crédito e link de volta (Remotive, RemoteOK, Jobicy, Himalayas e We Work Remotely) mostram "via <fonte>" com link para a vaga original.
- Na Himalayas, o botão de candidatura usa o link deles.

## Consequências

- A lista de fontes cresce sem mexer no núcleo: cada coletor entrega vagas no mesmo formato.
- Fonte que só lista endereços (sitemap: Abler e Super Estágios) entrega a lista de URLs com a data. A vaga só é gravada depois que a página de detalhe traz título e empresa, dentro do limite de enriquecimento (decisão de 2026-11-13; desenho da fase 1, DR-70).

## Pontos em aberto

- Endereços das levas A e B conferidos ao vivo em 2026-11-13 (apêndice do desenho da fase 1).
- Fontes cujos termos restringem a coleta: decidido pelo dono em 2026-11-13 (ver "Termos de uso"). Não está mais em aberto.
- Caminho público da Eureca: ainda a conferir numa captura nossa. Sem caminho público, ela fica fora.

## Ver também

- [0005. Sites que exigem login](0005-sites-com-login.md)
- [0006. Agenda das buscas e segundo plano](0006-agenda-e-segundo-plano.md)
- [0007. Tratamento das vagas: duplicadas, ciclo de vida, salário e rótulos](0007-tratamento-dos-dados.md)
- [0016. Licença, sala limpa e processo de trabalho](0016-licenca-clean-room-e-processo.md)
