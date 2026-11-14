-- Motivo da última falha de leitura da página, em código (T128, A49); nulo se a última leitura deu certo.
ALTER TABLE pagina_acompanhada ADD COLUMN motivo TEXT;
