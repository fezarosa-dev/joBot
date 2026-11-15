-- Por que a execução parou antes do fim (T153, D106); nulo na que não parou e nas antigas.
-- fechado: o joBot foi fechado (cancelamento, Ctrl+C); sem_batimento: o processo morreu (achada
-- na subida pelo batimento velho); banco: erro do SQLite; erro: qualquer outra exceção.
ALTER TABLE execucao ADD COLUMN parada TEXT
  CHECK (parada IS NULL OR parada IN ('fechado','sem_batimento','banco','erro'));
