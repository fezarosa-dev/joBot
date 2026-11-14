-- Quando cada fonte começou e terminou numa execução (T140): a tela de andamento lista as que ainda rodam.
CREATE TABLE execucao_fonte (
  execucao_id  INTEGER NOT NULL REFERENCES execucao(id) ON DELETE CASCADE,
  fonte        TEXT NOT NULL REFERENCES fonte(chave),
  comecou_em   TEXT NOT NULL,
  terminou_em  TEXT,
  PRIMARY KEY (execucao_id, fonte)
);
