"""Grupo "Ferramentas" em Configurações: baixar e remover o navegador (T240; D137.4 a D137.14) e
o modelo local (T417; desenho 10.2 da fase 4; D185.20).

O processo do instalador, a leitura do navegador e o `jobot ferramentas ... ia-local` entram por
`app.state` (`abrir_processo`, `ler_navegador` e `abrir_ia_local`); nada baixa de verdade e
nenhum teste espera tempo real fixo.
"""

import asyncio
import html as html_lib
import json
import re
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, get_args

import pytest
from fastapi.testclient import TestClient

import jobot.cli
from apoio.comando_falso import AbrirFalso, ComandoFalso
from apoio.relogio import RelogioFalso
from apoio.site_falso import LeitorFalso
from jobot.banco import cadastros
from jobot.banco.cadastros import gravar_config, ler_config
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.navegador.instalador import (
    comando_de_baixar,
    comando_de_remover,
)
from jobot.nucleo.ia.contrato import Pedido, Resposta, conferir
from jobot.painel import i18n
from jobot.painel.app import criar_app
from jobot.painel.rotas.configuracoes import MOTIVOS_IA, argumentos_ia_local
from jobot.painel.seguranca import CAMPO_CSRF
from jobot.sistema import casca, ia_local
from jobot.sistema.baixar import Motivo

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
        self.dados = tmp_path
        self.abrir_ia = AbrirFalso()
        self.app.state.abrir_ia_local = self.abrir_ia
        self.http = TestClient(self.app, base_url=BASE, follow_redirects=False)
        self.token: str = self.app.state.csrf

    async def _abrir(self, argumentos: Sequence[str], ambiente: Mapping[str, str]) -> Any:
        if self.erro_ao_abrir is not None:
            raise self.erro_ao_abrir
        self.abertos.append((list(argumentos), dict(ambiente)))
        return self.processo

    async def _ler(self) -> str | None:
        return self.no_disco

    @property
    def comando(self) -> ComandoFalso:
        return self.abrir_ia.comando

    @comando.setter
    def comando(self, comando: ComandoFalso) -> None:
        self.abrir_ia.comando = comando

    @property
    def comandos(self) -> list[tuple[list[str], Path]]:
        return self.abrir_ia.comandos

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


def test_ferramentas_sem_leitor_so_com_o_modelo_local(painel: Painel, sem_leitor: Painel) -> None:
    """Desenho 10.2 da fase 4 (D185.20): a aba fica sem leitor; o cartão do navegador, não."""
    resposta = sem_leitor.http.get(GRUPO)
    assert resposta.status_code == 200
    assert 'id="ferramenta-ia-local"' in resposta.text
    assert 'id="ferramenta-navegador"' not in resposta.text
    assert f'href="{GRUPO}"' in sem_leitor.http.get("/configuracoes/fontes").text
    com_leitor = painel.http.get(GRUPO).text  # controle: com leitor vêm os dois cartões
    assert 'id="ferramenta-navegador"' in com_leitor
    assert 'id="ferramenta-ia-local"' in com_leitor


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
def test_baixar_e_o_playwright_install_em_todo_canal(
    painel: Painel, tmp_path: Path, canal: str
) -> None:
    """O joBot não redistribui o navegador (D183.24): no canal `casca` também, o `playwright
    install` de sempre (o caminho c da T330), sem a release do joBot."""
    conteudo = {"casca": '{"canal": "casca", "manifesto": "/m.json"}', "outro": '{"canal": "x"}'}
    (tmp_path / "instalacao.json").write_text(conteudo.get(canal, "{"))
    painel.navegador(None)
    with TestClient(painel.app, base_url=BASE) as http:
        assert painel.post(BAIXAR, http).status_code == 200
        assert _esperar(lambda: len(painel.abertos) == 1)
        argumentos, ambiente = painel.abertos[0]
        painel.processo.liberar.set()
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


# ------------------------------------------- navegador desatualizado (T331; D174.13)


