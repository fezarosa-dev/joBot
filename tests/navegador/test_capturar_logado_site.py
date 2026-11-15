"""`scripts/capturar_logado.py` contra o site falso (T220; desenho A10).

O teste é síncrono: o `main` do script roda o próprio laço (`asyncio.run`), e o navegador sem
tela entra pelas `dependencias` injetadas, com a rota que recusa tudo fora do loopback. O Enter
é simulado. Nome e id da conta são inventados (`Fulana Exemplo`, `u-998877`).
"""

import importlib.util
import json
import sys
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import urlsplit

import pytest
from playwright.async_api import BrowserContext, Route, async_playwright

from apoio.cofre_falso import CofreFalso
from apoio.relogio import RelogioFalso
from apoio.site_falso import LOCAIS, LeitorFalso, SiteFalso, _Resposta
from jobot.navegador import limites
from jobot.navegador.execucao import Dependencias
from jobot.navegador.janela_comum import Janela, JanelaComum
from jobot.navegador.politica import dentro_dos_hosts
from jobot.sistema.cofre import Cofre
from jobot.sistema.instancia import captura_em_andamento, pid_do_servidor

pytestmark = pytest.mark.tela

RAIZ = Path(__file__).resolve().parents[2]
NOME = "Fulana Exemplo"
ID = "u-998877"
CSRF = "csrf-valor-falso-1"
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


class SiteDaConta(SiteFalso):
    """O site falso com uma página logada que busca os dados da conta em JSON."""

    def _rota(self, caminho: str, query: dict[str, list[str]], vez: int, cookie: str) -> _Resposta:
        if caminho == "/conta":
            return _Resposta(
                corpo=(
                    "<!doctype html><html><head><meta charset='utf-8'>"
                    f"<meta name='csrf-token' content='{CSRF}'><title>Conta</title></head>"
                    f"<body><div id='conta'>{NOME}</div><ul id='vagas'><li>Vaga 1</li></ul>"
                    "<script>fetch('/api/conta')</script></body></html>"
                ).encode()
            )
        if caminho == "/api/conta":
            corpo = {
                "csrf_token": CSRF,
                "sessao": JWT,
                "link": f"/painel;jsessionid={SESSAO}",
                "conta": {"id": ID, "nome": NOME},
                "vagas": [{"titulo": "Vaga 1"}],
            }
            return _Resposta(corpo=json.dumps(corpo).encode(), tipo="application/json")
        return super()._rota(caminho, query, vez, cookie)


def _montar(
    recusados: list[str], eventos: list[str] | None = None
) -> Callable[[Path, Mapping[str, str]], AbstractAsyncContextManager[Dependencias]]:
    """O navegador sem tela, com a rota que recusa tudo fora do loopback (e `eventos`, se vier)."""

    async def filtrar(route: Route) -> None:
        if urlsplit(route.request.url).hostname in LOCAIS:
            await route.continue_()
        else:
            recusados.append(route.request.url)
            await route.abort()

    @asynccontextmanager
    async def dependencias(d: Path, env: Mapping[str, str]) -> AsyncIterator[Dependencias]:
        async with async_playwright() as playwright:

            async def lancar(**argumentos: Any) -> BrowserContext:
                if eventos is not None:
                    eventos.append("contexto")
                argumentos.pop("channel", None)  # sempre o Chromium do Playwright, igual no CI
                contexto = await playwright.chromium.launch_persistent_context(
                    **argumentos, headless=True
                )
                await contexto.route("**/*", filtrar)
                return contexto

            yield Dependencias(
                dados=d,
                lancar=lancar,
                ambiente=lambda: {"DISPLAY": ":0"},
                politica=lambda leitor: lambda url: dentro_dos_hosts(url, leitor.hosts),
                sortear=lambda: limites.ESPERA_MIN_S,
                cofre=Cofre(d, CofreFalso()),
                avisar=lambda titulo, frase: None,
            )

    return dependencias


