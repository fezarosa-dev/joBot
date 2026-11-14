# Padrões e armadilhas do joBot

Lições que as revisões acharam. Leia antes de começar uma tarefa. Uma linha por lição.

- Toda tarefa que mexe em esquema lista os gatilhos de banco de forma explícita (os de `evento` e o `BEFORE DELETE` de `vaga`), não só as tabelas.
- `INSERT OR REPLACE`, `REPLACE` e `DROP TABLE` apagam a linha sem disparar o gatilho de `DELETE`, mas as cascatas rodam: grave com `INSERT ... ON CONFLICT DO UPDATE` e, na migração, desligue `foreign_keys` antes do `BEGIN`.
- `vaga_fts` e os gatilhos dela só existem quando `tem_fts5(con)` é verdadeiro; código e teste não podem supor FTS5.
- Toda grandeza de dinheiro diz a unidade no nome ou no tipo: `Salario` em centavos da moeda original; reais inteiros só nas colunas `_brl` do banco.
- Flags de comportamento (ex.: `para_no_429`) atravessam todas as camadas, de `fontes.json` até o `HttpDoEscopo`; teste a ponta e o meio.
- Sitemap: a janela de 30 dias filtra só URL nova; URL já conhecida conta como vista.
- Decisão do plano (DP) não contradiz decisão do redator (DR); havendo conflito, vale o desenho e o caso vai para `duvidas`.
- Arquivos compartilhados (`registro.py`, `fontes.json`, i18n `comum.json`) são fechados antes da onda; coletor não mexe neles.
- Toda condição do dono vira critério de aceite com teste.
