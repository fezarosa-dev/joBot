-- Fase 4, 0.6.0 (D234, decidido pelo dono em 2026-11-24): a pergunta que a IA sugere ao preparar
-- uma candidatura espera o aceite da pessoa antes de entrar no perfil. `sugerida = 1`: fica fora
-- do questionário e de todo pedido à IA até "Aceitar" (que a põe em 0) ou "Descartar" (que apaga
-- a linha). As perguntas de antes nascem aceitas (0), como já estavam. Só uma coluna nova: nenhum
-- gatilho, e nada aqui toca `vaga`, `evento` nem o FTS5.
ALTER TABLE pergunta_perfil ADD COLUMN sugerida INTEGER NOT NULL DEFAULT 0
  CHECK (sugerida IN (0, 1));