def _desatualizado(painel: Painel, marca: bool) -> None:
    pasta = painel.banco.parent / "app"
    casca.gravar_instalacao(
        painel.banco.parent,
        {
            "canal": "casca",
            "pasta": str(pasta),
            "uv": str(pasta / "bin" / "uv"),
            "venv": str(pasta / "venvs" / "venv-9.9.9"),
            "manifesto": str(pasta / "manifesto-9.9.9.json"),
            "navegador_desatualizado": marca,
        },
    )


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_navegador_desatualizado_mostra_o_aviso_e_baixar(painel: Painel, idioma: str) -> None:
    painel.idioma(idioma)
    painel.navegador("chromium")
    _desatualizado(painel, False)  # controle: sem a marca, só o Remover
    html = painel.http.get(GRUPO).text
    assert _t("navegador.desatualizado", idioma) not in _texto(html)
    assert BAIXAR not in html and REMOVER in html
    _desatualizado(painel, True)
    html = painel.http.get(GRUPO).text
    assert _t("navegador.desatualizado", idioma) in _texto(html)
    assert BAIXAR in html and REMOVER in html  # quem só quer tirar o velho ainda acha o Remover


def test_baixar_o_desatualizado_baixa_e_tira_a_marca(painel: Painel) -> None:
    painel.navegador("chromium")
    _desatualizado(painel, True)
    with TestClient(painel.app, base_url=BASE) as http:
        assert painel.post(BAIXAR, http).status_code == 200
        assert _esperar(lambda: len(painel.abertos) == 1)
        assert casca.navegador_desatualizado(painel.banco.parent)  # só sai depois do pronto
        painel.processo.liberar.set()
        assert _esperar(lambda: painel.resultado() == "pronto")
    assert not casca.navegador_desatualizado(painel.banco.parent)
    assert casca.ler_instalacao(painel.banco.parent)["venv"].endswith("venv-9.9.9")


@pytest.mark.parametrize("achado", [None, "chrome"])
def test_marca_sem_chromium_nao_diz_desatualizado(painel: Painel, achado: str | None) -> None:
    painel.navegador(achado)
    _desatualizado(painel, True)
    assert _t("navegador.desatualizado") not in _texto(painel.http.get(GRUPO).text)
    painel.navegador("chromium")  # controle: a mesma marca com o Chromium aparece
    assert _t("navegador.desatualizado") in _texto(painel.http.get(GRUPO).text)


# ------------------------------------------------------------------ modelo local (T417)


IA_LOCAL = f"{GRUPO}/ia-local"
HTMX = {"HX-Request": "true"}
MANIFESTO = ia_local.manifesto_local()
MODELOS = MANIFESTO["modelos"]
SERVIDOR = MANIFESTO["llama_server"]


def _ia(chave: str, idioma: str = "pt", **params: object) -> str:
    return i18n.carregar()[idioma][f"configuracoes.ferramentas.ia_local.{chave}"].format(**params)


def _anotar(painel: Painel, chave: str, *, sem: object = None, **mudar: object) -> None:
    """A anotação que o `jobot ferramentas baixar ia-local` deixa, com o manifesto de hoje, e os
    dois arquivos que ela aponta (menos o de `sem`: `programa` ou `modelo`)."""
    alvo = SERVIDOR["alvos"]["ubuntu-x64"]
    programa = f"llama/{SERVIDOR['build']}/llama-server"
    anotacao = {
        "build": SERVIDOR["build"],
        "alvo": "ubuntu-x64",
        "programa": programa,
        "servidor_sha256": alvo["sha256"],
        "modelo": chave,
        "arquivo": MODELOS[chave]["arquivo"],
        "modelo_sha256": MODELOS[chave]["sha256"],
    } | mudar
    pasta = painel.dados / "ferramentas"
    arquivos = {
        "programa": pasta / programa,
        "modelo": pasta / "modelos" / MODELOS[chave]["arquivo"],
    }
    for nome, arquivo in arquivos.items():
        if nome != sem:
            arquivo.parent.mkdir(parents=True, exist_ok=True)
            arquivo.write_bytes(b"x")
    (pasta / ia_local.ANOTACAO).write_text(json.dumps(anotacao))


