# 0007. Tratamento das vagas: duplicadas, ciclo de vida, salário e rótulos

- **Status:** aceita
- **Data:** 2026-11-13
- **Atualizada:** 2026-11-13

## Contexto

A mesma vaga aparece em vários sites e cidades, salários vêm em formatos diferentes e vagas fecham sem aviso. Sem tratar isso, o painel mostra lixo repetido e dados enganosos.

## Decisão

### Duplicadas e ciclo de vida

- Remoção de duplicadas pelo hash (uma "impressão digital" do texto) da URL sem parâmetros de rastreamento; a mesma vaga em várias cidades vira uma linha só quando a fonte usa a mesma URL; a mesma vaga com URLs diferentes fica em linhas separadas, e a pessoa pode ocultar as repetidas.
- A vaga fecha quando some da fonte. Se a fonte estava "parcial", só fecha depois de 30 dias sumida.
- Vaga com prazo vencido sai das listas.
- Nenhuma vaga é apagada, nem fechada nem antiga. O ciclo de vida marca; não apaga.

### O que fica guardado para a fase 6

Decisão de 2026-11-13. A fase 6 treina modelos (ADR 0015) e precisa destes dados desde o primeiro dia:

- O texto completo de toda vaga: o texto puro e o HTML bruto da descrição, quando houver.
- O histórico das ações da pessoa no painel (salvou, descartou, ocultou, mudou de status, desfez), com data. Fica numa tabela de eventos só de acréscimo: nada nela é alterado nem apagado.
- Na fase 1, descartar é ocultar a vaga à mão: o painel não tem botão de descartar separado. O histórico também registra o "mostrar mesmo assim" de uma vaga oculta por regra.
- O histórico é dado pessoal e fica só no computador da pessoa.

### Enriquecimento e salário

- Enriquecimento: busca detalhes na página da vaga, com cache de 30 dias e limite por execução.
- Leitor de salário: separa salário de benefícios, confere o período (por hora, mês ou ano) e se o valor é plausível. Tem um arquivo de casos de regressão em JSON (casos que garantem que um erro corrigido não volte).
- Salário em moeda estrangeira: convertido para reais pela cotação PTAX do Banco Central (uma consulta por dia), quando houver cotação.
- O filtro de salário mínimo usa o valor convertido. Sem cotação, a vaga não é eliminada pelo filtro.
- Na tela, ao lado do valor original, em letra menor e cor mais apagada, aparecem a cotação do dia e o valor em reais.
- Requisitos de estágio extraídos por expressões regulares.

### Rótulos e encaixe

- Rótulos: área, nível, modalidade (presencial, híbrido, remoto), região/UF e tipo de contrato; avisos como "exige visto" ou "exige doutorado".
- Encaixe com o perfil em três níveis (● bom, ◐ médio, ○ fraco), sempre com os motivos; habilidades que a pessoa tem (✓) e que faltam, por vaga.
- Vagas ocultas por regra podem voltar; o painel mostra quantas foram ocultas por cada motivo.

### Onde ficam as regras e como medir

- As regras ficam em arquivos de dados lidos pelo Python (versão local) e pelo JavaScript (versão Pages).
- Os casos de teste das regras ficam em JSON desde a fase 1. O teste em JavaScript chega com a versão Pages (fase 7).
- Conjunto de ouro (gabarito): 329 vagas reais, de 30 fontes, já coletadas em 2026-11-13.
- Rotulagem do gabarito em duas passadas: agentes do modelo Sonnet rotulam; o modelo Fable rotula de novo, às cegas (sem ver a primeira resposta). Onde discordam, o Fable decide e registra o porquê. O dono não confere amostra do gabarito.
- O gabarito fica só no computador de quem desenvolve, fora do repositório. O comando que mede recebe o caminho dele. No repositório vão só as regras e os números medidos.
- O gabarito nunca entra em dados de treino.
- O painel da fase 1 não tem tela para conferir rótulos. Ela existia para o dono avaliar as regras; em 2026-11-13 o dono trocou essa avaliação pelo gabarito rotulado por modelos, e a tela saiu.
- A fase 1 mede e registra o acerto de cada rótulo.
- Se algum rótulo ficar abaixo de 90% de acerto, só esse rótulo passa a usar o modelo gratuito multilingual-e5-small (cerca de 120 MB, licença MIT). Isso fica para a fase 3, junto com a IA local.

## Consequências

- Mudança de regra exige rodar os testes em Python e, a partir da fase 7, também em JavaScript.
- A precisão dos rótulos é medida, não suposta.
- O banco cresce com o tempo, porque nenhuma vaga é apagada.

## Ver também

- [0002. Duas versões, um núcleo](0002-duas-versoes-um-nucleo.md)
- [0004. Fontes públicas de vagas e coleta educada](0004-fontes-publicas.md)
- [0008. Painel e visual](0008-painel-e-visual.md)
- [0015. Treino de modelos (fase 6)](0015-treino.md)
