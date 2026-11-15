"""`scripts/capturar_logado.py` (T220; desenho A10): limpeza pela posição, conferência e trava.

Nome e id da conta são inventados (`Fulana Exemplo`, `u-998877`); os segredos da sessão também.
"""

import importlib.util
import json
import os
import sys
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from types import ModuleType

import pytest

from jobot.sistema.instancia import (
    Trava,
    captura_em_andamento,
    pid_do_servidor,
    pid_e_porta_do_servidor,
)

RAIZ = Path(__file__).resolve().parents[2]

NOME = "Fulana Exemplo"
ID = "u-998877"
CSRF = "csrf-valor-falso-1"
XSRF = "xsrf-valor-falso-2"
JWT = "eyJhbGciOiJub25lIn0.eyJzdWIiOiJ0ZXN0ZSJ9.YXNzaW5hdHVyYQ"
SESSAO = "SESSAOFALSA123"


def _carregar() -> ModuleType:
    pasta = str(RAIZ / "scripts")
    sys.path.insert(0, pasta)  # o script importa o `capturar.py` vizinho
    try:
        spec = importlib.util.spec_from_file_location(
            "capturar_logado", RAIZ / "scripts" / "capturar_logado.py"
        )
        assert spec is not None and spec.loader is not None
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
    finally:
        sys.path.remove(pasta)
    return modulo


capturar_logado = _carregar()
MARCADOR: str = capturar_logado.MARCADOR


def _limpar(texto: str, tipo: str, campos: list[str]) -> tuple[str, frozenset[str]]:
    limpo: tuple[str, frozenset[str]] = capturar_logado.limpar_logado(texto, tipo, campos)
    return limpo


def _conferir(texto: str, trocados: frozenset[str]) -> list[str]:
    achados: list[str] = capturar_logado.conferir_logado(texto, trocados)
    return achados


# --- limpeza e conferência ---------------------------------------------------------------


def test_limpa_e_passa() -> None:
    corpo = json.dumps(
        {
            "csrf_token": CSRF,
            "dados": {"xsrfToken": XSRF},
            "sessao": JWT,
            "link": f"https://site.invalid/painel;jsessionid={SESSAO}",
            "conta": {"id": ID, "nome": NOME},
            "vagas": [{"titulo": "Vaga 1"}],
        }
    )
    texto, trocados = _limpar(corpo, "application/json", ["$.conta.id", "$.conta.nome"])
    dado = json.loads(texto)
    assert dado["csrf_token"] == MARCADOR
    assert dado["dados"]["xsrfToken"] == MARCADOR
    assert dado["sessao"] == MARCADOR
    assert dado["link"] == f"https://site.invalid/painel;jsessionid={MARCADOR}"
    assert dado["conta"] == {"id": MARCADOR, "nome": MARCADOR}
    assert dado["vagas"] == [{"titulo": "Vaga 1"}]
    assert {ID, NOME, CSRF, XSRF, JWT, SESSAO} <= trocados
    assert _conferir(texto, trocados) == []

    pagina = (
        f"<html><head><meta name='csrf-token' content='{CSRF}'></head><body>"
        f"<div id='conta'>{NOME}</div><form><input type='hidden' value='{XSRF}' name='_xsrf'>"
        f"</form><a href='/sair?_csrf={CSRF}'>Sair</a><p>Vaga 1</p></body></html>"
    )
    html, trocados_html = _limpar(pagina, "text/html", ["#conta", "$.conta.id"])
    for segredo in (NOME, CSRF, XSRF):
        assert segredo not in html
        assert segredo in trocados_html
    assert "Vaga 1" in html
    assert _conferir(html, trocados_html) == []


def test_residuo_recusado_sem_mostrar_o_valor() -> None:
    corpo = json.dumps({"conta": {"id": ID}, "perfil": f"https://site.invalid/u/{ID}/vagas"})
    texto, trocados = _limpar(corpo, "application/json", ["$.conta.id"])
    assert json.loads(texto)["conta"]["id"] == MARCADOR
    achados = _conferir(texto, trocados)
    assert achados
    assert not any(ID in a for a in achados)

    nao_declarado = json.dumps({"vagas": [], "meu_csrf": CSRF})
    achados_csrf = _conferir(nao_declarado, frozenset())
    assert achados_csrf
    assert not any(CSRF in a for a in achados_csrf)


