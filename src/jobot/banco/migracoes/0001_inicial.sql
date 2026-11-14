-- Esquema inicial (desenho, seção 7.3). Migração aplicada nunca é editada: mudança nova = arquivo novo.
-- vaga_fts e os gatilhos dela ficam fora daqui: o migrar.py cria só quando há FTS5 (DR-05).

CREATE TABLE fonte (
  chave         TEXT PRIMARY KEY,                 -- 'greenhouse', 'remotive'...
  leva          TEXT NOT NULL CHECK (leva IN ('A','B')),
  ligada        INTEGER NOT NULL DEFAULT 1,
  intervalo_min INTEGER                           -- NULL = sem intervalo mínimo. Preenchido quando os termos ou os limites da fonte exigem, ou com um intervalo prático (seção 8.3)
);

CREATE TABLE empresa (
  id            INTEGER PRIMARY KEY,
  nome          TEXT NOT NULL,
  area          TEXT,
  pais          TEXT,                                    -- país da empresa, ISO 3166-1 alfa-2 (vem do empresas.json)
  fonte         TEXT NOT NULL REFERENCES fonte(chave),   -- o ATS
  identificador TEXT NOT NULL,
  parametros    TEXT NOT NULL DEFAULT '{}',              -- JSON: o que o ATS pede além do identificador (seção 8.6)
  ativa         INTEGER NOT NULL DEFAULT 1,
  removida_em   TEXT,                                    -- NULL = não removida. Remover marca a linha, não apaga (seção 8.6)
  origem        TEXT NOT NULL CHECK (origem IN ('lista_inicial','pessoa','descoberta')),
  conferida_em  TEXT,
  UNIQUE (fonte, identificador)
);

CREATE TABLE empresa_sugerida (                    -- vinda do Common Crawl
  id            INTEGER PRIMARY KEY,
  fonte         TEXT NOT NULL REFERENCES fonte(chave),
  identificador TEXT NOT NULL,
  url_exemplo   TEXT NOT NULL,
  descoberta_em TEXT NOT NULL,
  estado        TEXT NOT NULL DEFAULT 'pendente' CHECK (estado IN ('pendente','aprovada','descartada')),
  UNIQUE (fonte, identificador)
);

CREATE TABLE execucao (
  id            INTEGER PRIMARY KEY,
  tipo          TEXT NOT NULL CHECK (tipo IN ('busca','descoberta','paginas')),
  motivo        TEXT NOT NULL CHECK (motivo IN ('agenda','agora','recuperacao')),
  iniciada_em   TEXT NOT NULL,
  batimento_em  TEXT NOT NULL,                     -- atualizado a cada 30 s
  terminada_em  TEXT,
  estado        TEXT NOT NULL CHECK (estado IN ('rodando','concluida','interrompida'))
);
-- no máximo uma execução rodando de cada tipo, garantido pelo próprio banco.
-- Descoberta e páginas acompanhadas nunca seguram a busca (seção 12.3).
CREATE UNIQUE INDEX execucao_uma_por_tipo ON execucao(tipo) WHERE estado = 'rodando';

CREATE TABLE saude (
  execucao_id   INTEGER NOT NULL REFERENCES execucao(id) ON DELETE CASCADE,
  fonte         TEXT NOT NULL REFERENCES fonte(chave),
  escopo        TEXT NOT NULL DEFAULT '',
  estado        TEXT NOT NULL CHECK (estado IN ('ok','sem_mudanca','parcial','falhou','desligada','no_limite')),
  vagas         INTEGER NOT NULL DEFAULT 0,
  pedidos       INTEGER NOT NULL DEFAULT 0,
  duracao_ms    INTEGER NOT NULL DEFAULT 0,
  motivo        TEXT,                              -- chave de i18n + detalhe curto
  PRIMARY KEY (execucao_id, fonte, escopo)
);

