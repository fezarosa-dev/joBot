"""Grupo "Ferramentas" em Configurações: baixar e remover o navegador (T240; D137.4 a D137.14).

O processo do instalador e a leitura do navegador entram por `app.state` (`abrir_processo` e
`ler_navegador`); nada baixa de verdade e nenhum teste espera tempo real fixo.
"""

import asyncio
import html as html_lib
import re
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apoio.relogio import RelogioFalso
from apoio.site_falso import LeitorFalso
from jobot.banco import cadastros
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.navegador.instalador import (
    comando_de_baixar,
    comando_de_baixar_pela_casca,
    comando_de_remover,
)
from jobot.painel import i18n
from jobot.painel.app import criar_app
from jobot.painel.seguranca import CAMPO_CSRF

PORTA = 47623
BASE = f"http://127.0.0.1:{PORTA}"
GRUPO = "/configuracoes/ferramentas"
NAVEGADOR = f"{GRUPO}/navegador"
BAIXAR = f"{NAVEGADOR}/baixar"
REMOVER = f"{NAVEGADOR}/remover"
AGORA = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)


class ProcessoFalso:
    """Como o `LoginFalso`: o `wait()` só volta quando o teste libera (prazo de 5 s)."""

    def __init__(self) -> None:
        self.liberar = threading.Event()
        self.codigo = 0
        self.sinais: list[str] = []

    async def wait(self) -> int:
        for _ in range(500):
            if self.liberar.is_set():
                return self.codigo
            await asyncio.sleep(0.01)
        raise AssertionError("o teste não liberou o instalador")

    def terminate(self) -> None:
        self.sinais.append("terminate")

    def kill(self) -> None:
        self.sinais.append("kill")


class Painel:
    """App sobre um banco migrado, com o leitor do site falso e os falsos do instalador."""

    def __init__(self, tmp_path: Path, *, com_leitor: bool = True) -> None:
        self.banco = tmp_path / "jobot.db"
        leitor = LeitorFalso(base="http://127.0.0.1:9")
        with closing(abrir(self.banco)) as con:
            migrar(con, self.banco)
            cadastros.semear(con)
            cadastros.semear_leitores(con, [leitor])
        self.app = criar_app(tmp_path, PORTA)
        self.app.state.relogio = RelogioFalso(AGORA)
        self.app.state.leitores = (leitor,) if com_leitor else ()
        self.processo = ProcessoFalso()
        self.abertos: list[tuple[list[str], dict[str, str]]] = []
        self.erro_ao_abrir: Exception | None = None
        self.no_disco: str | None = None  # o que o `ler_navegador` falso acha depois
        self.app.state.abrir_processo = self._abrir
        self.app.state.ler_navegador = self._ler
        self.http = TestClient(self.app, base_url=BASE, follow_redirects=False)
        self.token: str = self.app.state.csrf

    async def _abrir(self, argumentos: Sequence[str], ambiente: Mapping[str, str]) -> Any:
        if self.erro_ao_abrir is not None:
            raise self.erro_ao_abrir
        self.abertos.append((list(argumentos), dict(ambiente)))
        return self.processo

    async def _ler(self) -> str | None:
        return self.no_disco

    def navegador(self, valor: str | None) -> None:
        self.app.state.navegador_instalado = valor
        self.no_disco = valor

    def idioma(self, idioma: str) -> None:
        with closing(abrir(self.banco)) as con:
            con.execute(
                "INSERT INTO config (chave, valor) VALUES ('idioma', ?)"
                " ON CONFLICT (chave) DO UPDATE SET valor = excluded.valor",
                (f'"{idioma}"',),
            )
            con.commit()

    def post(self, url: str, http: TestClient | None = None) -> Any:
        return (http or self.http).post(url, data={CAMPO_CSRF: self.token})

    def resultado(self) -> str | None:
        valor: str | None = getattr(self.app.state, "ferramentas", {}).get("navegador")
        return valor


@pytest.fixture
def painel(tmp_path: Path) -> Painel:
    return Painel(tmp_path)


@pytest.fixture
def sem_leitor(tmp_path: Path) -> Painel:
    return Painel(tmp_path, com_leitor=False)


def _texto(html: str) -> str:
    sem_tags = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html_lib.unescape(sem_tags))


def _t(chave: str, idioma: str = "pt") -> str:
    return i18n.carregar()[idioma][f"configuracoes.ferramentas.{chave}"]


