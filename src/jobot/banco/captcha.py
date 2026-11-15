"""Portão e teto diário do 2Captcha (plano T181; ADR 0022).

O interruptor `captcha_ligado` mora em `cadastros.PADROES`; aqui ficam o portão da fase 2 e o
contador de resoluções do dia, na chave `captcha_uso` da `config`.
"""

import sqlite3
from datetime import date

from jobot.banco.cadastros import ler_config

TETO_DIA = 30

# Um comando só: o contador vale `{"dia": "AAAA-MM-DD", "n": N}`. Valor que não é JSON, ou sem
# `dia` igual ao de hoje e `n` inteiro, recomeça em 1; com `n` no teto o WHERE barra a gravação.
_RESERVAR = """
INSERT INTO config (chave, valor) VALUES ('captcha_uso', json_object('dia', :dia, 'n', 1))
ON CONFLICT(chave) DO UPDATE SET valor = json_object(
    'dia', :dia,
    'n', CASE WHEN {de_hoje} THEN json_extract(config.valor, '$.n') + 1 ELSE 1 END
)
WHERE NOT ({de_hoje} AND json_extract(config.valor, '$.n') >= :teto)
""".format(
    de_hoje="""(CASE WHEN json_valid(config.valor)
        THEN json_extract(config.valor, '$.dia') IS :dia
             AND json_type(config.valor, '$.n') IS 'integer'
        ELSE 0 END)"""
)


def captcha_pronto(con: sqlite3.Connection, chave: str | None) -> bool:
    """Portão da navegação com login: interruptor ligado e chave salva."""
    return ler_config(con, "captcha_ligado") is True and chave is not None


def reservar_resolucao(con: sqlite3.Connection, dia: date) -> bool:
    """Conta uma resolução em `dia`; `False` (sem contar) quando o teto do dia já foi usado."""
    with con:
        cur = con.execute(_RESERVAR, {"dia": dia.isoformat(), "teto": TETO_DIA})
    return cur.rowcount == 1
