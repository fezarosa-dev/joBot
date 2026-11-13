# 0007. Tratamento das vagas: duplicadas, ciclo de vida, salário e rótulos

- **Status:** aceita
- **Data:** 2026-11-13

## Contexto

A mesma vaga aparece em vários sites e cidades, salários vêm em formatos diferentes e vagas fecham sem aviso. Sem tratar isso, o painel mostra lixo repetido e dados enganosos.

## Decisão

### Duplicadas e ciclo de vida

- Remoção de duplicadas pelo hash (uma "impressão digital" do texto) da URL sem parâmetros de rastreamento; a mesma vaga em várias cidades vira uma linha só.
- A vaga fecha quando some da fonte. Se a fonte estava "parcial", só fecha depois de 30 dias sumida.
- Vaga com prazo vencido sai das listas.

### Enriquecimento e salário

- Enriquecimento: busca detalhes na página da vaga, com cache de 30 dias e limite por execução.
- Leitor de salário: separa salário de benefícios, confere o período (por hora, mês ou ano) e se o valor é plausível. Tem um arquivo YAML de casos de regressão (casos que garantem que um erro corrigido não volte).
- Requisitos de estágio extraídos por expressões regulares.

### Rótulos e encaixe

- Rótulos: área, nível, modalidade (presencial, híbrido, remoto), região/UF e tipo de contrato; avisos como "exige visto" ou "exige doutorado".
- Encaixe com o perfil em três níveis (● bom, ◐ médio, ○ fraco), sempre com os motivos; habilidades que a pessoa tem (✓) e que faltam, por vaga.
- Vagas ocultas por regra podem voltar; o painel mostra quantas foram ocultas por cada motivo.

### Onde ficam as regras e como medir

- As regras ficam em arquivos de dados lidos pelo Python (versão local) e pelo JavaScript (versão Pages), com os mesmos casos de teste nos dois.
- Conjunto de ouro: cerca de 300 vagas reais rotuladas por nós; a pessoa confere uma amostra de 30 numa tela do painel (cerca de 5 minutos).
- Se algum rótulo ficar abaixo de 90% de acerto, só esse rótulo passa a usar o modelo gratuito multilingual-e5-small (cerca de 120 MB, licença MIT).

## Consequências

- Mudança de regra exige rodar os testes em Python e em JavaScript.
- A precisão dos rótulos é medida, não suposta.

## Ver também

- [0002. Duas versões, um núcleo](0002-duas-versoes-um-nucleo.md)
- [0004. Fontes públicas de vagas e coleta educada](0004-fontes-publicas.md)
- [0008. Painel e visual](0008-painel-e-visual.md)
