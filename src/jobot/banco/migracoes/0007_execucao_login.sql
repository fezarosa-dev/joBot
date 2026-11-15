-- Tipo de execução 'login' (T201, D132.6, D132.47): a leitura com login da fase 2.
-- O SQLite não muda um CHECK no lugar: a tabela é refeita com as mesmas colunas e o mesmo índice.
-- O migrar desliga foreign_keys antes do BEGIN, então o DROP não apaga saude nem execucao_fonte,
-- e as chaves delas seguem apontando para 'execucao' depois do RENAME. execucao não tem gatilho.
CREATE TABLE execucao_nova (
  id            INTEGER PRIMARY KEY,
  tipo          TEXT NOT NULL CHECK (tipo IN ('busca','descoberta','paginas','login')),
  motivo        TEXT NOT NULL CHECK (motivo IN ('agenda','agora','recuperacao')),
  iniciada_em   TEXT NOT NULL,
  batimento_em  TEXT NOT NULL,                     -- atualizado a cada 30 s
  terminada_em  TEXT,
  estado        TEXT NOT NULL CHECK (estado IN ('rodando','concluida','interrompida')),
  parada        TEXT
    CHECK (parada IS NULL OR parada IN ('fechado','sem_batimento','banco','erro'))
);
INSERT INTO execucao_nova (id, tipo, motivo, iniciada_em, batimento_em, terminada_em, estado, parada)
  SELECT id, tipo, motivo, iniciada_em, batimento_em, terminada_em, estado, parada FROM execucao;
DROP TABLE execucao;
ALTER TABLE execucao_nova RENAME TO execucao;
-- no máximo uma execução rodando de cada tipo, garantido pelo próprio banco.
CREATE UNIQUE INDEX execucao_uma_por_tipo ON execucao(tipo) WHERE estado = 'rodando';