def test_captura_do_site_falso_grava_limpa(tmp_path: Path) -> None:
    dados = tmp_path / "dados"
    base = tmp_path / "fixtures"
    recusados: list[str] = []
    durante: list[bool] = []
    dependencias = _montar(recusados)

    async def enter() -> None:  # a pessoa aperta Enter com a captura em andamento
        durante.append(captura_em_andamento(dados))

    with SiteDaConta() as site:
        leitor = LeitorFalso.para(
            site,
            url_entrada=site.url("/conta"),
            respostas=(r"127\.0\.0\.1/api/conta", r"127\.0\.0\.1/conta"),
            campos_conta=("#conta", "$.conta.id", "$.conta.nome"),
        )
        codigo = capturar_logado.main(
            ["falso_logado", "--caso", "conta"],
            env={"JOBOT_DADOS": str(dados)},
            dependencias=dependencias,
            enter=enter,
            base=base,
            leitores_registrados=lambda: (leitor,),
            relogio=RelogioFalso(),
        )

    assert codigo == 0
    assert durante == [True]
    assert pid_do_servidor(dados) is None  # soltou a trava
    assert recusados == [], f"pedido para fora do loopback: {recusados}"
    pasta = base / "falso_logado"
    nomes = sorted(p.name for p in pasta.iterdir())
    assert len(nomes) == 4
    casos = [p for p in pasta.iterdir() if not p.name.endswith(".meta.json")]
    assert sorted(p.suffix for p in casos) == [".html", ".json"]
    for arquivo in pasta.iterdir():
        texto = arquivo.read_text(encoding="utf-8")
        for segredo in (NOME, ID, CSRF, JWT, SESSAO):
            assert segredo not in texto, f"{arquivo.name} ainda tem um segredo"
    json_ = next(p for p in casos if p.suffix == ".json")
    dado = json.loads(json_.read_text(encoding="utf-8"))
    assert dado["conta"] == {"id": capturar_logado.MARCADOR, "nome": capturar_logado.MARCADOR}
    assert dado["vagas"] == [{"titulo": "Vaga 1"}]
    html_ = next(p for p in casos if p.suffix == ".html").read_text(encoding="utf-8")
    assert "&lt;limpo&gt;" in html_ and "Vaga 1" in html_
    meta = json.loads((pasta / f"{json_.stem}.meta.json").read_text(encoding="utf-8"))
    assert meta["cabecalhos"] == {}
    assert capturar_logado.problemas(pasta) == []


def _capturar_com_recorte(tmp_path: Path, argv: list[str]) -> tuple[int, Path]:
    """A captura do site falso com leitor e `--recorte` em `#vagas`; devolve o código e a pasta."""
    base = tmp_path / "fixtures"
    with SiteDaConta() as site:
        leitor = LeitorFalso.para(
            site,
            url_entrada=site.url("/conta"),
            respostas=(r"127\.0\.0\.1/api/conta", r"127\.0\.0\.1/conta"),
            campos_conta=("#conta", "$.conta.id", "$.conta.nome"),
        )

        async def enter() -> None:
            pass

        codigo = capturar_logado.main(
            ["falso_logado", "--caso", "conta", "--recorte", "#vagas", *argv],
            env={"JOBOT_DADOS": str(tmp_path / "dados")},
            dependencias=_montar([]),
            enter=enter,
            base=base,
            leitores_registrados=lambda: (leitor,),
            relogio=RelogioFalso(),
        )
    return codigo, base / "falso_logado"


def test_com_recorte_nao_grava_json(tmp_path: Path) -> None:
    codigo, pasta = _capturar_com_recorte(tmp_path, [])
    assert codigo == 0
    assert sorted(p.name for p in pasta.iterdir()) == ["conta.html", "conta.meta.json"]


def test_com_recorte_grava_o_html_final_com_leitor(tmp_path: Path) -> None:
    codigo, pasta = _capturar_com_recorte(tmp_path, [])
    assert codigo == 0
    assert (pasta / "conta.html").is_file()
    html_ = (pasta / "conta.html").read_text(encoding="utf-8")
    assert "Vaga 1" in html_
    assert "<title>Conta</title>" in html_
    assert "csrf-token" not in html_  # o recorte tirou o `<meta>` do `<head>`
    meta = json.loads((pasta / "conta.meta.json").read_text(encoding="utf-8"))
    assert meta["recorte"] == ["#vagas"]


def test_login_abre_a_janela_comum_antes_da_captura(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    eventos: list[str] = []
    abertas: list[Sequence[str]] = []

    class Fecha:
        async def wait(self) -> int:
            return 0

        def terminate(self) -> None:
            pass

        def kill(self) -> None:
            pass

    async def achar() -> Path | None:
        return Path("/x/chrome")

    async def abrir(argumentos: Sequence[str], ambiente: Mapping[str, str]) -> Janela:
        eventos.append("janela")
        abertas.append(argumentos)
        return Fecha()

    async def enter() -> None:
        pass

    base = tmp_path / "fixtures"
    with SiteDaConta() as site:
        leitor = LeitorFalso.para(
            site,
            url_entrada=site.url("/conta"),
            respostas=(r"127\.0\.0\.1/api/conta", r"127\.0\.0\.1/conta"),
            campos_conta=("#conta", "$.conta.id", "$.conta.nome"),
        )
        codigo = capturar_logado.main(
            ["falso_logado", "--caso", "conta", "--login", site.url("/login")],
            env={"JOBOT_DADOS": str(tmp_path / "dados")},
            dependencias=_montar([], eventos),
            enter=enter,
            base=base,
            leitores_registrados=lambda: (leitor,),
            relogio=RelogioFalso(),
            janela=JanelaComum(caminho=achar, abrir=abrir),
        )
    assert codigo == 0
    assert eventos == ["janela", "contexto"]
    assert abertas[0][-1] == site.url("/login")
    saida = capsys.readouterr().out
    assert "Abra a página que quer guardar e aperte Enter aqui." in saida
    assert "senha" not in saida