def _esperar(condicao: Callable[[], bool], s: float = 5.0) -> bool:
    fim = time.monotonic() + s
    while not condicao():
        if time.monotonic() >= fim:
            return False
        time.sleep(0.01)
    return True


def _livre(painel: Painel) -> bool:
    """A trava do navegador não existe ou está solta."""
    trava = getattr(painel.app.state, "travas", {}).get("navegador")
    return trava is None or not trava.locked()


def _trava_presa(painel: Painel, nome: str = "login") -> asyncio.Lock:
    trava = asyncio.Lock()
    asyncio.run(trava.acquire())
    painel.app.state.travas = {nome: trava}
    return trava


# ------------------------------------------------------------------ o grupo


def test_ferramentas_some_sem_leitor(painel: Painel, sem_leitor: Painel) -> None:
    resposta = sem_leitor.http.get(GRUPO)  # grupo guardado que sumiu: Geral (T308)
    assert (resposta.status_code, resposta.headers.get("location")) == (
        303,
        "/configuracoes/geral",
    )
    assert f'href="{GRUPO}"' not in sem_leitor.http.get("/configuracoes/fontes").text
    assert f'href="{GRUPO}"' in painel.http.get("/configuracoes/fontes").text
    assert painel.http.get(GRUPO).status_code == 200


def test_ferramentas_e_o_ultimo_grupo(painel: Painel) -> None:
    abas = re.findall(r'href="(/configuracoes/[^"/]+)"', painel.http.get(GRUPO).text)
    assert abas[-1] == GRUPO


def test_post_no_grupo_ferramentas_da_405(painel: Painel) -> None:
    http = TestClient(
        painel.app, base_url=BASE, follow_redirects=False, raise_server_exceptions=False
    )
    assert http.post(GRUPO, data={CAMPO_CSRF: painel.token}).status_code == 405


@pytest.mark.parametrize("achado", [None, "chrome", "chromium"])
def test_botao_baixar_so_sem_navegador(painel: Painel, achado: str | None) -> None:
    painel.navegador(achado)
    html = painel.http.get(GRUPO).text
    assert (BAIXAR in html) is (achado is None)


def test_com_chrome_sem_baixar_nem_remover(painel: Painel) -> None:
    painel.navegador("chrome")
    html = painel.http.get(GRUPO).text
    assert _t("estado.chrome") in _texto(html)
    assert BAIXAR not in html and REMOVER not in html


def test_nenhum_recurso_externo_nem_terminal(painel: Painel) -> None:
    painel.navegador(None)
    html = painel.http.get(GRUPO).text
    assert re.findall(r'(?:\ssrc|<link\b[^>]*\shref)="https?://', html) == []
    assert "terminal" not in html and "playwright install" not in html


# ------------------------------------------------------------------ baixar


def test_baixar_mostra_baixando_e_depois_instalado(painel: Painel) -> None:
    painel.navegador(None)
    with TestClient(painel.app, base_url=BASE) as http:
        resposta = painel.post(BAIXAR, http)
        assert resposta.status_code == 200
        assert _t("estado.baixando") in _texto(resposta.text)
        assert _t("dica_baixando") in _texto(resposta.text)
        assert 'hx-trigger="every 5s"' in resposta.text
        assert _esperar(lambda: len(painel.abertos) == 1)
        assert painel.abertos[0][0] == comando_de_baixar()
        assert http.get(NAVEGADOR).status_code == 204
        painel.no_disco = "chromium"
        painel.processo.liberar.set()
        assert _esperar(lambda: painel.resultado() == "pronto")
        final = http.get(NAVEGADOR)
        assert final.status_code == 200
        assert _t("aviso.pronto") in _texto(final.text)
        assert REMOVER in final.text
        assert 'hx-trigger="every 5s"' not in final.text
        assert painel.app.state.navegador_instalado == "chromium"