CREATE TABLE vaga (
  id                 INTEGER PRIMARY KEY,
  url_hash           TEXT NOT NULL UNIQUE,         -- única chave de duplicata (ADR 0007)
  titulo             TEXT NOT NULL,
  empresa            TEXT NOT NULL,
  descricao_texto    TEXT NOT NULL DEFAULT '',
  url                TEXT NOT NULL,                -- URL canônica
  idioma             TEXT,
  area TEXT, nivel TEXT, modalidade TEXT, contrato TEXT,
  avisos             TEXT NOT NULL DEFAULT '[]',
  sal_moeda TEXT, sal_min INTEGER, sal_max INTEGER, sal_periodo TEXT,
  sal_mensal_min INTEGER,                          -- na moeda original
  sal_mensal_min_brl INTEGER,                      -- em reais inteiros (não centavos), para ordenar e filtrar; NULL sem cotação
  sal_mensal_max_brl INTEGER,                      -- o máximo mensal, em reais inteiros; NULL sem cotação ou sem máximo
                                                   -- vaga em BRL: os dois valem centavos ÷ 100, arredondado, sem cotação
                                                   -- e mesmo com a conversão desligada (seção 10.3)
  sal_cotacao_data TEXT,                           -- dia da cotação usada; NULL na vaga em BRL
  sal_plausivel INTEGER, sal_texto TEXT,
  beneficios         TEXT NOT NULL DEFAULT '[]',
  requisitos_estagio TEXT,
  publicada_em TEXT, prazo TEXT, inicio TEXT,
  primeira_vista_em  TEXT NOT NULL,
  ultima_vista_em    TEXT NOT NULL,
  fechada_em         TEXT,
  status             TEXT NOT NULL DEFAULT 'nova'
                     CHECK (status IN ('nova','salva','candidatei','entrevista','recusada','oferta')),
  status_em          TEXT,
  oculta_manual      INTEGER NOT NULL DEFAULT 0
                     CHECK (oculta_manual IN (-1,0,1)),  -- 0 regras, 1 à mão, -1 mostrar mesmo assim (DP2)
  versao_regras      TEXT NOT NULL
);
CREATE INDEX vaga_lista ON vaga(fechada_em, oculta_manual, status);
CREATE INDEX vaga_primeira_vista ON vaga(primeira_vista_em);
CREATE INDEX vaga_prazo ON vaga(prazo);
CREATE INDEX vaga_empresa ON vaga(empresa);
-- vaga nunca é apagada (seção 7.6)
CREATE TRIGGER vaga_sem_delete BEFORE DELETE ON vaga
BEGIN
  SELECT RAISE(ABORT, 'vaga nunca é apagada');
END;
-- gravar de novo é sempre INSERT ... ON CONFLICT(url_hash) DO UPDATE, nunca apagando e recriando a linha (DR-69)

CREATE TABLE local_vaga (
  vaga_id  INTEGER NOT NULL REFERENCES vaga(id) ON DELETE CASCADE,
  cidade TEXT, uf TEXT, pais TEXT
);
CREATE INDEX local_vaga_uf ON local_vaga(uf);

CREATE TABLE ocorrencia (                          -- cada vez que uma fonte mostra a vaga
  id               INTEGER PRIMARY KEY,
  vaga_id          INTEGER NOT NULL REFERENCES vaga(id) ON DELETE CASCADE,
  fonte            TEXT NOT NULL REFERENCES fonte(chave),
  escopo           TEXT NOT NULL DEFAULT '',
  id_externo       TEXT,
  url              TEXT NOT NULL,                  -- como a fonte mandou
  coletada         TEXT NOT NULL,                  -- VagaColetada em JSON (inclui url_candidatura), para reprocessar sem baixar de novo
  primeira_vista_em TEXT NOT NULL,
  ultima_vista_em  TEXT NOT NULL,
  sumiu_em         TEXT,
  UNIQUE (vaga_id, fonte, escopo)                  -- a mesma URL pode aparecer em mais de um escopo ou fonte
);
CREATE INDEX ocorrencia_escopo ON ocorrencia(fonte, escopo, ultima_vista_em);
CREATE INDEX ocorrencia_vaga ON ocorrencia(vaga_id);

CREATE TABLE busca (                               -- buscas salvas (ADR 0001)
  id INTEGER PRIMARY KEY,
  nome TEXT NOT NULL,
  ativa INTEGER NOT NULL DEFAULT 1,
  cargos TEXT NOT NULL DEFAULT '[]',               -- palavras-chave
  cidades TEXT NOT NULL DEFAULT '[]',              -- [{cidade, uf, pais}]
  modalidades TEXT NOT NULL DEFAULT '[]',
  niveis TEXT NOT NULL DEFAULT '[]',
  salario_min INTEGER, salario_moeda TEXT,         -- mensal, em centavos de salario_moeda
  idiomas TEXT NOT NULL DEFAULT '[]',
  regras_ocultar TEXT NOT NULL DEFAULT '{}',       -- quais regras de ocultar estão ligadas
  criada_em TEXT NOT NULL
);

