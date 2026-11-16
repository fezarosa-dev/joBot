-- Dados do progresso da busca (T246, desenho 5.9, E2): o painel só lê e mostra.
-- Só tabelas novas: nenhuma tabela de hoje muda, e nenhum gatilho (evento, vaga, FTS5) as toca.
-- Nada é apagado: as linhas ficam depois de `fim`; o CASCADE só vale se uma execução sumir.
CREATE TABLE andamento (
  execucao_id     INTEGER PRIMARY KEY REFERENCES execucao(id) ON DELETE CASCADE,
  etapas          TEXT NOT NULL,   -- JSON: as etapas que rodam, fixadas no começo
  etapa           TEXT NOT NULL CHECK (etapa IN
                    ('preparando','coleta','detalhes','regras','cotacoes','encaixe','fim')),
  feitas          INTEGER,
  total           INTEGER,
  total_planejado INTEGER,
  partida         REAL NOT NULL DEFAULT 0,
  mudou_em        TEXT NOT NULL
);
CREATE TABLE andamento_fonte (
  execucao_id   INTEGER NOT NULL REFERENCES execucao(id) ON DELETE CASCADE,
  fonte         TEXT NOT NULL REFERENCES fonte(chave),
  estado        TEXT NOT NULL CHECK (estado IN ('fila','lendo','pronto','falhou','esperando')),
  feitas        INTEGER NOT NULL DEFAULT 0,
  total         INTEGER NOT NULL,
  espera_ate    TEXT,
  espera_motivo TEXT CHECK (espera_motivo IS NULL OR espera_motivo IN ('limite','erro')),
  PRIMARY KEY (execucao_id, fonte)
);