def test_limpeza_acha_pela_posicao() -> None:
    corpo = json.dumps({"conta": {"id": ID}, "recado": f"Oi, {NOME}"})
    texto, trocados = _limpar(corpo, "application/json", ["$.conta.id"])
    assert json.loads(texto)["conta"]["id"] == MARCADOR
    assert NOME in texto  # fora das posições dadas, a limpeza não procura pelo valor
    assert NOME not in trocados


def test_segredo_opaco_sai_pelo_nome() -> None:
    """Sem leitor entra todo JSON do host: token, sessão, senha e chave saem pelo nome do campo."""
    segredos = {
        "access_token": "opaco-falso-1",
        "sessionId": "opaco-falso-2",
        "refreshToken": "opaco-falso-3",
        "client_secret": "opaco-falso-4",
        "password": "opaco-falso-5",
        "Authorization": "Bearer opaco-falso-6",
        "apiKey": "opaco-falso-7",
    }
    corpo = json.dumps({"vagas": [{"titulo": "Vaga 1"}], **segredos})
    texto, trocados = _limpar(corpo, "application/json", [])
    dado = json.loads(texto)
    assert {chave: dado[chave] for chave in segredos} == dict.fromkeys(segredos, MARCADOR)
    assert dado["vagas"] == [{"titulo": "Vaga 1"}]
    assert _conferir(texto, trocados) == []
    query, _ = _limpar("<a href='/api?access_token=opaco-falso-8&pagina=2'>", "text/html", [])
    assert "opaco-falso-8" not in query
    assert "pagina=2" in query


def test_email_e_telefone_saem_ou_recusam() -> None:
    email = "contato.ficticio@site.invalid"
    telefone = "+55 11 98765-4321"
    corpo = json.dumps({"conta": {"id": ID}, "recado": f"Fale em {email} ou {telefone}"})
    conteudo, trocados = capturar_logado.preparar(corpo, "application/json", ["$.conta.id"], None)
    saida = conteudo.decode()
    assert email not in saida
    assert telefone not in saida
    assert _conferir(saida, trocados) == []

    achados = _conferir(corpo, frozenset())
    assert any(a.startswith("email") for a in achados)
    assert any(a.startswith("telefone") for a in achados)
    assert not any(email in a or "98765" in a for a in achados)


def test_meta_sem_cookie_cabecalho_nem_valor_de_query() -> None:
    url = f"https://site.invalid/api/conta?id={ID}&aba=perfil#topo"
    meta: dict[str, object] = capturar_logado.meta_logado(url, 200, "application/json")
    assert meta["url"] == "https://site.invalid/api/conta?id&aba"
    assert meta["codigo"] == 200
    assert meta["cabecalhos"] == {}
    serializado = json.dumps(meta)
    for valor in (ID, "perfil", "topo"):
        assert valor not in serializado


# --- argumentos e trava ------------------------------------------------------------------


@asynccontextmanager
async def _nao_abre(dados: Path, env: Mapping[str, str]) -> AsyncIterator[object]:
    raise AssertionError("não devia abrir o navegador")
    yield  # só para o Python tratar a função como gerador


def test_sem_leitor_exige_host(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    env = {"JOBOT_DADOS": str(tmp_path)}
    codigo = capturar_logado.main(["--caso", "conta"], env=env, dependencias=_nao_abre)
    assert codigo == 2
    assert "--host" in capsys.readouterr().err
    assert pid_do_servidor(tmp_path) is None


def test_com_jobot_lock_preso_recusa(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    trava = Trava(tmp_path, 47615)
    assert trava.pegar()
    try:
        codigo = capturar_logado.main(
            ["--caso", "conta", "--host", "site.invalid"],
            env={"JOBOT_DADOS": str(tmp_path)},
            dependencias=_nao_abre,
        )
    finally:
        trava.soltar()
    assert codigo == 1
    assert "aberto" in capsys.readouterr().err


def test_segura_o_jobot_lock_sem_porta(tmp_path: Path) -> None:
    vistos: list[tuple[tuple[int | None, int | None], bool]] = []

    @asynccontextmanager
    async def olhar_a_trava(dados: Path, env: Mapping[str, str]) -> AsyncIterator[object]:
        vistos.append((pid_e_porta_do_servidor(dados), captura_em_andamento(dados)))
        raise RuntimeError("parou aqui")
        yield

    codigo = capturar_logado.main(
        ["--caso", "conta", "--host", "site.invalid"],
        env={"JOBOT_DADOS": str(tmp_path)},
        dependencias=olhar_a_trava,
    )
    assert vistos == [((os.getpid(), None), True)]
    assert codigo == 1
    assert pid_do_servidor(tmp_path) is None  # soltou a trava ao sair
