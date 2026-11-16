"""Conferir agora no navegador e o estado do "Fazer login agora" (plano T273, E5), sem navegador."""

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from playwright.async_api import Error as ErroDoPlaywright

from apoio.cofre_falso import CofreFalso
from apoio.relogio import RelogioFalso
from apoio.site_falso import LeitorFalso
from jobot.navegador import conferir, limites
from jobot.navegador.abrir import SemNavegador, SemTela
from jobot.navegador.conferir import Conferencia, conferir_sessao
from jobot.navegador.execucao import Dependencias
from jobot.navegador.login_manual import Resultado, sessao_do_login
from jobot.navegador.pagina import Visita
from jobot.nucleo.contas import EstadoSessao, MotivoSessao
from jobot.nucleo.leitores.base import Captura
from jobot.sistema.cofre import Cofre

pytestmark = pytest.mark.anyio

LEITOR = LeitorFalso(base="https://site.test")  # `pagina_logada` procura `id="conta"` no HTML


class ContextoFalso:
    """O `BrowserContext` falso: `close` chama quem ouviu, como o Playwright."""

    def __init__(self) -> None:
        self.ouvintes: list[Callable[[Any], None]] = []
        self.fechamentos = 0
        self.abas: list[object] = []

    def on(self, evento: str, ouvinte: Callable[[Any], None]) -> None:
        if evento == "close":
            self.ouvintes.append(ouvinte)

    async def new_page(self) -> object:
        aba = object()
        self.abas.append(aba)
        return aba

    def fechar_pela_pessoa(self) -> None:
        for ouvinte in self.ouvintes:
            ouvinte(self)

    async def close(self) -> None:
        self.fechamentos += 1
        self.fechar_pela_pessoa()