def _tarefas(painel: Painel, valor: object = None) -> Any:
    with closing(abrir(painel.banco)) as con:
        if valor is not None:
            gravar_config(con, "ia_tarefas", valor)
        return ler_config(con, "ia_tarefas")


def _post_ia(painel: Painel, acao: str, http: TestClient) -> Any:
    return http.post(f"{IA_LOCAL}/{acao}", data={CAMPO_CSRF: painel.token}, headers=HTMX)


def _ia_livre(painel: Painel) -> bool:
    trava = getattr(painel.app.state, "travas", {}).get("ia_local")
    return trava is None or not trava.locked()


def _acoes_ia(html: str) -> list[str]:
    return re.findall(rf'<form method="post" action="{IA_LOCAL}/([a-z]+)"', html)


def test_modelo_local_nao_baixado_mostra_tamanho_e_baixar(sem_leitor: Painel) -> None:
    html = sem_leitor.http.get(GRUPO).text
    texto = _texto(html)
    assert _ia("estado.nao_baixado") in texto
    assert _ia("tamanho", menor="1,3 GB", maior="2,7 GB") in texto
    assert _acoes_ia(html) == ["baixar"]
    formulario = html[html.index(f'action="{IA_LOCAL}/baixar"') :]
    assert f'name="{CAMPO_CSRF}" value="{sem_leitor.token}"' in formulario.split("</form>")[0]


@pytest.mark.parametrize(("chave", "outro"), [("4b", "2b"), ("2b", "4b")])
def test_baixado_mostra_modelo_tamanho_licenca_e_origem(
    sem_leitor: Painel, chave: str, outro: str
) -> None:
    _anotar(sem_leitor, chave)
    html = sem_leitor.http.get(GRUPO).text
    texto = _texto(html)
    modelo, alvo = MODELOS[chave], SERVIDOR["alvos"]["ubuntu-x64"]
    tamanho = {"2b": "1,3 GB", "4b": "2,7 GB"}
    assert _ia("estado.baixado") in texto
    assert _ia("modelo", nome=modelo["nome"], tamanho=tamanho[chave]) in texto
    assert _ia("licenca", licenca=modelo["licenca"]) in texto
    assert _ia("origem", origem=modelo["origem"]) in texto
    assert _ia("programa", build=SERVIDOR["build"]) in texto
    assert _ia("licenca", licenca=alvo["licenca"]) in texto
    assert _ia("origem", origem=alvo["origem"]) in texto
    assert _ia("trocar", nome=MODELOS[outro]["nome"], tamanho=tamanho[outro]) in texto
    assert _acoes_ia(html) == ["trocar", "remover"]
    assert _ia("desatualizado") not in texto


def test_baixar_tem_barra_por_bytes_e_depois_pronto(sem_leitor: Painel) -> None:
    painel = sem_leitor
    painel.comando.antes = [
        {"memoria": 8 << 30, "modelo": "4b", "lento": False},
        {"etapa": "ia_local", "feito": 250, "total": 1000},
    ]
    with TestClient(painel.app, base_url=BASE) as http:
        resposta = _post_ia(painel, "baixar", http)
        assert resposta.status_code == 200
        assert _ia("estado.baixando") in _texto(resposta.text)
        assert 'hx-trigger="every 5s"' in resposta.text
        assert re.search(r"<progress\b[^>]*aria-label=", resposta.text)
        assert _esperar(lambda: 'value="250"' in http.get(IA_LOCAL, headers=HTMX).text)
        andando = http.get(IA_LOCAL, headers=HTMX).text
        assert re.search(r'<progress\b[^>]*max="1000" value="250"', andando)
        assert _ia("andamento", pct=25) in _texto(andando)
        assert _acoes_ia(andando) == []  # nada de botão enquanto roda
        _anotar(painel, "4b")  # o comando anota o que baixou antes do `fim`
        painel.comando.liberar.set()
        assert _esperar(lambda: _ia_livre(painel))
        final = http.get(IA_LOCAL, headers=HTMX).text
        assert _ia("aviso.pronto") in _texto(final)
        assert _ia("estado.baixado") in _texto(final)
        assert "<progress" not in final and 'hx-trigger="every 5s"' not in final
        assert _ia("aviso.pronto") not in _texto(http.get(IA_LOCAL, headers=HTMX).text)
    assert painel.comandos == [(["baixar", "ia-local"], painel.dados)]