@pytest.mark.parametrize("canal", ["casca", "outro", "quebrado"])
def test_baixar_no_canal_casca_usa_a_release(painel: Painel, tmp_path: Path, canal: str) -> None:
    """Canal `casca`: o subcomando da T330 (caminho b), com a pasta de dados; fora dele, ou com o
    `instalacao.json` quebrado, o `playwright install` de sempre (caminho c)."""
    conteudo = {"casca": '{"canal": "casca", "manifesto": "/m.json"}', "outro": '{"canal": "x"}'}
    (tmp_path / "instalacao.json").write_text(conteudo.get(canal, "{"))
    painel.navegador(None)
    with TestClient(painel.app, base_url=BASE) as http:
        assert painel.post(BAIXAR, http).status_code == 200
        assert _esperar(lambda: len(painel.abertos) == 1)
        argumentos, ambiente = painel.abertos[0]
        painel.processo.liberar.set()
    if canal == "casca":
        assert argumentos == comando_de_baixar_pela_casca()
        assert ambiente["JOBOT_DADOS"] == str(tmp_path)
    else:
        assert argumentos == comando_de_baixar()
        assert "JOBOT_DADOS" not in ambiente


@pytest.mark.parametrize("resultado", ["pronto", "falhou_baixar", "removido"])
def test_resultado_terminal_so_aparece_uma_vez(painel: Painel, resultado: str) -> None:
    painel.navegador("chromium" if resultado == "pronto" else None)
    painel.app.state.ferramentas = {"navegador": resultado}
    primeiro = painel.http.get(NAVEGADOR)
    assert primeiro.status_code == 200
    assert _t(f"aviso.{resultado}") in _texto(primeiro.text)
    segundo = painel.http.get(NAVEGADOR)
    assert _t(f"aviso.{resultado}") not in _texto(segundo.text)
    estado = "instalado" if resultado == "pronto" else "nao_instalado"
    assert _t(f"estado.{estado}") in _texto(segundo.text)
    assert "navegador" not in getattr(painel.app.state, "ferramentas", {})


def test_baixando_nao_se_apaga(painel: Painel) -> None:
    painel.app.state.ferramentas = {"navegador": "baixando"}
    assert painel.http.get(NAVEGADOR).status_code == 204
    assert painel.resultado() == "baixando"


def test_baixar_sem_navegador_no_disco_falha(painel: Painel) -> None:
    painel.navegador(None)
    painel.processo.liberar.set()  # o instalador sai com 0, mas não há navegador no disco
    with TestClient(painel.app, base_url=BASE) as http:
        assert painel.post(BAIXAR, http).status_code == 200
        assert _esperar(lambda: painel.resultado() == "falhou_baixar")
    assert painel.abertos


@pytest.mark.parametrize("achado", ["chrome", "chromium"])
def test_post_com_navegador_nao_baixa(painel: Painel, achado: str) -> None:
    painel.navegador(achado)
    painel.processo.liberar.set()
    with TestClient(painel.app, base_url=BASE) as http:
        assert painel.post(BAIXAR, http).status_code == 200
        assert painel.abertos == []
        assert painel.resultado() is None
        painel.navegador(None)  # controle: a mesma montagem sem navegador abre o instalador
        painel.post(BAIXAR, http)
        assert _esperar(lambda: len(painel.abertos) == 1)


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_baixar_falhou_mostra_o_que_fazer(painel: Painel, idioma: str) -> None:
    painel.idioma(idioma)
    painel.navegador(None)
    painel.processo.codigo = 1
    painel.processo.liberar.set()
    with TestClient(painel.app, base_url=BASE) as http:
        assert painel.post(BAIXAR, http).status_code == 200
        assert _esperar(lambda: painel.resultado() == "falhou_baixar")
        html = http.get(NAVEGADOR).text
    texto = _texto(html)
    assert _t("aviso.falhou_baixar", idioma) in texto
    if idioma == "pt":
        assert "Confira a internet" in texto
    assert "jobot.log" in texto
    assert _t("estado.falhou", idioma) in texto
    assert BAIXAR in html
    assert "terminal" not in texto and "playwright install" not in texto


def test_erro_inesperado_vira_falhou(painel: Painel) -> None:
    painel.navegador(None)
    painel.erro_ao_abrir = RuntimeError("quebrou")
    with TestClient(painel.app, base_url=BASE) as http:
        assert painel.post(BAIXAR, http).status_code == 200
        assert _esperar(lambda: painel.resultado() == "falhou_baixar")
        assert _esperar(lambda: _livre(painel))


def test_um_download_por_vez(painel: Painel) -> None:
    painel.navegador(None)
    with TestClient(painel.app, base_url=BASE) as http:
        painel.post(BAIXAR, http)
        assert _esperar(lambda: len(painel.abertos) == 1)
        segundo = painel.post(BAIXAR, http)
        assert len(painel.abertos) == 1
        assert _t("estado.baixando") in _texto(segundo.text)
        painel.processo.liberar.set()
        assert _esperar(lambda: _livre(painel))
    assert len(painel.abertos) == 1


