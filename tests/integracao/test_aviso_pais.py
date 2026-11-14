"""O aviso de restrição de país nomeia os países da vaga, no cartão e no detalhe (T147)."""

import json
import re
from contextlib import closing
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apoio.relogio import RelogioFalso
from apoio.semear import AGORA, _encaixe, inserir_vaga, semear
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.painel.app import criar_app

PORTA = 47617
GENERICO = {"pt": "Restrita a moradores de um país", "en": "Restricted to residents of one country"}


def _montar(tmp_path: Path, idioma: str, paises: list[str]) -> tuple[TestClient, int]:
    banco = tmp_path / "jobot.db"
    with closing(abrir(banco)) as con:
        migrar(con, banco)
        con.execute("INSERT INTO config (chave, valor) VALUES ('idioma', ?)", (json.dumps(idioma),))
        vaga_id = inserir_vaga(con, avisos='["restrito_a_pais"]')
        for pais in paises:
            con.execute("INSERT INTO local_vaga (vaga_id, pais) VALUES (?, ?)", (vaga_id, pais))
        con.commit()
    app = criar_app(tmp_path, PORTA)
    return TestClient(app, base_url=f"http://127.0.0.1:{PORTA}"), vaga_id


def _selos(html: str) -> str:
    return " ".join(re.findall(r'<li class="selo">(.*?)</li>', html, re.S))


@pytest.mark.parametrize(
    ("idioma", "paises", "esperado"),
    [
        ("pt", ["BR"], "Só para quem mora em: Brasil"),
        ("pt", ["BR", "PT", "ES"], "Só para quem mora em: Brasil, Portugal e Espanha"),
        (
            "pt",
            ["BR", "PT", "ES", "US", "CA"],
            "Só para quem mora em: Brasil, Portugal, Espanha +2",
        ),
        ("pt", ["BR", "BR"], "Só para quem mora em: Brasil"),
        ("en", ["BR"], "Only for residents of: Brazil"),
        ("en", ["BR", "PT", "ES"], "Only for residents of: Brazil, Portugal and Spain"),
        ("pt", [], GENERICO["pt"]),
        ("en", [], GENERICO["en"]),
    ],
)
def test_aviso_nomeia_os_paises(
    tmp_path: Path, idioma: str, paises: list[str], esperado: str
) -> None:
    http, vaga_id = _montar(tmp_path, idioma, paises)
    cartao = http.get("/vagas?aba=todas").text
    assert f'id="vaga-{vaga_id}"' in cartao
    assert esperado in _selos(cartao)
    assert esperado in _selos(http.get(f"/vagas/{vaga_id}").text)


def test_destaques_tambem_nomeiam_os_paises(tmp_path: Path) -> None:
    banco = tmp_path / "jobot.db"
    with closing(abrir(banco)) as con:
        migrar(con, banco)
        busca = semear(con)["busca"]
        vaga_id = inserir_vaga(
            con,
            avisos='["restrito_a_pais"]',
            primeira_vista_em=(AGORA - timedelta(hours=3)).isoformat(),
        )
        con.execute("INSERT INTO local_vaga (vaga_id, pais) VALUES (?, 'BR')", (vaga_id,))
        _encaixe(con, busca, vaga_id, 99)
        con.commit()
    app = criar_app(tmp_path, PORTA)
    app.state.relogio = RelogioFalso()
    http = TestClient(app, base_url=f"http://127.0.0.1:{PORTA}")
    pagina = http.get("/vagas?aba=destaques").text
    assert f'id="vaga-{vaga_id}"' in pagina
    assert "Só para quem mora em: Brasil" in _selos(pagina)
