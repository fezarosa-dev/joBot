-- Quando a pessoa abriu a candidatura de cada vaga pelo painel (D147.15): uma linha por vaga, atualizada no lugar.
CREATE TABLE candidatura (
  vaga_id   INTEGER PRIMARY KEY REFERENCES vaga(id),
  abriu_em  TEXT NOT NULL,
  perguntar INTEGER NOT NULL DEFAULT 1 CHECK (perguntar IN (0, 1))
);
CREATE TRIGGER candidatura_sem_delete BEFORE DELETE ON candidatura
BEGIN SELECT RAISE(ABORT, 'candidatura não é apagada'); END;