# ------------------------------------------------------------------ remover


def test_remover_mostra_removendo_e_depois_removido(painel: Painel) -> None:
    painel.navegador("chromium")
    with TestClient(painel.app, base_url=BASE) as http:
        resposta = painel.post(REMOVER, http)
        assert _t("estado.removendo") in _texto(resposta.text)
        assert _esperar(lambda: len(painel.abertos) == 1)
        assert painel.abertos[0][0] == comando_de_remover()
        travas = painel.app.state.travas
        assert travas["navegador"].locked() and travas["login"].locked()
        painel.no_disco = None
        painel.processo.liberar.set()
        assert _esperar(lambda: painel.resultado() == "removido")
        final = http.get(NAVEGADOR)
        assert _t("aviso.removido") in _texto(final.text)
        assert BAIXAR in final.text
        assert _esperar(lambda: _livre(painel))
        assert not travas["login"].locked()


def test_remover_que_outro_usa_continua(painel: Painel) -> None:
    painel.navegador("chromium")  # o `ler_navegador` continua achando o Chromium
    painel.processo.liberar.set()
    with TestClient(painel.app, base_url=BASE) as http:
        painel.post(REMOVER, http)
        assert _esperar(lambda: painel.resultado() == "continua")
        assert _t("aviso.continua") in _texto(http.get(NAVEGADOR).text)


def test_remover_com_login_rodando_nao_remove(painel: Painel) -> None:
    painel.navegador("chromium")
    trava = _trava_presa(painel)
    resposta = painel.post(REMOVER)
    assert painel.abertos == []
    assert _t("aviso.em_uso") in _texto(resposta.text)
    assert "navegador" not in getattr(painel.app.state, "ferramentas", {})
    trava.release()  # controle: com a trava livre o mesmo POST abre o processo
    painel.processo.liberar.set()
    with TestClient(painel.app, base_url=BASE) as http:
        painel.post(REMOVER, http)
        assert _esperar(lambda: len(painel.abertos) == 1)


@pytest.mark.parametrize("achado", [None, "chrome"])
def test_remover_sem_chromium_nao_remove(painel: Painel, achado: str | None) -> None:
    painel.navegador(achado)
    painel.processo.liberar.set()
    with TestClient(painel.app, base_url=BASE) as http:
        painel.post(REMOVER, http)
        assert painel.abertos == []
        painel.navegador("chromium")  # controle: com o Chromium do Playwright, remove
        painel.post(REMOVER, http)
        assert _esperar(lambda: len(painel.abertos) == 1)


@pytest.mark.parametrize(
    ("metodo", "rota"), [("GET", NAVEGADOR), ("POST", BAIXAR), ("POST", REMOVER)]
)
def test_ferramentas_sem_leitor_da_404(sem_leitor: Painel, metodo: str, rota: str) -> None:
    sem_leitor.navegador("chromium" if rota == REMOVER else None)
    if metodo == "GET":
        assert sem_leitor.http.get(rota).status_code == 404
    else:
        assert sem_leitor.post(rota).status_code == 404
    assert sem_leitor.abertos == []


# ------------------------------------------------------------------ textos