def test_trocar_baixa_o_outro_e_leva_as_tarefas_locais(sem_leitor: Painel) -> None:
    painel = sem_leitor
    _anotar(painel, "4b")
    local = {"ligada": True, "backend": "local", "modelo": MODELOS["4b"]["nome"]}
    _tarefas(painel, {"encaixe": local})
    with TestClient(painel.app, base_url=BASE) as http:
        assert _post_ia(painel, "trocar", http).status_code == 200
        _anotar(painel, "2b")
        painel.comando.liberar.set()
        assert _esperar(lambda: _ia_livre(painel))
    assert painel.comandos == [(["baixar", "ia-local", "--modelo", "2b"], painel.dados)]
    assert _tarefas(painel) == {"encaixe": local | {"modelo": MODELOS["2b"]["nome"]}}


class _FabricaIA:
    """`app.state.ia` falsa (teste ao ligar, T416): anota os pares e responde no formato."""

    def __init__(self) -> None:
        self.pares: list[tuple[str, str]] = []

    def __call__(self, backend: str, modelo: str) -> _FabricaIA:
        self.pares.append((backend, modelo))
        return self

    def pedir(self, pedido: Pedido) -> Resposta:
        return conferir(pedido, {"pede": ["Python"]}, "local")

    def fechar(self) -> None:
        pass


def test_trocar_testa_o_modelo_novo_das_tarefas_ligadas(sem_leitor: Painel) -> None:
    """O par (local, modelo) mudou com as tarefas ligadas: o teste ao ligar roda no novo, com o
    laço esperando por ele (T416, desenho 6.1)."""
    painel = sem_leitor
    _anotar(painel, "4b")
    local = {"ligada": True, "backend": "local", "modelo": MODELOS["4b"]["nome"]}
    _tarefas(painel, {"encaixe": local})
    fabrica = _FabricaIA()
    painel.app.state.ia = fabrica
    painel.app.state.ia_pessoa = set()
    painel.app.state.ia_acordar = asyncio.Event()
    novo = ("local", MODELOS["2b"]["nome"])
    with TestClient(painel.app, base_url=BASE) as http:
        assert _post_ia(painel, "trocar", http).status_code == 200
        _anotar(painel, "2b")
        painel.comando.liberar.set()
        assert _esperar(lambda: _ia_livre(painel))
        assert _esperar(lambda: not getattr(painel.app.state, "ia_fila", []))
        assert fabrica.pares == [novo]
        assert painel.app.state.ia_testes[novo].estado == "ok"
        assert painel.app.state.ia_acordar.is_set()
        assert painel.app.state.ia_pessoa == set()


def test_trocar_sem_tarefa_ligada_nao_testa(sem_leitor: Painel) -> None:
    painel = sem_leitor
    _anotar(painel, "4b")
    local = {"ligada": False, "backend": "local", "modelo": MODELOS["4b"]["nome"]}
    _tarefas(painel, {"encaixe": local})
    fabrica = _FabricaIA()
    painel.app.state.ia = fabrica
    with TestClient(painel.app, base_url=BASE) as http:
        assert _post_ia(painel, "trocar", http).status_code == 200
        _anotar(painel, "2b")
        painel.comando.liberar.set()
        assert _esperar(lambda: _ia_livre(painel))
    assert fabrica.pares == []
    assert _tarefas(painel) == {"encaixe": local | {"modelo": MODELOS["2b"]["nome"]}}


@pytest.mark.parametrize(
    "mudar",
    [
        {"build": "b1"},
        {"servidor_sha256": "0" * 64},
        {"modelo_sha256": "0" * 64},
    ],
)
def test_atualizar_quando_o_manifesto_mudou(sem_leitor: Painel, mudar: dict[str, str]) -> None:
    painel = sem_leitor
    _anotar(painel, "2b", **mudar)
    html = painel.http.get(GRUPO).text
    assert _ia("desatualizado") in _texto(html)
    assert _acoes_ia(html) == ["atualizar", "trocar", "remover"]
    with TestClient(painel.app, base_url=BASE) as http:
        assert _post_ia(painel, "atualizar", http).status_code == 200
        painel.comando.liberar.set()
        assert _esperar(lambda: _ia_livre(painel))
    assert painel.comandos == [(["atualizar", "ia-local"], painel.dados)]


