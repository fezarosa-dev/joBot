"""Migração 0013 (T430): perfil completo, experiências, cursos, perguntas e preparos (desenho 8, 9).

Confere o esquema (colunas, CHECK, chaves) e a gravação de `banco/perfil.py` e `banco/ia.py`:
`ON CONFLICT DO UPDATE`, "Apagar perfil" apaga tudo isso e tirar uma experiência apaga a linha.
"""

import shutil
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from jobot.banco import ia, perfil
from jobot.banco.conexao import abrir
from jobot.banco.migrar import MIGRACOES, migrar

ARQUIVO = MIGRACOES / "0013_perfil.sql"
T0 = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
AGORA = T0.isoformat()


def _arquivo_da_0013() -> Path:
    """Afirma que o arquivo existe: o vermelho é por asserção, não por I/O."""
    assert ARQUIVO.exists()
    return ARQUIVO


@pytest.fixture
def antes(tmp_path: Path) -> Iterator[tuple[sqlite3.Connection, Path, Path]]:
    """Banco nas versões 0001 a 0012, mais a pasta onde a 0013 entra."""
    _arquivo_da_0013()
    pasta = tmp_path / "ate_a_decima_segunda"
    pasta.mkdir()
    for arquivo in sorted(MIGRACOES.glob("*.sql"))[:12]:
        shutil.copy(arquivo, pasta)
    caminho = tmp_path / "jobot.db"
    con = abrir(caminho)
    assert migrar(con, caminho, pasta) == 12
    yield con, caminho, pasta
    con.close()


def _aplicar_0013(con: sqlite3.Connection, caminho: Path, pasta: Path) -> None:
    shutil.copy(_arquivo_da_0013(), pasta)
    assert migrar(con, caminho, pasta) == 13


def _vaga(con: sqlite3.Connection, vaga_id: int) -> None:
    con.execute(
        "INSERT INTO vaga (id, url_hash, titulo, empresa, url, primeira_vista_em,"
        " ultima_vista_em, versao_regras) VALUES (?, ?, 't', 'e', ?, '2026-11-13',"
        " '2026-11-13', 'v1')",
        (vaga_id, f"h{vaga_id}", f"https://x.test/{vaga_id}"),
    )


@pytest.fixture
def con(antes: tuple[sqlite3.Connection, Path, Path]) -> sqlite3.Connection:
    """Banco só até a 0013, com as vagas 1 e 2: migrações novas não mudam o que se confere."""
    c, caminho, pasta = antes
    _aplicar_0013(c, caminho, pasta)
    _vaga(c, 1)
    _vaga(c, 2)
    c.commit()
    return c


