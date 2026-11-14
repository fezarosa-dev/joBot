"""Migrações numeradas em `migracoes/`, versão em `PRAGMA user_version` (desenho, 7.4)."""

import re
import sqlite3
from pathlib import Path

from jobot.banco.conexao import tem_fts5

MIGRACOES = Path(__file__).parent / "migracoes"
COPIAS_GUARDADAS = 3

# vaga_fts fica fora do .sql fixo: só existe quando o SQLite tem FTS5 (DR-05).
# Sem gatilho de DELETE: vaga nunca é apagada.
_FTS5 = """
CREATE VIRTUAL TABLE vaga_fts USING fts5(
  titulo, empresa, descricao_texto,
  content='vaga', content_rowid='id',
  tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER vaga_fts_insert AFTER INSERT ON vaga
BEGIN
  INSERT INTO vaga_fts (rowid, titulo, empresa, descricao_texto)
  VALUES (new.id, new.titulo, new.empresa, new.descricao_texto);
END;
CREATE TRIGGER vaga_fts_update AFTER UPDATE OF titulo, empresa, descricao_texto ON vaga
BEGIN
  INSERT INTO vaga_fts (vaga_fts, rowid, titulo, empresa, descricao_texto)
  VALUES ('delete', old.id, old.titulo, old.empresa, old.descricao_texto);
  INSERT INTO vaga_fts (rowid, titulo, empresa, descricao_texto)
  VALUES (new.id, new.titulo, new.empresa, new.descricao_texto);
END;
"""


class BancoMaisNovo(Exception):
    """O banco foi criado por um joBot mais novo; abrir assim o estragaria (RF5)."""


def _migracoes(pasta: Path) -> list[tuple[int, Path]]:
    achadas = [(int(m[1]), p) for p in pasta.glob("*.sql") if (m := re.match(r"(\d+)_", p.name))]
    return sorted(achadas)


def _versao(con: sqlite3.Connection) -> int:
    versao: int = con.execute("PRAGMA user_version").fetchone()[0]
    return versao


def _copiar(con: sqlite3.Connection, caminho: Path, versao: int) -> None:
    """Cópia pela API de backup, guardando só as mais recentes (DR-06)."""
    copia = sqlite3.connect(caminho.with_name(f"{caminho.name}.antes-v{versao}"))
    try:
        con.backup(copia)
    finally:
        copia.close()
    prefixo = f"{caminho.name}.antes-v"
    copias = sorted(
        (int(p.name.removeprefix(prefixo)), p)
        for p in caminho.parent.glob(f"{prefixo}*")
        if p.name.removeprefix(prefixo).isdigit()
    )
    for _, velha in copias[:-COPIAS_GUARDADAS]:
        velha.unlink()


def _aplicar(con: sqlite3.Connection, numero: int, sql: str) -> None:
    # o pragma não muda dentro de transação: desliga antes do BEGIN. Sem isso o DROP TABLE de
    # uma reconstrução de vaga apagaria os filhos em cascata (desenho 7.4, DR-69).
    if numero == 1 and tem_fts5(con):
        sql += _FTS5
    con.execute("PRAGMA foreign_keys=OFF")
    try:
        # executescript não faz COMMIT no fim, mas faz um antes de rodar: por isso um só,
        # com o BEGIN dentro, e a transação segue aberta até o COMMIT abaixo
        con.executescript(f"BEGIN;\n{sql}\n")
        quebradas = con.execute("PRAGMA foreign_key_check").fetchall()
        if quebradas:
            raise sqlite3.IntegrityError(
                f"migração {numero:04d} deixa chave estrangeira quebrada: {quebradas[:5]!r}"
            )
        con.execute(f"PRAGMA user_version = {numero:d}")
        con.execute("COMMIT")
    except BaseException:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    finally:
        con.execute("PRAGMA foreign_keys=ON")


def migrar(con: sqlite3.Connection, caminho: Path, pasta: Path = MIGRACOES) -> int:
    """Aplica as migrações que faltam, cada uma na sua transação; devolve a versão final."""
    migracoes = _migracoes(pasta)
    atual = _versao(con)
    conhecida = migracoes[-1][0] if migracoes else 0
    if atual > conhecida:
        raise BancoMaisNovo(f"banco na versão {atual}; este joBot conhece até a {conhecida}")
    faltam = [(n, p) for n, p in migracoes if n > atual]
    if faltam and con.in_transaction:
        # com transação aberta o PRAGMA foreign_keys=OFF não vale e o DROP TABLE apagaria filhos
        raise sqlite3.OperationalError("migrar pede a conexão sem transação aberta")
    if faltam and atual > 0:  # banco vazio não tem o que guardar
        _copiar(con, caminho, atual)
    for numero, arquivo in faltam:
        _aplicar(con, numero, arquivo.read_text(encoding="utf-8"))
    return _versao(con)