def test_sem_mudanca_no_manifesto_nao_atualiza(sem_leitor: Painel) -> None:
    """(guarda) O manifesto de hoje não oferece nem roda o Atualizar."""
    painel = sem_leitor
    _anotar(painel, "2b")
    assert "atualizar" not in _acoes_ia(painel.http.get(GRUPO).text)
    with TestClient(painel.app, base_url=BASE) as http:
        assert _post_ia(painel, "atualizar", http).status_code == 200
        assert painel.comandos == []
        _anotar(painel, "2b", build="b1")  # controle: com o manifesto mudado, roda
        _post_ia(painel, "atualizar", http)
        painel.comando.liberar.set()
        assert _esperar(lambda: _ia_livre(painel))
    assert painel.comandos == [(["atualizar", "ia-local"], painel.dados)]


def test_remover_desliga_as_tarefas_no_local(sem_leitor: Painel) -> None:
    painel = sem_leitor
    _anotar(painel, "2b")
    local = {"ligada": True, "backend": "local", "modelo": MODELOS["2b"]["nome"]}
    _tarefas(painel, {"encaixe": local})
    with TestClient(painel.app, base_url=BASE) as http:
        resposta = _post_ia(painel, "remover", http)
        assert _ia("estado.removendo") in _texto(resposta.text)
        assert _tarefas(painel) == {"encaixe": local | {"ligada": False}}  # já, antes do fim
        (painel.dados / "ferramentas" / ia_local.ANOTACAO).unlink()
        painel.comando.liberar.set()
        assert _esperar(lambda: _ia_livre(painel))
        final = _texto(http.get(IA_LOCAL, headers=HTMX).text)
    assert painel.comandos == [(["remover", "ia-local"], painel.dados)]
    assert _ia("aviso.removido") in final
    assert _ia("estado.nao_baixado") in final


def test_remover_nao_mexe_na_tarefa_de_outro_backend(sem_leitor: Painel) -> None:
    """(guarda) Só as tarefas no `local` desligam."""
    painel = sem_leitor
    _anotar(painel, "2b")
    claude = {"ligada": True, "backend": "anthropic", "modelo": "claude-haiku-4-5"}
    _tarefas(painel, {"encaixe": claude})
    with TestClient(painel.app, base_url=BASE) as http:
        _post_ia(painel, "remover", http)
        assert _tarefas(painel) == {"encaixe": claude}
        painel.comando.liberar.set()
        assert _esperar(lambda: _ia_livre(painel))
    _tarefas(painel, {"encaixe": claude | {"backend": "local"}})  # controle: no local, desliga
    with TestClient(painel.app, base_url=BASE) as http:
        painel.comando = ComandoFalso()
        _post_ia(painel, "remover", http)
        assert _tarefas(painel)["encaixe"]["ligada"] is False
        painel.comando.liberar.set()
        assert _esperar(lambda: _ia_livre(painel))


def test_motivos_sao_os_do_comando() -> None:
    assert set(MOTIVOS_IA) == {*get_args(Motivo), "programa_ausente", "modelo_ausente"}


@pytest.mark.parametrize("idioma", ["pt", "en"])
@pytest.mark.parametrize("motivo", [*MOTIVOS_IA, "inventado", None])
def test_falha_diz_o_motivo(sem_leitor: Painel, idioma: str, motivo: str | None) -> None:
    painel = sem_leitor
    painel.idioma(idioma)
    fim: dict[str, object] = {"fim": "falhou"}
    painel.comando.depois = [fim | {"motivo": motivo} if motivo else fim]
    painel.comando.codigo = 1
    painel.comando.liberar.set()
    with TestClient(painel.app, base_url=BASE) as http:
        _post_ia(painel, "baixar", http)
        assert _esperar(lambda: _ia_livre(painel))
        html = http.get(IA_LOCAL, headers=HTMX).text
    texto = _texto(html)
    razao = _ia(f"motivo.{motivo if motivo in MOTIVOS_IA else 'outro'}", idioma)
    assert _ia("aviso.falhou_baixar", idioma, motivo=razao) in texto
    assert _acoes_ia(html) == ["baixar"]  # tentar de novo


