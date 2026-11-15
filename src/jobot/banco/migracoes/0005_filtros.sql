-- Índices dos filtros da 0.2.0 (T162, Parte H do desenho). Só índices: nenhuma tabela, gatilho
-- nem FTS5 muda. As expressões são letra por letra as das condições de `banco/leitura.py`.
CREATE INDEX local_vaga_vaga ON local_vaga(vaga_id);
CREATE INDEX local_vaga_pais ON local_vaga(pais, vaga_id);
-- Com julianday() num índice, gravar em publicada_em ou primeira_vista_em um texto que dependa do
-- relógio do SQLite ('now', CURRENT_TIMESTAMP) falha. Grave sempre ISO vindo do relógio injetado.
CREATE INDEX vaga_publicada_ou_vista ON vaga(julianday(COALESCE(publicada_em, primeira_vista_em)));
CREATE INDEX vaga_sal_baixo_brl ON vaga(COALESCE(sal_mensal_min_brl, sal_mensal_max_brl));
CREATE INDEX vaga_sal_alto_brl ON vaga(COALESCE(sal_mensal_max_brl, sal_mensal_min_brl));