_PREFIXO = "configuracoes.ferramentas."
_SEM_PROCESSO = {"instalado", "nao_instalado", "chrome", "falhou"}


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_estados_em_pt_e_en(painel: Painel, idioma: str) -> None:
    catalogo = i18n.carregar()[idioma]
    estados = sorted(
        c.removeprefix(_PREFIXO + "estado.") for c in catalogo if c.startswith(_PREFIXO + "estado.")
    )
    avisos = sorted(
        c.removeprefix(_PREFIXO + "aviso.") for c in catalogo if c.startswith(_PREFIXO + "aviso.")
    )
    assert estados and avisos
    painel.idioma(idioma)
    vistos: dict[str, str] = {}

    for estado in estados:
        if estado in ("baixando", "removendo"):
            processo = ProcessoFalso()
            painel.processo = processo
            painel.navegador(None if estado == "baixando" else "chromium")
            with TestClient(painel.app, base_url=BASE) as http:
                vistos[estado] = _texto(
                    painel.post(BAIXAR if estado == "baixando" else REMOVER, http).text
                )
                processo.liberar.set()
                assert _esperar(lambda: _livre(painel))
            if estado == "baixando":
                assert catalogo[_PREFIXO + "dica_baixando"] in vistos[estado]
            painel.app.state.ferramentas = {}
            continue
        assert estado in _SEM_PROCESSO, f"estado novo sem tratamento no teste: {estado}"
        painel.navegador({"instalado": "chromium", "chrome": "chrome"}.get(estado))
        if estado == "falhou":
            painel.app.state.ferramentas = {"navegador": "falhou_baixar"}
        vistos[estado] = _texto(painel.http.get(NAVEGADOR).text)

    for estado, texto in vistos.items():
        assert catalogo[_PREFIXO + "estado." + estado] in texto, estado

    for aviso in avisos:
        if aviso == "em_uso":
            painel.navegador("chromium")
            trava = _trava_presa(painel)
            texto = _texto(painel.post(REMOVER).text)
            trava.release()
        else:
            painel.navegador("chromium" if aviso in ("pronto", "continua") else None)
            painel.app.state.ferramentas = {"navegador": aviso}
            texto = _texto(painel.http.get(NAVEGADOR).text)
        assert catalogo[_PREFIXO + "aviso." + aviso] in texto, aviso


# o passo dos sites do assistente mostra o navegador e os cartões juntos (D166): quando o
# navegador muda, a resposta final leva os cartões em OOB, com o "Fazer login agora" atualizado
ASSISTENTE = {"HX-Request": "true", "HX-Current-URL": f"{BASE}/primeira-execucao/sites?busca=1"}
NA_ABA = {"HX-Request": "true", "HX-Current-URL": f"{BASE}{GRUPO}"}
LOGIN_DO_SITE = "/configuracoes/contas/falso_logado/login"


def _cartoes_oob(html: str) -> str | None:
    achado = re.search(r'<div\b[^>]*\bid="contas-sites"[^>]*>', html)
    if achado is None:
        return None
    assert 'hx-swap-oob="outerHTML:#contas-sites"' in achado[0]
    return html[achado.start() :]


def _botao_de_login(html: str) -> str:
    botao = re.search(rf'<button\b[^>]*hx-post="{LOGIN_DO_SITE}"[^>]*>', html)
    assert botao is not None, "sem o botão Fazer login agora"
    return botao[0]


def test_baixar_no_assistente_liga_o_login_dos_cartoes(painel: Painel) -> None:
    painel.navegador(None)
    with TestClient(painel.app, base_url=BASE) as http:
        painel.post(BAIXAR, http)
        assert _esperar(lambda: len(painel.abertos) == 1)
        painel.no_disco = "chromium"
        painel.processo.liberar.set()
        assert _esperar(lambda: painel.resultado() == "pronto")
        final = http.get(NAVEGADOR, headers=ASSISTENTE)
        assert final.status_code == 200
        oob = _cartoes_oob(final.text)
        assert oob is not None, "a resposta final não trouxe os cartões"
        botao = _botao_de_login(oob)
        assert "disabled" not in botao.replace("hx-disabled-elt", "")
        assert "aria-describedby" not in botao
        assert 'id="contas-sem-navegador"' not in oob
        # controle: na aba Ferramentas não há cartões para trocar
        assert _cartoes_oob(http.get(NAVEGADOR, headers=NA_ABA).text) is None


def test_remover_no_assistente_desliga_o_login_dos_cartoes(painel: Painel) -> None:
    painel.navegador("chromium")
    with TestClient(painel.app, base_url=BASE) as http:
        painel.post(REMOVER, http)
        assert _esperar(lambda: len(painel.abertos) == 1)
        painel.no_disco = None
        painel.processo.liberar.set()
        assert _esperar(lambda: painel.resultado() == "removido")
        oob = _cartoes_oob(http.get(NAVEGADOR, headers=ASSISTENTE).text)
        assert oob is not None, "a resposta final não trouxe os cartões"
        botao = _botao_de_login(oob)
        assert re.search(r"\sdisabled[\s>]", botao)
        assert 'aria-describedby="contas-sem-navegador"' in botao
        frase = re.search(r'<p\b[^>]*\bid="contas-sem-navegador"[^>]*>([^<]*)</p>', oob)
        assert frase is not None and "baixe o navegador acima" in frase[1]