def test_saida_com_erro_e_falha_mesmo_com_fim_pronto(sem_leitor: Painel) -> None:
    painel = sem_leitor
    painel.comando.codigo = 1  # o processo saiu com erro: a linha `fim` não basta
    painel.comando.liberar.set()
    with TestClient(painel.app, base_url=BASE) as http:
        _post_ia(painel, "baixar", http)
        assert _esperar(lambda: _ia_livre(painel))
        texto = _texto(http.get(IA_LOCAL, headers=HTMX).text)
    assert _ia("aviso.falhou_baixar", motivo=_ia("motivo.outro")) in texto


def test_um_comando_por_vez(sem_leitor: Painel) -> None:
    painel = sem_leitor
    with TestClient(painel.app, base_url=BASE) as http:
        _post_ia(painel, "baixar", http)
        segundo = _post_ia(painel, "baixar", http)
        assert _ia("estado.baixando") in _texto(segundo.text)
        assert len(painel.comandos) <= 1
        assert _esperar(lambda: len(painel.comandos) == 1)
        painel.comando.liberar.set()
        assert _esperar(lambda: _ia_livre(painel))
    assert len(painel.comandos) == 1


@pytest.mark.parametrize("acao", ["trocar", "remover", "atualizar"])
def test_acao_sem_modelo_baixado_nao_roda(sem_leitor: Painel, acao: str) -> None:
    """(guarda) Trocar, Remover e Atualizar pedem o modelo baixado; Baixar pede que não esteja."""
    painel = sem_leitor
    with TestClient(painel.app, base_url=BASE) as http:
        assert _post_ia(painel, acao, http).status_code == 200
        _anotar(painel, "2b")
        assert _post_ia(painel, "baixar", http).status_code == 200
        assert painel.comandos == []
        _anotar(painel, "2b", build="b1")  # controle: com o modelo baixado e mudado, roda
        _post_ia(painel, acao, http)
        painel.comando.liberar.set()
        assert _esperar(lambda: _ia_livre(painel))
    assert len(painel.comandos) == 1


def test_acao_desconhecida_da_404(sem_leitor: Painel) -> None:
    assert sem_leitor.post(f"{IA_LOCAL}/apagar").status_code == 404
    assert sem_leitor.comandos == []


def test_sem_javascript_o_post_volta_a_pagina(sem_leitor: Painel) -> None:
    with TestClient(sem_leitor.app, base_url=BASE, follow_redirects=False) as http:
        resposta = sem_leitor.post(f"{IA_LOCAL}/baixar", http)
        assert (resposta.status_code, resposta.headers.get("location")) == (303, GRUPO)
        assert _ia("estado.baixando") in _texto(http.get(GRUPO).text)
        sem_leitor.comando.liberar.set()
        assert _esperar(lambda: _ia_livre(sem_leitor))


def test_post_sem_csrf_nao_roda(sem_leitor: Painel) -> None:
    http = TestClient(sem_leitor.app, base_url=BASE, raise_server_exceptions=False)
    assert http.post(f"{IA_LOCAL}/baixar", headers=HTMX).status_code == 403
    assert sem_leitor.comandos == []


def _falhou_e_voltou(painel: Painel, http: TestClient) -> None:
    """O cartão depois de uma falha: aviso, trava solta e "Baixar" de volta."""
    assert _esperar(lambda: _ia_livre(painel))
    html = http.get(IA_LOCAL, headers=HTMX).text
    assert _ia("aviso.falhou_baixar", motivo=_ia("motivo.outro")) in _texto(html)
    assert _acoes_ia(html) == ["baixar"]
    assert 'hx-trigger="every 5s"' not in html


def test_comando_que_nao_abre_vira_falha(sem_leitor: Painel) -> None:
    painel = sem_leitor
    painel.abrir_ia.erro = OSError("sem python")
    with TestClient(painel.app, base_url=BASE) as http:
        _post_ia(painel, "baixar", http)
        _falhou_e_voltou(painel, http)