CREATE TABLE encaixe (                             -- calculado por busca
  busca_id INTEGER NOT NULL REFERENCES busca(id) ON DELETE CASCADE,
  vaga_id  INTEGER NOT NULL REFERENCES vaga(id) ON DELETE CASCADE,
  nota     INTEGER,                                -- 0 a 100; NULL quando a busca não tem nenhum critério (seção 11.1)
  nivel    TEXT CHECK (nivel IN ('bom','medio','fraco')),
  motivos  TEXT NOT NULL,                          -- [{chave, params}]
  oculta_motivo TEXT,                              -- regra que escondeu; NULL se visível
  PRIMARY KEY (busca_id, vaga_id)
);
CREATE INDEX encaixe_ordem ON encaixe(busca_id, oculta_motivo, nota DESC);

CREATE TABLE correcao (                            -- "Algo errado nesta vaga?"
  id INTEGER PRIMARY KEY,
  vaga_id INTEGER NOT NULL REFERENCES vaga(id) ON DELETE CASCADE,
  campo TEXT NOT NULL,                             -- 'area','nivel','modalidade','contrato','uf','salario','fechada','outro'
  valor_antigo TEXT, valor_novo TEXT, comentario TEXT,
  criada_em TEXT NOT NULL
);

CREATE TABLE evento (                              -- histórico das ações da pessoa no painel; só de acréscimo (seção 7.6)
  id        INTEGER PRIMARY KEY,
  vaga_id   INTEGER NOT NULL REFERENCES vaga(id),  -- sem CASCADE: vaga nunca é apagada
  acao      TEXT NOT NULL CHECK (acao IN ('salvou','ocultou','mostrou','mudou_status','desfez')),
  de        TEXT,                                  -- status anterior, quando a ação mexe no status
  para      TEXT,                                  -- status novo, quando a ação mexe no status
  criado_em TEXT NOT NULL
);
-- evento só recebe acréscimo (seção 7.6)
CREATE TRIGGER evento_sem_update BEFORE UPDATE ON evento
BEGIN
  SELECT RAISE(ABORT, 'evento só recebe acréscimo');
END;
CREATE TRIGGER evento_sem_delete BEFORE DELETE ON evento
BEGIN
  SELECT RAISE(ABORT, 'evento só recebe acréscimo');
END;

CREATE TABLE cotacao (                             -- PTAX de fechamento, uma linha por moeda e dia
  moeda      TEXT NOT NULL,                        -- 'USD', 'EUR'...
  data       TEXT NOT NULL,                        -- dia do boletim
  venda      TEXT NOT NULL,                        -- reais por 1 unidade da moeda, em decimal
  buscada_em TEXT NOT NULL,
  PRIMARY KEY (moeda, data)
);

CREATE TABLE cache_http (                          -- validadores para pedido condicional (seção 8.2)
  url           TEXT PRIMARY KEY,
  etag          TEXT,
  last_modified TEXT,
  visto_em      TEXT NOT NULL
);

CREATE TABLE enriquecimento (                      -- cache de 30 dias
  url_hash TEXT PRIMARY KEY,
  buscado_em TEXT NOT NULL,
  conteudo TEXT NOT NULL                           -- vazio quando o detalhe não trouxe título ou empresa (DR-70)
);

CREATE TABLE pagina_acompanhada (
  id INTEGER PRIMARY KEY,
  url TEXT NOT NULL UNIQUE,
  nome TEXT NOT NULL,
  ativa INTEGER NOT NULL DEFAULT 1,
  texto TEXT, hash_texto TEXT,
  verificada_em TEXT, mudou_em TEXT,
  estado TEXT                                      -- ok, falhou
);
CREATE TABLE mudanca_pagina (
  id INTEGER PRIMARY KEY,
  pagina_id INTEGER NOT NULL REFERENCES pagina_acompanhada(id) ON DELETE CASCADE,
  detectada_em TEXT NOT NULL,
  diferenca TEXT NOT NULL,                         -- saída do difflib
  vista INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE config (chave TEXT PRIMARY KEY, valor TEXT NOT NULL);   -- valor em JSON
