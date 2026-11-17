-- Fonte com login (T202, D132.8, D132.20): marca as fontes lidas pelo navegador com login.
-- As linhas antigas ficam com 0 (fonte pública); só a semeadura dos leitores põe 1.
ALTER TABLE fonte ADD COLUMN com_login INTEGER NOT NULL DEFAULT 0 CHECK (com_login IN (0,1));
