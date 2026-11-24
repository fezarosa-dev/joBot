-- Fase 4, 0.6.0 (desenho 8 e 9; D185.13, D226): o resto do perfil, experiências, cursos, as
-- perguntas do perfil e o preparo de candidatura de cada vaga.
-- Só colunas novas em `perfil` e tabelas novas: nenhum gatilho novo, e nada aqui toca `vaga`,
-- `evento` nem o FTS5. Sem CPF, data de nascimento e projetos; o texto do currículo nunca é
-- guardado (só serve à extração). Tudo isto é dado da pessoa: "Apagar perfil" apaga as cinco
-- tabelas, e tirar uma experiência ou um curso apaga a linha.

-- Colunas novas da linha única. Listas em JSON; vazio = NULL.
ALTER TABLE perfil ADD COLUMN nome TEXT;
ALTER TABLE perfil ADD COLUMN email TEXT;
ALTER TABLE perfil ADD COLUMN telefone TEXT;
ALTER TABLE perfil ADD COLUMN cidade_moradia TEXT;
ALTER TABLE perfil ADD COLUMN cargo_atual TEXT;
ALTER TABLE perfil ADD COLUMN anos_de_experiencia INTEGER
  CHECK (anos_de_experiencia IS NULL OR anos_de_experiencia BETWEEN 0 AND 60);
ALTER TABLE perfil ADD COLUMN formacao_nivel TEXT CHECK (formacao_nivel IS NULL OR formacao_nivel
  IN ('medio', 'tecnico', 'graduacao', 'pos_graduacao', 'mestrado', 'doutorado'));
ALTER TABLE perfil ADD COLUMN resumo TEXT;
ALTER TABLE perfil ADD COLUMN idiomas_falados TEXT;  -- JSON: lista de [idioma, nível]
ALTER TABLE perfil ADD COLUMN links TEXT;            -- JSON: lista de textos

-- Uma linha por experiência (A5). Sem chave para `perfil`: "Apagar perfil" apaga as duas juntas.
CREATE TABLE experiencia (
  id        INTEGER PRIMARY KEY,
  cargo     TEXT NOT NULL CHECK (cargo <> ''),
  empresa   TEXT,
  inicio    TEXT,                -- AAAA-MM
  fim       TEXT,                -- AAAA-MM; NULL = o emprego de hoje
  descricao TEXT
);

-- Uma linha por curso (A7) ou curso avulso.
CREATE TABLE curso (
  id          INTEGER PRIMARY KEY,
  nome        TEXT NOT NULL CHECK (nome <> ''),
  instituicao TEXT,
  situacao    TEXT CHECK (situacao IS NULL OR situacao IN ('concluido', 'cursando', 'trancado')),
  previsao    TEXT               -- AAAA-MM: fim ou previsão de formatura
);

-- Perguntas do perfil: as base sem coluna própria e as de lacuna da IA. A `chave` é única para a
-- mesma pergunta voltar à mesma linha (`ON CONFLICT DO UPDATE`) sem perder a resposta.
CREATE TABLE pergunta_perfil (
  id            INTEGER PRIMARY KEY,
  chave         TEXT NOT NULL UNIQUE,
  pergunta      TEXT NOT NULL,
  por_que       TEXT,
  resposta      TEXT,            -- NULL = ainda sem resposta
  origem        TEXT NOT NULL CHECK (origem IN ('base', 'ia')),
  criada_em     TEXT NOT NULL,
  respondida_em TEXT
);

-- O último preparo de candidatura de cada vaga (desenho 9): refazer substitui a linha. Só o acerto
-- grava; a falha não mexe no preparo anterior. Listas em JSON.
CREATE TABLE preparo_candidatura (
  vaga_id   INTEGER PRIMARY KEY REFERENCES vaga(id),
  idioma    TEXT NOT NULL,
  carta     TEXT NOT NULL,
  resumo    TEXT NOT NULL,
  tem       TEXT NOT NULL,       -- do código (desenho 5.5)
  faltam    TEXT NOT NULL,       -- do código (desenho 5.5)
  perguntar TEXT NOT NULL,       -- as perguntas que a IA sugeriu, já conferidas
  usou      TEXT NOT NULL,       -- as chaves do perfil que a IA disse ter usado
  backend   TEXT NOT NULL,
  modelo    TEXT NOT NULL,
  versao    INTEGER NOT NULL,    -- VERSAO da tarefa `candidatura`
  feito_em  TEXT NOT NULL        -- ISO com fuso, do relógio injetado
);