def test_saida_que_levanta_no_meio_mata_o_comando(sem_leitor: Painel) -> None:
    painel = sem_leitor
    painel.comando.erro = OSError("cano")
    painel.comando.liberar.set()
    with TestClient(painel.app, base_url=BASE) as http:
        _post_ia(painel, "baixar", http)
        _falhou_e_voltou(painel, http)
    assert painel.comando.sinais == ["kill"]


def test_tarefa_cancelada_mata_o_comando(sem_leitor: Painel) -> None:
    """`/sair` e o fim do servidor cancelam a tarefa: o filho não segue baixando sozinho."""
    painel = sem_leitor
    with TestClient(painel.app, base_url=BASE) as http:
        _post_ia(painel, "baixar", http)
        assert _esperar(lambda: len(painel.comandos) == 1)
        assert painel.comando.sinais == []
        assert http.portal is not None
        for tarefa in list(painel.app.state.tarefas):
            http.portal.call(tarefa.cancel)
        assert _esperar(lambda: _ia_livre(painel))
    assert painel.comando.sinais == ["kill"]


def test_comando_que_termina_nao_e_morto(sem_leitor: Painel) -> None:
    """(controle) O `kill` é só do caminho de erro."""
    painel = sem_leitor
    painel.comando.liberar.set()
    with TestClient(painel.app, base_url=BASE) as http:
        _post_ia(painel, "baixar", http)
        assert _esperar(lambda: _ia_livre(painel))
    assert painel.comando.sinais == []


@pytest.mark.parametrize(
    "torta",
    [{"modelo": ["2b"]}, {"modelo": {"2b": 1}}, {"alvo": ["ubuntu-x64"]}, {"arquivo": ["m.gguf"]}],
)
def test_anotacao_torta_nao_derruba_a_pagina(sem_leitor: Painel, torta: dict[str, object]) -> None:
    painel = sem_leitor
    _anotar(painel, "2b", **torta)
    resposta = TestClient(painel.app, base_url=BASE, raise_server_exceptions=False).get(GRUPO)
    assert resposta.status_code == 200
    assert _ia("estado.nao_baixado") in _texto(resposta.text)
    assert _acoes_ia(resposta.text) == ["baixar"]
    with TestClient(painel.app, base_url=BASE) as http:
        assert _post_ia(painel, "baixar", http).status_code == 200
        painel.comando.liberar.set()
        assert _esperar(lambda: _ia_livre(painel))
    assert painel.comandos == [(["baixar", "ia-local"], painel.dados)]
    _anotar(painel, "2b")  # controle: a anotação boa mostra "Baixado"
    assert _ia("estado.baixado") in _texto(painel.http.get(GRUPO).text)


@pytest.mark.parametrize("sem", ["programa", "modelo"])
def test_arquivo_anotado_que_sumiu_oferece_atualizar(sem_leitor: Painel, sem: str) -> None:
    """Apagado à mão: o `atualizar ia-local` baixa o que falta."""
    painel = sem_leitor
    _anotar(painel, "2b", sem=sem)
    html = painel.http.get(GRUPO).text
    assert _ia("desatualizado") in _texto(html)
    assert _acoes_ia(html) == ["atualizar", "trocar", "remover"]
    _anotar(painel, "2b")  # controle: com os dois arquivos, nada a atualizar
    assert _acoes_ia(painel.http.get(GRUPO).text) == ["trocar", "remover"]


def test_removendo_sem_barra_nem_dica_de_download(sem_leitor: Painel) -> None:
    painel = sem_leitor
    with TestClient(painel.app, base_url=BASE) as http:
        baixando = _post_ia(painel, "baixar", http).text  # controle: no baixando, tem
        painel.comando.liberar.set()
        assert _esperar(lambda: _ia_livre(painel))
        _anotar(painel, "2b")
        painel.comando = ComandoFalso()
        removendo = _post_ia(painel, "remover", http).text
        painel.comando.liberar.set()
        assert _esperar(lambda: _ia_livre(painel))
    dica = _t("dica_baixando")
    assert "<progress" in baixando and dica in _texto(baixando)
    assert _ia("estado.removendo") in _texto(removendo)
    assert "<progress" not in removendo and dica not in _texto(removendo)


