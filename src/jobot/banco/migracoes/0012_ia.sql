-- Fase 4, 0.5.0 (desenho 5.4, 5.5 e 8; D185.12, D185.13 e D188): perfil mínimo, o que cada vaga
-- pede segundo a IA e o nível do encaixe sem o critério de habilidades.
-- Só tabelas novas e uma coluna em `encaixe`: nenhum gatilho novo, e gravar `habilidades_vaga`
-- não toca `vaga`, `evento` nem o FTS5.

-- Uma linha só. "Apagar perfil" apaga a linha: é dado da pessoa, não vaga.
CREATE TABLE perfil (
  id            INTEGER PRIMARY KEY CHECK (id = 1),
  habilidades   TEXT NOT NULL,     -- JSON: lista de textos
  atualizado_em TEXT NOT NULL      -- ISO com fuso, do relógio injetado
);

-- Uma linha por vaga, atualizada no lugar. Falha nunca apaga o `pede` anterior.
CREATE TABLE habilidades_vaga (
  vaga_id       INTEGER PRIMARY KEY REFERENCES vaga(id),
  chave         TEXT,              -- hash do texto enviado + VERSAO + backend + modelo do `pede`
  pede          TEXT,              -- JSON: lista do que a vaga pede, já conferida; NULL = nunca deu certo
  backend       TEXT,              -- de onde veio o `pede`
  modelo        TEXT,
  versao        INTEGER,           -- VERSAO da tarefa `encaixe`
  feito_em      TEXT,              -- hora do `pede`, ISO com fuso
  falha         TEXT CHECK (falha IS NULL OR falha IN ('recusa','formato','contexto')),
  falha_em      TEXT,
  falha_chave   TEXT,              -- a chave que falhou: `tentativas` conta as falhas com ela
  falha_backend TEXT,              -- o backend da falha, para a contagem do dia (D188)
  tentativas    INTEGER NOT NULL DEFAULT 0 CHECK (tentativas >= 0)
);

-- O nível sem o critério de habilidades: a fila do laço lê este (desenho 5.4). Até hoje não há
-- esse critério, então o nível sem ele é o próprio nível (D188). `encaixe` não tem gatilho.
ALTER TABLE encaixe ADD COLUMN nivel_base TEXT CHECK (nivel_base IN ('bom','medio','fraco'));
UPDATE encaixe SET nivel_base = nivel;
