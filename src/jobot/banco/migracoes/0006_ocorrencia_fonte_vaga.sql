-- Índice do chip de fonte (T192, D129 item 3). Só um índice: nenhuma tabela, gatilho nem FTS5 muda.
-- Cobre `JOIN ocorrencia o ON o.vaga_id = v.id` agrupado por `o.fonte`: a consulta lê só o índice.
-- Com 300 mil vagas o chip cai de 2,2 s para 0,46 s.
CREATE INDEX ocorrencia_fonte_vaga ON ocorrencia(fonte, vaga_id);
