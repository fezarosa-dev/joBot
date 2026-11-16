"""O mapa da entrada para o estado do login e o registro com aviso (plano T272, E3)."""

import ast
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

import pytest
from playwright.async_api import Error as ErroDoPlaywright

from apoio.relogio import RelogioFalso
from apoio.site_falso import LeitorFalso
from jobot.banco.cadastros import semear_leitores
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.banco.sessoes import ler_sessao
from jobot.navegador.captcha import Widget
from jobot.navegador.pagina import Recusada, Visita
from jobot.navegador.sessao import estado_da_falha, estado_da_visita, registrar_sessao
from jobot.nucleo.contas import EstadoSessao, MotivoSessao
from jobot.nucleo.leitores.base import Captura

pytestmark = pytest.mark.anyio

EXECUCAO = Path(__file__).resolve().parents[2] / "src" / "jobot" / "navegador" / "execucao.py"
LEITOR = LeitorFalso(base="https://site.test")  # `pagina_logada` procura `id="conta"` no HTML
FRASE_PT = (
    "Sua sessão no Site falso caiu. Abra o joBot e entre de novo em Configurações › Sites com"
    " login."
)
FRASE_EN = (
    "Your Site falso session ended. Open joBot and sign in again in Settings › Sites with login."
)


def _captura(html: str) -> Captura:
    return Captura("https://site.test/logado", 200, html, ())


@pytest.fixture
def con(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    caminho = tmp_path / "jobot.db"
    c = abrir(caminho)
    migrar(c, caminho)
    semear_leitores(c, [LEITOR])
    yield c
    c.close()


class Avisos:
    """O `avisar` falso: guarda as chamadas."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, str]] = []

    def __call__(self, titulo: str, frase: str) -> None:
        self.chamadas.append((titulo, frase))


@pytest.mark.parametrize(
    ("visita", "esperado"),
    [
        pytest.param(_captura("<div id='conta'>Conta</div>"), ("conectado", None), id="logada"),
        pytest.param(_captura("<p>Entrar</p>"), ("precisa_entrar", None), id="sem_marca"),
        pytest.param("precisa_login", ("precisa_entrar", None), id="precisa_login"),
        pytest.param("bloqueio", ("nao_conferiu", "bloqueio"), id="bloqueio"),
        pytest.param(Recusada("fora.test"), ("nao_conferiu", "bloqueio"), id="recusada"),
        pytest.param("captcha", ("nao_conferiu", "desafio"), id="captcha"),
        pytest.param(
            Widget("recaptcha_v2", "chave", False, None, None),
            ("nao_conferiu", "desafio"),
            id="widget",
        ),
        pytest.param("no_limite", ("nao_conferiu", "no_limite"), id="no_limite"),
    ],
)
def test_mapa_da_entrada(
    visita: Visita, esperado: tuple[EstadoSessao, MotivoSessao | None]
) -> None:
    assert estado_da_visita(visita, LEITOR) == esperado


def test_falha_do_playwright_vira_sem_rede() -> None:
    assert estado_da_falha(ErroDoPlaywright("net::ERR_CONNECTION_REFUSED")) == (
        "nao_conferiu",
        "sem_rede",
    )


def test_outra_excecao_vira_erro() -> None:
    # guarda (nasce verde com o valor errado); mutante: toda falha vira `sem_rede`
    assert estado_da_falha(RuntimeError("quebrou")) == ("nao_conferiu", "erro")


async def _registrar(
    con: sqlite3.Connection,
    relogio: RelogioFalso,
    avisos: Avisos,
    estado: EstadoSessao,
    motivo: MotivoSessao | None = None,
    idioma: Literal["pt", "en"] = "pt",
) -> bool:
    await relogio.dormir(60)
    return await registrar_sessao(
        con, LEITOR, estado, motivo, relogio, avisar=avisos, idioma=idioma
    )


async def test_registrar_avisa_uma_vez_por_queda(con: sqlite3.Connection) -> None:
    relogio, avisos = RelogioFalso(), Avisos()
    sequencia: list[tuple[EstadoSessao, MotivoSessao | None]] = [
        ("conectado", None),
        ("precisa_entrar", None),
        ("precisa_entrar", None),
        ("nao_conferiu", "sem_rede"),
        ("precisa_entrar", None),
        ("conectado", None),
        ("precisa_entrar", None),
    ]
    abriram = [await _registrar(con, relogio, avisos, e, m) for e, m in sequencia]
    assert abriram == [False, True, False, False, False, False, True]
    assert avisos.chamadas == [("joBot", FRASE_PT), ("joBot", FRASE_PT)]
    sessao = ler_sessao(con, "site", LEITOR.chave)
    assert sessao is not None and sessao.estado == "precisa_entrar"


async def test_registrar_nunca_entrou_nao_avisa(con: sqlite3.Connection) -> None:
    relogio, avisos = RelogioFalso(), Avisos()
    assert await _registrar(con, relogio, avisos, "precisa_entrar") is False
    assert avisos.chamadas == []
    # controle positivo na mesma montagem: depois de entrar, a queda avisa
    await _registrar(con, relogio, avisos, "conectado")
    assert await _registrar(con, relogio, avisos, "precisa_entrar") is True
    assert avisos.chamadas == [("joBot", FRASE_PT)]


async def test_aviso_no_idioma_en(con: sqlite3.Connection) -> None:
    relogio, avisos = RelogioFalso(), Avisos()
    await _registrar(con, relogio, avisos, "conectado", idioma="en")
    await _registrar(con, relogio, avisos, "precisa_entrar", idioma="en")
    assert avisos.chamadas == [("joBot", FRASE_EN)]


def test_titulo_so_em_sessao() -> None:
    # guarda; mutante: `execucao.py` volta a definir `_TITULO_AVISO`
    arvore = ast.parse(EXECUCAO.read_text(encoding="utf-8"))
    nomes = {
        alvo.id
        for no in ast.walk(arvore)
        if isinstance(no, ast.Assign | ast.AnnAssign)
        for alvo in (no.targets if isinstance(no, ast.Assign) else [no.target])
        if isinstance(alvo, ast.Name)
    }
    assert nomes & {"_TITULO_AVISO", "TITULO_AVISO"} == set()
