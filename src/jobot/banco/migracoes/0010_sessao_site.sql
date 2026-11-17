-- Estado da conta de cada site com login (D139.16) e de cada conta de fora (Gmail, D145): uma linha por chave, atualizada no lugar.
-- Só tabelas novas: nenhuma tabela de hoje muda, e nenhum gatilho (evento, vaga, FTS5) as toca.
CREATE TABLE sessao_site (
  fonte        TEXT PRIMARY KEY REFERENCES fonte(chave),
  estado       TEXT NOT NULL CHECK (estado IN ('conectado','precisa_entrar','nao_conferiu')),
  motivo       TEXT CHECK (motivo IS NULL OR motivo IN (
                 'sem_rede','desafio','bloqueio','no_limite','sem_tela','sem_navegador',
                 'em_uso','erro','esquecido')),
  conferido_em TEXT NOT NULL,  -- hora da última conferência, ISO com fuso, do relógio injetado
  entrou_em    TEXT,           -- última vez visto conectado; NULL = nunca entrou
  avisado_em   TEXT            -- queda aberta: aviso já mandado ou marcado; NULL = sem queda aberta
);
CREATE TABLE sessao_conta (
  conta        TEXT PRIMARY KEY CHECK (conta IN ('gmail')),
  estado       TEXT NOT NULL CHECK (estado IN ('conectado','precisa_entrar','nao_conferiu')),
  motivo       TEXT CHECK (motivo IS NULL OR motivo IN ('sem_rede','bloqueio','erro','esquecido')),
  conferido_em TEXT NOT NULL,
  entrou_em    TEXT,
  avisado_em   TEXT
);
