# 0004. Fontes públicas de vagas e coleta educada

- **Status:** aceita
- **Data:** 2026-11-13

## Contexto

Muitas vagas estão em fontes abertas, sem login: APIs públicas (endereços que entregam dados para programas), quadros de vagas de empresas e repositórios no GitHub. É preciso decidir quais fontes entram e como coletar sem incomodar os sites.

## Decisão

### Fontes

- Cada fonte tem uma chave liga/desliga.
- Repositórios de vagas em issues do GitHub: backend-br, frontendbr, soujava, remotejobsbr e developersRJ.
- Sites e APIs internacionais: Jobicy, Hacker News "Who is hiring" (via Algolia), Remotive, RemoteOK, Himalayas e We Work Remotely.
- Quadros de vagas de sistemas de recrutamento (ATS): Greenhouse, Lever, Ashby, SmartRecruiters, Workday, Eightfold, Oracle HCM, InHire, Quickin e Recrutei.
- Portais brasileiros: Gupy, CIEE, Sólides, IEL, Super Estágios, Cia de Talentos, Eureca e Abler.
- Sites de carreira de grandes empresas: Google, Amazon, Microsoft, NVIDIA e Meta.
- Murais públicos de estágio, como o da USP.

### Lista de empresas

- Lista própria, feita só de fatos públicos (nome da empresa e identificador do quadro de vagas), cada um conferido no endereço ao vivo e guardado no nosso formato.
- Descoberta semanal de novos quadros de vagas pelo Common Crawl (pode desligar).
- Acompanhar mudanças em páginas de programas (por exemplo, trainee e escola de verão), dentro da função "adicionar site".

### Coleta educada

- Identificação clara do robô (user agent), intervalo entre pedidos e espera maior quando o site responde 429 (pedidos demais).
- Saúde de cada fonte a cada execução: ok, parcial ou falhou. A falha de uma fonte nunca para as outras.
- Todo endereço (por exemplo, o JSON público da Gupy) é confirmado com uma captura nossa antes de virar coletor. Os testes usam só fixtures (amostras de dados de teste) feitas por nós.

## Consequências

- A lista de fontes cresce sem mexer no núcleo: cada coletor entrega vagas no mesmo formato.

## Pontos em aberto

- Confirmar cada endereço público com captura própria, começando pela Gupy.

## Ver também

- [0005. Sites que exigem login](0005-sites-com-login.md)
- [0006. Agenda das buscas e segundo plano](0006-agenda-e-segundo-plano.md)
- [0007. Tratamento das vagas: duplicadas, ciclo de vida, salário e rótulos](0007-tratamento-dos-dados.md)
- [0016. Licença, sala limpa e processo de trabalho](0016-licenca-clean-room-e-processo.md)