class Montagem:
    """Os falsos trocados no módulo `conferir` e o que eles viram."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self.contexto = ContextoFalso()
        self.aberturas: list[tuple[Path, Any]] = []
        self.visitas: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.em_uso = False
        self.erro_ao_abrir: Exception | None = None
        self.visita: Callable[[], Any] = lambda: _captura('<div id="conta"></div>')
        self.deps = Dependencias(
            dados=tmp_path,
            lancar=self._lancar,
            ambiente=lambda: {"DISPLAY": ":0"},
            politica=lambda leitor: lambda url: True,
            sortear=lambda: limites.ESPERA_MIN_S,
            cofre=Cofre(tmp_path, CofreFalso()),
            avisar=lambda titulo, frase: None,
        )
        monkeypatch.setattr(conferir, "abrir_contexto", self._abrir_contexto)
        monkeypatch.setattr(conferir, "visitar", self._visitar)
        monkeypatch.setattr(conferir, "perfil_em_uso", lambda perfil: self.em_uso)

    async def _lancar(self, **argumentos: Any) -> Any:
        raise AssertionError("o `abrir_contexto` falso não lança nada")

    async def _abrir_contexto(self, dados: Path, ambiente: Any, lancar: Any) -> ContextoFalso:
        self.aberturas.append((dados, ambiente))
        if self.erro_ao_abrir is not None:
            raise self.erro_ao_abrir
        return self.contexto

    async def _visitar(self, *args: Any, **kwargs: Any) -> Visita:
        self.visitas.append((args, kwargs))
        resultado = self.visita()
        if asyncio.iscoroutine(resultado):
            resultado = await resultado
        assert not isinstance(resultado, Exception)
        return resultado  # type: ignore[no-any-return]

    async def conferir(self) -> Conferencia | None:
        tarefa = asyncio.ensure_future(conferir_sessao(LEITOR, self.deps, RelogioFalso()))
        feitas, _ = await asyncio.wait({tarefa}, timeout=5)
        assert feitas, "conferir_sessao não voltou"
        return tarefa.result()


def _captura(html: str) -> Captura:
    return Captura("https://site.test/logado", 200, html, ())


def _levanta(erro: Exception) -> Callable[[], Any]:
    def visita() -> Any:
        raise erro

    return visita


@pytest.fixture
def montagem(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Montagem:
    # o erro do Playwright espera o `close` atrasado até `ESPERA_FECHAR_S`; sem tempo real aqui
    monkeypatch.setattr(limites, "ESPERA_FECHAR_S", 0.0)
    return Montagem(monkeypatch, tmp_path)


# ------------------------------------------------------------------ conferir_sessao


async def test_conferir_visita_a_entrada_sem_cola(montagem: Montagem) -> None:
    await montagem.conferir()
    assert len(montagem.visitas) == 1
    args, kwargs = montagem.visitas[0]
    assert args[1] == LEITOR.url_entrada
    assert args[2] is LEITOR
    assert "cola" not in kwargs


async def test_conferir_logado_da_conectado(montagem: Montagem) -> None:
    assert await montagem.conferir() == Conferencia("conectado", None)
    assert montagem.contexto.fechamentos == 1


async def test_conferir_sem_sessao_da_precisa_entrar(montagem: Montagem) -> None:
    montagem.visita = lambda: _captura("<form id='login'></form>")
    assert await montagem.conferir() == Conferencia("precisa_entrar", None)


async def test_perfil_em_uso_nao_abre(montagem: Montagem) -> None:
    montagem.em_uso = True
    assert await montagem.conferir() == Conferencia("nao_conferiu", "em_uso")
    assert montagem.aberturas == []


@pytest.mark.parametrize(
    ("erro", "motivo"), [(SemTela(), "sem_tela"), (SemNavegador(), "sem_navegador")]
)
async def test_sem_tela_e_sem_navegador(
    montagem: Montagem, erro: Exception, motivo: MotivoSessao
) -> None:
    montagem.erro_ao_abrir = erro
    assert await montagem.conferir() == Conferencia("nao_conferiu", motivo)
    assert montagem.visitas == []


async def test_erro_do_playwright_vira_sem_rede(montagem: Montagem) -> None:
    montagem.visita = _levanta(ErroDoPlaywright("net::ERR_CONNECTION_REFUSED"))
    assert await montagem.conferir() == Conferencia("nao_conferiu", "sem_rede")
    assert montagem.contexto.fechamentos == 1


async def test_fechar_a_janela_devolve_none(montagem: Montagem) -> None:
    def visita() -> Any:
        montagem.contexto.fechar_pela_pessoa()
        raise ErroDoPlaywright("Target page, context or browser has been closed")

    montagem.visita = visita
    assert await montagem.conferir() is None


async def test_outra_excecao_vira_erro_e_loga(
    montagem: Montagem, caplog: pytest.LogCaptureFixture
) -> None:
    montagem.visita = _levanta(RuntimeError("quebrou"))
    with caplog.at_level(logging.WARNING, logger="jobot.navegador.conferir"):
        assert await montagem.conferir() == Conferencia("nao_conferiu", "erro")
    registros = [r for r in caplog.records if r.name == "jobot.navegador.conferir"]
    assert len(registros) == 1
    assert registros[0].exc_info is not None
    assert LEITOR.chave in registros[0].getMessage()
    assert montagem.contexto.fechamentos == 1


async def test_prazo_estourado_vira_sem_rede_e_fecha(
    montagem: Montagem, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(limites, "PRAZO_CONFERIR_S", 0.01)
    nunca = asyncio.Event()

    async def espera() -> Visita:
        await nunca.wait()
        raise AssertionError("o evento nunca chega")

    montagem.visita = espera
    assert await montagem.conferir() == Conferencia("nao_conferiu", "sem_rede")
    assert montagem.contexto.fechamentos == 1


async def test_prazo_nao_cobre_a_abertura(
    montagem: Montagem, monkeypatch: pytest.MonkeyPatch
) -> None:
    # cancelar o launch no meio deixa um Chromium órfão com o SingletonLock
    monkeypatch.setattr(limites, "PRAZO_CONFERIR_S", 0.01)
    abrir_rapido = montagem._abrir_contexto

    async def abrir_devagar(dados: Path, ambiente: Any, lancar: Any) -> ContextoFalso:
        await asyncio.sleep(0.05)
        return await abrir_rapido(dados, ambiente, lancar)

    monkeypatch.setattr(conferir, "abrir_contexto", abrir_devagar)
    assert await montagem.conferir() == Conferencia("conectado", None)
    assert montagem.contexto.fechamentos == 1


# ------------------------------------------------------------------ "Fazer login agora"


@pytest.mark.parametrize(
    ("resultado", "esperado"),
    [
        ("pronto", ("conectado", None)),
        ("nao_entrou", ("precisa_entrar", None)),
        ("tempo_esgotado", ("precisa_entrar", None)),
        ("sem_tela", ("nao_conferiu", "sem_tela")),
        ("sem_navegador", ("nao_conferiu", "sem_navegador")),
        ("em_uso", ("nao_conferiu", "em_uso")),
    ],
)
def test_sessao_do_login_tabela(
    resultado: Resultado, esperado: tuple[EstadoSessao, MotivoSessao | None]
) -> None:
    assert sessao_do_login(resultado) == esperado


def test_intervalo_e_prazo_nos_limites() -> None:
    assert limites.INTERVALO_CONFERIR_S == 600
    assert limites.PRAZO_CONFERIR_S == 60