def _recusa(con: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> bool:
    """Verdadeiro se o banco recusa o comando (`IntegrityError`). Desfaz o que entrou."""
    con.execute("SAVEPOINT t")
    try:
        con.execute(sql, params)
    except sqlite3.IntegrityError:
        return True
    finally:
        con.execute("ROLLBACK TO t")
        con.execute("RELEASE t")
    return False


def _colunas(con: sqlite3.Connection, tabela: str) -> dict[str, int]:
    """Nome da coluna -> posição na chave primária (0 = fora dela)."""
    return {nome: pk for _, nome, _, _, _, pk in con.execute(f"PRAGMA table_info({tabela})")}


def _conta(con: sqlite3.Connection, tabela: str) -> int:
    return int(con.execute(f"SELECT count(*) FROM {tabela}").fetchone()[0])


# esquema


def test_versao_sobe_para_13(con: sqlite3.Connection) -> None:
    assert con.execute("PRAGMA user_version").fetchone()[0] == 13


def test_perfil_ganha_as_colunas_e_nada_de_cpf_nascimento_projetos_nem_curriculo(
    con: sqlite3.Connection,
) -> None:
    assert _colunas(con, "perfil") == {
        "id": 1,
        "habilidades": 0,
        "atualizado_em": 0,
        "nome": 0,
        "email": 0,
        "telefone": 0,
        "cidade_moradia": 0,
        "cargo_atual": 0,
        "anos_de_experiencia": 0,
        "formacao_nivel": 0,
        "resumo": 0,
        "idiomas_falados": 0,
        "links": 0,
    }
    # o igual acima já recusa coluna a mais; o texto do esquema também não cita esses dados
    esquema = " ".join(r[0] or "" for r in con.execute("SELECT sql FROM sqlite_master")).lower()
    for proibido in ("cpf", "nascimento", "projeto", "curriculo"):
        assert proibido not in esquema, proibido


def test_perfil_confere_anos_e_formacao(con: sqlite3.Connection) -> None:
    sql = (
        "INSERT INTO perfil (id, habilidades, atualizado_em, anos_de_experiencia, formacao_nivel)"
        " VALUES (1, '[]', ?, ?, ?)"
    )
    for anos, nivel in ((None, None), (0, "medio"), (60, "doutorado"), (5, "pos_graduacao")):
        assert _recusa(con, sql, (AGORA, anos, nivel)) is False, (anos, nivel)
    for nivel in ("tecnico", "graduacao", "mestrado"):
        assert _recusa(con, sql, (AGORA, 1, nivel)) is False, nivel
    assert _recusa(con, sql, (AGORA, -1, None)) is True
    assert _recusa(con, sql, (AGORA, 61, None)) is True
    assert _recusa(con, sql, (AGORA, None, "phd")) is True


def test_experiencia_e_curso_colunas(con: sqlite3.Connection) -> None:
    assert _colunas(con, "experiencia") == {
        "id": 1,
        "cargo": 0,
        "empresa": 0,
        "inicio": 0,
        "fim": 0,
        "descricao": 0,
    }
    assert _colunas(con, "curso") == {
        "id": 1,
        "nome": 0,
        "instituicao": 0,
        "situacao": 0,
        "previsao": 0,
    }
    sql = "INSERT INTO experiencia (cargo) VALUES (?)"
    assert _recusa(con, sql, ("Analista",)) is False
    assert _recusa(con, sql, (None,)) is True
    assert _recusa(con, sql, ("",)) is True


def test_curso_situacao_so_a_lista(con: sqlite3.Connection) -> None:
    sql = "INSERT INTO curso (nome, situacao) VALUES ('ADS', ?)"
    for situacao in (None, "concluido", "cursando", "trancado"):
        assert _recusa(con, sql, (situacao,)) is False, situacao
    assert _recusa(con, sql, ("formado",)) is True
    assert _recusa(con, "INSERT INTO curso (nome) VALUES ('')") is True


def test_pergunta_perfil_origem_base_ou_ia_e_chave_unica(con: sqlite3.Connection) -> None:
    assert _colunas(con, "pergunta_perfil") == {
        "id": 1,
        "chave": 0,
        "pergunta": 0,
        "por_que": 0,
        "resposta": 0,
        "origem": 0,
        "criada_em": 0,
        "respondida_em": 0,
    }
    sql = "INSERT INTO pergunta_perfil (chave, pergunta, origem, criada_em) VALUES (?, 'p?', ?, ?)"
    assert _recusa(con, sql, ("a", "base", AGORA)) is False
    assert _recusa(con, sql, ("b", "ia", AGORA)) is False
    assert _recusa(con, sql, ("c", "outra", AGORA)) is True
    assert _recusa(con, sql, ("d", None, AGORA)) is True
    con.execute(sql, ("e", "ia", AGORA))
    assert _recusa(con, sql, ("e", "base", AGORA)) is True  # chave repetida


def test_preparo_candidatura_uma_linha_por_vaga(con: sqlite3.Connection) -> None:
    assert _colunas(con, "preparo_candidatura") == {
        "vaga_id": 1,
        "idioma": 0,
        "carta": 0,
        "resumo": 0,
        "tem": 0,
        "faltam": 0,
        "perguntar": 0,
        "usou": 0,
        "backend": 0,
        "modelo": 0,
        "versao": 0,
        "feito_em": 0,
    }
    sql = (
        "INSERT INTO preparo_candidatura (vaga_id, idioma, carta, resumo, tem, faltam, perguntar,"
        " usou, backend, modelo, versao, feito_em)"
        " VALUES (?, 'pt', 'c', 'r', '[]', '[]', '[]', '[]', 'local', 'm', 1, ?)"
    )
    assert _recusa(con, sql, (1, AGORA)) is False
    assert _recusa(con, sql, (999, AGORA)) is True  # vaga_id referencia vaga
    con.execute(sql, (1, AGORA))
    assert _recusa(con, sql, (1, AGORA)) is True  # uma linha por vaga


def test_antes_nada_se_perde(antes: tuple[sqlite3.Connection, Path, Path]) -> None:
    con, caminho, pasta = antes
    _vaga(con, 1)
    con.execute(
        "INSERT INTO perfil (id, habilidades, atualizado_em) VALUES (1, '[\"Python\"]', ?)",
        (AGORA,),
    )
    con.execute(
        "INSERT INTO habilidades_vaga (vaga_id, pede, feito_em) VALUES (1, '[\"SQL\"]', ?)",
        (AGORA,),
    )
    con.execute("INSERT INTO candidatura (vaga_id, abriu_em) VALUES (1, ?)", (AGORA,))
    con.commit()
    tabelas = ("vaga", "candidatura", "habilidades_vaga", "evento", "config")
    guardadas = {t: con.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall() for t in tabelas}
    gatilhos = con.execute("SELECT name FROM sqlite_master WHERE type = 'trigger'").fetchall()

    _aplicar_0013(con, caminho, pasta)

    for tabela, linhas in guardadas.items():
        assert con.execute(f"SELECT * FROM {tabela} ORDER BY 1").fetchall() == linhas, tabela
    assert perfil.habilidades(con) == ["Python"]
    assert perfil.dados(con) == perfil.Dados()  # as colunas novas nascem vazias
    gatilhos_depois = con.execute("SELECT name FROM sqlite_master WHERE type = 'trigger'")
    assert gatilhos_depois.fetchall() == gatilhos  # nenhum gatilho novo nem perdido
    for tabela in ("experiencia", "curso", "pergunta_perfil", "preparo_candidatura"):
        assert _conta(con, tabela) == 0, tabela


# perfil


def _dados(**mudar: Any) -> perfil.Dados:
    base: dict[str, Any] = {
        "nome": "Pessoa Teste",
        "email": "pessoa@exemplo.test",
        "telefone": "+55 11 90000-0000",
        "cidade_moradia": "Campinas",
        "cargo_atual": "Analista",
        "anos_de_experiencia": 4,
        "formacao_nivel": "graduacao",
        "resumo": "Gosto de dados.",
        "idiomas_falados": (("pt", "fluente"), ("en", "intermediario")),
        "links": ("https://exemplo.test/eu",),
    }
    base.update(mudar)
    return perfil.Dados(**base)


def test_sem_perfil_dados_vazios(con: sqlite3.Connection) -> None:
    assert perfil.dados(con) == perfil.Dados()
    perfil.gravar_dados(con, _dados(), T0)  # controle: com a linha, os dados voltam
    assert perfil.dados(con) == _dados()


def test_dados_gravados_duas_vezes_ficam_uma_linha_e_guardam_as_habilidades(
    con: sqlite3.Connection,
) -> None:
    perfil.gravar_habilidades(con, ["Python"], T0)
    perfil.gravar_dados(con, _dados(), T0 + timedelta(hours=1))
    perfil.gravar_dados(con, _dados(cargo_atual="Cientista", links=()), T0 + timedelta(hours=2))
    assert _conta(con, "perfil") == 1
    assert perfil.dados(con) == _dados(cargo_atual="Cientista", links=())
    assert perfil.habilidades(con) == ["Python"]  # gravar os dados não mexe nas habilidades
    hora = con.execute("SELECT atualizado_em FROM perfil").fetchone()[0]
    assert hora == (T0 + timedelta(hours=2)).isoformat()


def test_habilidades_gravadas_depois_guardam_os_dados(con: sqlite3.Connection) -> None:
    perfil.gravar_dados(con, _dados(), T0)
    assert perfil.habilidades(con) == []  # dados sem habilidades: lista vazia
    perfil.gravar_habilidades(con, ["Rust"], T0 + timedelta(hours=1))
    assert perfil.dados(con) == _dados()
    assert perfil.habilidades(con) == ["Rust"]


@pytest.mark.parametrize(
    ("coluna", "valor"),
    [
        ("idiomas_falados", "não é json"),
        ("idiomas_falados", '[["pt"], {"x": 1}, ["en", 3]]'),
        ("links", '{"a": 1}'),
        ("links", "[3, null]"),
    ],
)
def test_json_adulterado_le_vazio(con: sqlite3.Connection, coluna: str, valor: str) -> None:
    perfil.gravar_dados(con, _dados(), T0)
    con.execute(f"UPDATE perfil SET {coluna} = ?", (valor,))
    con.commit()
    assert perfil.dados(con) == _dados(**{coluna: ()})


def test_json_meio_estranho_guarda_so_o_que_serve(con: sqlite3.Connection) -> None:
    perfil.gravar_dados(con, _dados(), T0)
    con.execute(
        "UPDATE perfil SET idiomas_falados = ?, links = ?",
        ('[["pt", "fluente"], ["en"], 7]', '["https://a.test", 2]'),
    )
    con.commit()
    lido = perfil.dados(con)
    assert lido.idiomas_falados == (("pt", "fluente"),)
    assert lido.links == ("https://a.test",)


def test_experiencia_gravada_editada_e_tirada(con: sqlite3.Connection) -> None:
    exp = perfil.Experiencia(cargo="Analista", empresa="ACME", inicio="2020-01", descricao="SQL")
    primeira = perfil.gravar_experiencia(con, exp)
    segunda = perfil.gravar_experiencia(con, perfil.Experiencia(cargo="Estagiário"))
    assert primeira != segunda
    editada = perfil.Experiencia(cargo="Analista Sênior", empresa="ACME", id=primeira)
    assert perfil.gravar_experiencia(con, editada) == primeira  # mesma linha, no lugar
    assert perfil.experiencias(con) == [editada, perfil.Experiencia(cargo="Estagiário", id=segunda)]
    perfil.apagar_experiencia(con, primeira)
    assert perfil.experiencias(con) == [perfil.Experiencia(cargo="Estagiário", id=segunda)]
    assert _conta(con, "experiencia") == 1  # a linha some, não fica marcada


def test_curso_gravado_editado_e_tirado(con: sqlite3.Connection) -> None:
    curso = perfil.Curso(nome="ADS", instituicao="Fatec", situacao="cursando", previsao="2027-12")
    cid = perfil.gravar_curso(con, curso)
    outro = perfil.gravar_curso(con, perfil.Curso(nome="Inglês"))
    concluido = perfil.Curso(nome="ADS", instituicao="Fatec", situacao="concluido", id=cid)
    assert perfil.gravar_curso(con, concluido) == cid
    assert perfil.cursos(con) == [concluido, perfil.Curso(nome="Inglês", id=outro)]
    perfil.apagar_curso(con, outro)
    assert perfil.cursos(con) == [concluido]
    assert _conta(con, "curso") == 1


def test_pergunta_sugerida_de_novo_nao_apaga_a_resposta(con: sqlite3.Connection) -> None:
    perfil.gravar_pergunta(con, "ia:docker", "Já usou Docker?", "ia", T0, por_que="A vaga pede.")
    perfil.responder_pergunta(con, "ia:docker", "Sim, dois anos.", T0 + timedelta(hours=1))
    perfil.gravar_pergunta(
        con, "ia:docker", "Você já usou Docker?", "ia", T0 + timedelta(hours=2), por_que="Outra."
    )
    assert _conta(con, "pergunta_perfil") == 1
    assert perfil.perguntas(con) == [
        perfil.PerguntaPerfil(
            chave="ia:docker",
            pergunta="Você já usou Docker?",
            origem="ia",
            por_que="Outra.",
            resposta="Sim, dois anos.",
        )
    ]
    respondida = con.execute("SELECT criada_em, respondida_em FROM pergunta_perfil").fetchone()
    assert respondida == (T0.isoformat(), (T0 + timedelta(hours=1)).isoformat())


def test_responder_pergunta_que_nao_existe_nao_cria(con: sqlite3.Connection) -> None:
    perfil.responder_pergunta(con, "nao:existe", "x", T0)
    assert _conta(con, "pergunta_perfil") == 0
    perfil.gravar_pergunta(con, "base:links", "Seus links?", "base", T0)  # controle
    perfil.responder_pergunta(con, "base:links", "https://a.test", T0)
    assert [p.resposta for p in perfil.perguntas(con)] == ["https://a.test"]


# preparo


def _preparo(**mudar: Any) -> ia.Preparo:
    base: dict[str, Any] = {
        "idioma": "pt",
        "carta": "Olá, <script>x</script>",
        "resumo": "Resumo.",
        "tem": ("Python",),
        "faltam": ("Docker",),
        "perguntar": ("Já usou Docker?",),
        "usou": ("cargo_atual", "habilidades"),
        "backend": "local",
        "modelo": "qwen",
        "versao": 1,
        "feito_em": T0.isoformat(),
    }
    base.update(mudar)
    return ia.Preparo(**base)


def test_preparo_refeito_substitui_a_linha(con: sqlite3.Connection) -> None:
    assert ia.preparo(con, 1) is None
    ia.gravar_preparo(con, 1, _preparo())
    novo = _preparo(carta="Outra carta", faltam=(), feito_em=(T0 + timedelta(hours=1)).isoformat())
    ia.gravar_preparo(con, 1, novo)
    assert _conta(con, "preparo_candidatura") == 1
    assert ia.preparo(con, 1) == novo
    assert ia.preparo(con, 2) is None  # outra vaga, sem preparo


def test_preparo_com_json_adulterado_le_listas_vazias(con: sqlite3.Connection) -> None:
    ia.gravar_preparo(con, 1, _preparo())
    con.execute("UPDATE preparo_candidatura SET tem = 'x', faltam = '{}', usou = '[1, \"a\"]'")
    con.commit()
    assert ia.preparo(con, 1) == _preparo(tem=(), faltam=(), usou=("a",))


# Apagar perfil


def _tudo(con: sqlite3.Connection) -> None:
    perfil.gravar_habilidades(con, ["Python"], T0)
    perfil.gravar_dados(con, _dados(), T0)
    perfil.gravar_experiencia(con, perfil.Experiencia(cargo="Analista"))
    perfil.gravar_curso(con, perfil.Curso(nome="ADS"))
    perfil.gravar_pergunta(con, "ia:x", "x?", "ia", T0)
    ia.gravar_preparo(con, 1, _preparo())
    con.execute(
        "INSERT INTO habilidades_vaga (vaga_id, pede, feito_em) VALUES (1, '[\"SQL\"]', ?)",
        (AGORA,),
    )
    con.execute("INSERT INTO candidatura (vaga_id, abriu_em) VALUES (1, ?)", (AGORA,))
    con.commit()


def test_apagar_perfil_apaga_tudo_do_perfil(con: sqlite3.Connection) -> None:
    _tudo(con)
    pessoais = ("perfil", "experiencia", "curso", "pergunta_perfil", "preparo_candidatura")
    for tabela in pessoais:  # controle: há o que apagar
        assert _conta(con, tabela) == 1, tabela
    perfil.apagar_perfil(con)
    for tabela in pessoais:
        assert _conta(con, tabela) == 0, tabela
    # o que é da vaga fica: não depende do perfil (desenho 8)
    assert _conta(con, "habilidades_vaga") == 1
    assert _conta(con, "candidatura") == 1
    assert _conta(con, "vaga") == 2