def test_sem_javascript_rodando_tem_link_para_recarregar(sem_leitor: Painel) -> None:
    painel = sem_leitor
    with TestClient(painel.app, base_url=BASE) as http:
        assert "<noscript" not in http.get(GRUPO).text  # parado: nada a recarregar
        _post_ia(painel, "baixar", http)
        html = http.get(GRUPO).text
        painel.comando.liberar.set()
        assert _esperar(lambda: _ia_livre(painel))
    trecho = re.search(r"<noscript>(.*?)</noscript>", html, re.S)
    assert trecho is not None
    assert f'href="{GRUPO}"' in trecho.group(1)
    assert _ia("recarregar") in _texto(trecho.group(1))


_FOCO = "data-foco-se-livre"


def _com_foco(html: str) -> list[str]:
    """O texto de cada elemento marcado para receber o foco depois da troca."""
    return [_texto(m).strip() for m in re.findall(rf"<p\b[^>]*{_FOCO}[^>]*>(.*?)</p>", html)]


def test_foco_no_estado_depois_do_botao_e_no_aviso_do_fim(sem_leitor: Painel) -> None:
    """O botão apertado some na troca: o foco vai ao estado; o polling não o rouba; o fim vai
    ao aviso."""
    painel = sem_leitor
    with TestClient(painel.app, base_url=BASE) as http:
        assert _com_foco(_post_ia(painel, "baixar", http).text) == [_ia("estado.baixando")]
        assert _com_foco(http.get(IA_LOCAL, headers=HTMX).text) == []
        painel.comando.liberar.set()
        assert _esperar(lambda: _ia_livre(painel))
        assert _com_foco(http.get(IA_LOCAL, headers=HTMX).text) == [_ia("aviso.pronto")]
        assert _com_foco(http.get(IA_LOCAL, headers=HTMX).text) == []


@pytest.mark.parametrize(("chave", "mudou"), [(None, False), ("2b", True), ("4b", True)])
def test_argumentos_passam_pelo_parser_do_cli(chave: str | None, mudou: bool) -> None:
    """Cada lista que a rota roda é um `jobot ferramentas ... ia-local` que o CLI aceita."""
    listas = [a for a in argumentos_ia_local(chave, mudou).values() if a is not None]
    assert listas
    for lista in listas:
        inteiro = ia_local.comando(lista)
        assert inteiro[:3] == [sys.executable, "-m", "jobot"]
        lido = jobot.cli._parser().parse_args(inteiro[3:])
        assert (lido.comando, lido.ferramenta) == ("ferramentas", "ia-local")
        assert lido.acao == lista[0]
        if "--modelo" in lista:
            assert lido.modelo == lista[-1]


def test_remover_de_verdade_numa_pasta_vazia(tmp_path: Path) -> None:
    """O comando real, sem rede: `remover ia-local` sem nada baixado sai pronto."""

    async def rodar() -> tuple[list[dict[str, Any]], int]:
        comando = await ia_local.abrir_comando(["remover", "ia-local"], tmp_path)
        assert comando.stdout is not None
        linhas = [json.loads(linha) async for linha in comando.stdout]
        return linhas, await comando.wait()

    linhas, codigo = asyncio.run(rodar())
    assert (linhas[-1], codigo) == ({"fim": "pronto"}, 0)


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_textos_do_modelo_local_nos_dois_catalogos(idioma: str) -> None:
    pt, outro = i18n.carregar()["pt"], i18n.carregar()[idioma]
    prefixo = "configuracoes.ferramentas.ia_local."
    assert {c for c in pt if c.startswith(prefixo)} == {c for c in outro if c.startswith(prefixo)}
    assert {f"{prefixo}motivo.{m}" for m in (*MOTIVOS_IA, "outro")} <= set(outro)
    explicacao = outro["configuracoes.ferramentas.explicacao"]
    assert "navegador" not in explicacao and "browser" not in explicacao
