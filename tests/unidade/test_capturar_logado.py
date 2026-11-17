"""`scripts/capturar_logado.py` (T220; desenho A10): limpeza pela posição, conferência e trava.

Nome e id da conta são inventados (`Fulana Exemplo`, `u-998877`); os segredos da sessão também.
"""

import importlib.util
import json
import os
import socket
import sys
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from selectolax.lexbor import LexborHTMLParser, LexborNode

from apoio.cofre_falso import CofreFalso
from apoio.relogio import RelogioFalso
from jobot.navegador import limites
from jobot.navegador.execucao import Dependencias
from jobot.navegador.janela_comum import Janela, JanelaComum
from jobot.navegador.perfil import pasta_do_perfil
from jobot.nucleo.leitores.base import RespostaCapturada
from jobot.sistema.cofre import Cofre
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


# --- recorte, tirar e login pela janela comum (T234; D136.10, D136.11) -------------------

SELETOR = '[componentkey^="job-card-component-ref-"]'
FRASE = "2 school alumni work here"
PADRAO = "alumni|ex-alunos"
PAGINA = (
    "<!doctype html><html><head><title>Vagas</title></head><body>"
    "<nav>Menu NAVTEXTO</nav><ul>"
    '<li componentkey="job-card-component-ref-1">Vaga A<ul>'
    '<li componentkey="job-card-component-ref-2">Interna</li></ul></li>'
    '<li componentkey="job-card-component-ref-3">Vaga B</li></ul></body></html>'
)


def _recortar(html: str, seletores: list[str], host: str) -> str:
    saida: str = capturar_logado.recortar(html, seletores, host)
    return saida


def _no(html: str, seletor: str) -> LexborNode:
    no = LexborHTMLParser(html).css_first(seletor)
    assert no is not None, seletor
    return no


def _tirar(html: str, padroes: list[str]) -> str:
    saida: str = capturar_logado.tirar(html, padroes)
    return saida


def _sem_imagens(html: str) -> str:
    saida: str = capturar_logado.sem_imagens(html)
    return saida


def _conferir_tirar(html: str, padroes: list[str]) -> list[str]:
    restos: list[str] = capturar_logado.conferir_tirar(html, padroes)
    return restos


class _JanelaQueFecha:
    async def wait(self) -> int:
        return 0

    def terminate(self) -> None:
        pass

    def kill(self) -> None:
        pass


def _janela(abertas: list[Sequence[str]], caminho: Path | None = Path("/x/chrome")) -> JanelaComum:
    async def achar() -> Path | None:
        return caminho

    async def abrir(argumentos: Sequence[str], ambiente: Mapping[str, str]) -> Janela:
        abertas.append(argumentos)
        return _JanelaQueFecha()

    return JanelaComum(caminho=achar, abrir=abrir)


def _com_deps(ambiente: Mapping[str, str]) -> Any:
    @asynccontextmanager
    async def dependencias(dados: Path, env: Mapping[str, str]) -> AsyncIterator[Dependencias]:
        async def lancar(**argumentos: Any) -> Any:
            raise AssertionError("o `_navegar` está trocado: ninguém lança o navegador")

        yield Dependencias(
            dados=dados,
            lancar=lancar,
            ambiente=lambda: ambiente,
            politica=lambda leitor: lambda url: True,
            sortear=lambda: limites.ESPERA_MIN_S,
            cofre=Cofre(dados, CofreFalso()),
            avisar=lambda titulo, frase: None,
        )

    return dependencias


def _capturar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    html: str,
    argv: list[str],
    *,
    eventos: list[str] | None = None,
    ambiente: Mapping[str, str] | None = None,
    janela: JanelaComum | None = None,
) -> tuple[int, Path]:
    """Roda o `main` com o `_navegar` trocado por uma resposta de HTML sintético."""

    async def falso(*args: Any, **kwargs: Any) -> list[RespostaCapturada]:
        if eventos is not None:
            eventos.append("navegar")
        url = "https://www.linkedin.com/jobs/search/?keywords=enfermeiro"
        return [RespostaCapturada(url, 200, "text/html", html)]

    monkeypatch.setattr(capturar_logado, "_navegar", falso)
    base = tmp_path / "fixtures"
    codigo: int = capturar_logado.main(
        ["--caso", "caso", "--host", "www.linkedin.com", *argv],
        env={"JOBOT_DADOS": str(tmp_path / "dados")},
        dependencias=_com_deps({"DISPLAY": ":0"} if ambiente is None else ambiente),
        base=base,
        relogio=RelogioFalso(),
        janela=janela,
    )
    return codigo, base / "caso"


def test_recorte_guarda_titulo_e_nos_de_fora() -> None:
    saida = _recortar(PAGINA, [SELETOR], "www.linkedin.com")
    assert "<title>Vagas</title>" in saida
    assert saida.count("Vaga A") == 1
    assert saida.count("Interna") == 1  # dentro do nó de fora, uma vez só
    assert saida.count("Vaga B") == 1
    assert saida.index("Vaga A") < saida.index("Vaga B")
    assert "NAVTEXTO" not in saida


def test_recorte_sem_no_recusa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo, pasta = _capturar(tmp_path, monkeypatch, PAGINA, ["--recorte", ".nao-existe"])
    assert codigo == 2
    saida = capsys.readouterr()
    assert "recorte sem nó" in saida.err + saida.out
    assert not pasta.exists()


def test_recorte_com_um_seletor_sem_no_grava(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    argv = ["--recorte", ".nao-existe", "--recorte", SELETOR]
    codigo, pasta = _capturar(tmp_path, monkeypatch, PAGINA, argv)
    assert codigo == 0
    texto = (pasta / "caso.html").read_text(encoding="utf-8")
    assert "Vaga B" in texto
    assert "NAVTEXTO" not in texto


def test_recorte_limpa_o_valor_da_query() -> None:
    pagina = (
        "<html><head><title>T</title></head><body><div id='c'>"
        "<a id='l' href='https://www.linkedin.com/safety/go/"
        "?url=https%3A%2F%2Fempresa.test%2Fvaga&mt=SEGREDO&urlhash=abc'>x</a>"
        "<img id='i' src='/x?trackingId=SEGREDO'>"
        "<a id='o' href='https://outro.test/p?mt=VALOR'>y</a></div></body></html>"
    )
    saida = _recortar(pagina, ["#c"], "www.linkedin.com")
    href = _no(saida, "#l").attributes["href"] or ""
    src = _no(saida, "#i").attributes["src"] or ""
    assert parse_qs(urlsplit(href).query) == {
        "url": ["https://empresa.test/vaga"],
        "mt": [MARCADOR],
        "urlhash": [MARCADOR],
    }
    assert parse_qs(urlsplit(src).query) == {"trackingId": [MARCADOR]}
    assert "SEGREDO" not in saida
    assert _no(saida, "#o").attributes["href"] == "https://outro.test/p?mt=VALOR"


@pytest.mark.parametrize(
    ("link", "limpo"),
    [
        ("https://br.linkedin.com/p?mt=VALOR", True),
        ("https://linkedin.com/p?mt=VALOR", True),
        ("https://www.linkedin.com/p?mt=VALOR", True),
        ("https://a.b.linkedin.com/p?mt=VALOR", True),
        ("https://outro.test/p?mt=VALOR", False),
        ("https://naolinkedin.com/p?mt=VALOR", False),
        ("https://linkedin.com.outro.test/p?mt=VALOR", False),
    ],
)
def test_recorte_limpa_a_query_do_site_com_ou_sem_subdominio(link: str, limpo: bool) -> None:
    pagina = f"<html><body><div id='c'><a id='l' href='{link}'>x</a></div></body></html>"
    saida = _recortar(pagina, ["#c"], "www.linkedin.com")
    esperado = link.replace("VALOR", MARCADOR) if limpo else link
    assert _no(saida, "#l").attributes["href"] == esperado


def test_recorte_limpa_cada_url_do_srcset() -> None:
    pagina = (
        "<html><body><div id='c'><img id='i' srcset='"
        "https://media.linkedin.com/a?t=SEGREDO1&url=https%3A%2F%2Fx.test 1x, "
        "/b?t=SEGREDO2 2x, https://outro.test/c?t=FICA 480w'></div></body></html>"
    )
    saida = _recortar(pagina, ["#c"], "www.linkedin.com")
    srcset = _no(saida, "#i").attributes["srcset"] or ""
    assert "SEGREDO" not in saida
    itens = [i.strip().rsplit(" ", 1) for i in srcset.split(", ")]
    assert [d for _, d in itens] == ["1x", "2x", "480w"]
    assert parse_qs(urlsplit(itens[0][0]).query) == {
        "t": [MARCADOR],
        "url": ["https://x.test"],
    }
    assert parse_qs(urlsplit(itens[1][0]).query) == {"t": [MARCADOR]}
    assert itens[2][0] == "https://outro.test/c?t=FICA"


@pytest.mark.parametrize(
    "srcset",
    [
        "https://www.linkedin.com/i?a=1,b=SEGREDO 2x, https://www.linkedin.com/j?c=SEGREDO2 1x",
        "https://www.linkedin.com/i?a=SEGREDO 1x,https://www.linkedin.com/j?b=SEGREDO2 2x",
        "  ,https://www.linkedin.com/i?a=SEGREDO,, https://www.linkedin.com/j?b=SEGREDO2 480w ,",
    ],
)
def test_recorte_srcset_com_virgula_na_url_ou_sem_espaco(srcset: str) -> None:
    pagina = f"<html><body><div id='c'><img id='i' srcset='{srcset}'></div></body></html>"
    saida = _recortar(pagina, ["#c"], "www.linkedin.com")
    novo = _no(saida, "#i").attributes["srcset"] or ""
    assert "SEGREDO" not in saida
    descritores = [d for d in ("1x", "2x", "480w") if d in srcset]
    assert all(d in novo for d in descritores)
    assert MARCADOR in novo


def test_recorte_troca_o_link_que_nao_se_le() -> None:
    pagina = "<html><body><div id='c'><a id='l' href='http://[abc/p?mt=SEGREDO'>x</a></div></body></html>"
    saida = _recortar(pagina, ["#c"], "www.linkedin.com")
    assert _no(saida, "#l").attributes["href"] == MARCADOR
    assert "SEGREDO" not in saida


def test_tirar_troca_o_texto_e_o_atributo() -> None:
    pagina = (
        f"<html><body><p id='t'>{FRASE}</p><p id='u' aria-label='{FRASE}'>ok</p>"
        "<p id='v'>fica</p></body></html>"
    )
    saida = _tirar(pagina, [PADRAO])
    assert _no(saida, "#t").text(deep=False) == MARCADOR
    assert _no(saida, "#u").attributes["aria-label"] == MARCADOR
    assert _no(saida, "#u").text(deep=False) == "ok"
    assert _no(saida, "#v").text(deep=False) == "fica"
    assert "alumni" not in saida


def test_tirar_recusa_o_residuo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    com_comentario = PAGINA.replace("</ul></body>", f"</ul><!-- {FRASE} --></body>")
    assert len(_conferir_tirar(_tirar(com_comentario, [PADRAO]), [PADRAO])) == 1
    codigo, pasta = _capturar(
        tmp_path, monkeypatch, com_comentario, ["--recorte", "body", "--tirar", PADRAO]
    )
    assert codigo == 1
    assert not pasta.exists()
    # controle: a mesma montagem, sem o comentário, grava
    codigo, pasta = _capturar(
        tmp_path, monkeypatch, PAGINA, ["--recorte", "body", "--tirar", PADRAO]
    )
    assert codigo == 0
    assert (pasta / "caso.html").is_file()


def test_sem_imagens_troca_todo_endereco_de_imagem() -> None:
    pagina = (
        "<html><body>"
        "<img id='a' src='https://cdn.exemplo/escola.png' srcset='https://cdn.exemplo/e1.png 1x, "
        "https://cdn.exemplo/e2.png 2x' alt='Logo da escola'>"
        "<picture><source id='b' srcset='https://cdn.exemplo/p.webp 480w'><img id='b2'></picture>"
        "<video id='c' poster='https://cdn.exemplo/capa.jpg'></video>"
        "<svg><image id='d' href='https://cdn.exemplo/s.svg' xlink:href='https://cdn.exemplo/x.svg'>"
        "</image></svg>"
        "<div id='e' style=\"color:red;background-image:url('https://cdn.exemplo/f.png')\">t</div>"
        "<a id='f' href='https://www.linkedin.com/jobs/view/1'>Vaga</a>"
        "</body></html>"
    )
    saida = _sem_imagens(pagina)
    assert "cdn.exemplo" not in saida
    assert _no(saida, "#a").attributes["src"] == MARCADOR
    assert _no(saida, "#a").attributes["srcset"] == MARCADOR
    assert _no(saida, "#a").attributes["alt"] == "Logo da escola"
    assert _no(saida, "#b").attributes["srcset"] == MARCADOR
    assert _no(saida, "#c").attributes["poster"] == MARCADOR
    assert _no(saida, "#d").attributes["href"] == MARCADOR
    assert _no(saida, "#d").attributes["xlink:href"] == MARCADOR
    assert _no(saida, "#e").attributes["style"] == f"color:red;background-image:url({MARCADOR})"
    assert _no(saida, "#f").attributes["href"] == "https://www.linkedin.com/jobs/view/1"
    assert _no(saida, "#f").text(deep=False) == "Vaga"


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ('url("a")', f"url({MARCADOR})"),
        ("url(a)", f"url({MARCADOR})"),
        ("URL(a)", f"url({MARCADOR})"),
        ('url( "a" ) no-repeat, url(b)', f"url({MARCADOR}) no-repeat, url({MARCADOR})"),
        ("url('a)b')", f"url({MARCADOR})"),
        ('url("a)b")', f"url({MARCADOR})"),
        ('url( "a)b" )', f"url({MARCADOR})"),
        ('url("a)b" )', f"url({MARCADOR})"),
        ("color:red;background:url(a) top", f"color:red;background:url({MARCADOR}) top"),
    ],
)
def test_sem_imagens_troca_cada_url_do_style(entrada: str, esperado: str) -> None:
    estilo = entrada.replace("&", "&amp;").replace('"', "&quot;")
    saida = _sem_imagens(f'<html><body><div id="e" style="{estilo}">t</div></body></html>')
    assert _no(saida, "#e").attributes["style"] == esperado


def test_sem_imagens_troca_o_src_do_source_dentro_de_video() -> None:
    pagina = (
        "<html><body><video><source id='s' src='https://cdn.exemplo/v.mp4'></video></body></html>"
    )
    saida = _sem_imagens(pagina)
    assert _no(saida, "#s").attributes["src"] == MARCADOR
    assert "cdn.exemplo" not in saida


def test_sem_imagens_troca_o_data_com_endereco_e_deixa_o_resto() -> None:
    pagina = (
        "<html><body>"
        "<img id='a' data-src='https://cdn.exemplo/a.png' data-delayed-url='//cdn.exemplo/b.png'"
        " data-id='7'>"
        "<source id='b' data-srcset='https://cdn.exemplo/c.webp 2x'>"
        "<video id='c' data-ghost-url='https://cdn.exemplo/d.jpg'></video>"
        "<svg><image id='d' data-src='https://cdn.exemplo/e.svg'></image></svg>"
        "<div id='e' data-src='https://cdn.exemplo/f.png'>t</div>"
        "</body></html>"
    )
    saida = _sem_imagens(pagina)
    assert _no(saida, "#a").attributes["data-src"] == MARCADOR
    assert _no(saida, "#a").attributes["data-delayed-url"] == MARCADOR
    assert _no(saida, "#a").attributes["data-id"] == "7"
    assert _no(saida, "#b").attributes["data-srcset"] == MARCADOR
    assert _no(saida, "#c").attributes["data-ghost-url"] == MARCADOR
    assert _no(saida, "#d").attributes["data-src"] == MARCADOR
    # fora de img, source, video e image o atributo data-* não é tocado
    assert _no(saida, "#e").attributes["data-src"] == "https://cdn.exemplo/f.png"


def test_captura_grava_html_sem_endereco_de_imagem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pagina = PAGINA.replace(
        "Vaga B", "Vaga B<img src='https://escola-qualquer.exemplo/logo.png' alt='x'>"
    )
    codigo, pasta = _capturar(tmp_path, monkeypatch, pagina, [])
    assert codigo == 0
    gravado = (pasta / "caso.html").read_text(encoding="utf-8")
    assert "escola-qualquer.exemplo" not in gravado
    assert _no(gravado, "img").attributes["src"] == MARCADOR


def test_tirar_com_expressao_torta_devolve_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    codigo, pasta = _capturar(tmp_path, monkeypatch, PAGINA, ["--tirar", "("])
    assert codigo == 2
    assert not pasta.exists()


def test_recorte_com_seletor_invalido_devolve_2_antes_de_tudo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    abertas: list[Sequence[str]] = []
    eventos: list[str] = []
    codigo, pasta = _capturar(
        tmp_path,
        monkeypatch,
        PAGINA,
        ["--recorte", SELETOR, "--recorte", "[[", "--login", "https://www.linkedin.com/login"],
        eventos=eventos,
        janela=_janela(abertas),
    )
    assert codigo == 2
    assert abertas == []
    assert eventos == []
    assert not pasta.exists()
    assert "--recorte" in capsys.readouterr().err


def test_recorte_cabe_no_limite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    grande = (
        "<html><head><title>Vagas</title></head><body>"
        f"<div>{'texto ' * 40000}</div><div id='alvo'>pequeno</div></body></html>"
    )
    codigo, pasta = _capturar(tmp_path, monkeypatch, grande, ["--recorte", "#alvo"])
    assert codigo == 0
    assert (pasta / "caso.html").stat().st_size < 50 * 1024  # MAX_BYTES do `capturar.py`


def test_meta_guarda_recorte_e_tirar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    argv = ["--recorte", SELETOR, "--recorte", "nav", "--tirar", PADRAO, "--tirar", "outro"]
    codigo, pasta = _capturar(tmp_path, monkeypatch, PAGINA, argv)
    assert codigo == 0
    meta = json.loads((pasta / "caso.meta.json").read_text(encoding="utf-8"))
    assert meta.get("recorte") == [SELETOR, "nav"]
    assert meta.get("tirar") == [PADRAO, "outro"]


def test_meta_so_com_tirar_nao_guarda_as_listas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    codigo, pasta = _capturar(tmp_path, monkeypatch, PAGINA, ["--tirar", PADRAO])
    assert codigo == 0
    meta = json.loads((pasta / "caso.meta.json").read_text(encoding="utf-8"))
    assert "recorte" not in meta
    assert "tirar" not in meta


@pytest.mark.parametrize("url", ["javascript:alert(1)", "--remote-debugging-port=9222"])
def test_login_recusa_endereco_que_nao_e_http(tmp_path: Path, url: str) -> None:
    abertas: list[Sequence[str]] = []
    env = {"JOBOT_DADOS": str(tmp_path)}

    def rodar(endereco: str) -> int:
        codigo: int = capturar_logado.main(
            ["--caso", "conta", "--host", "site.invalid", f"--login={endereco}"],
            env=env,
            dependencias=_nao_abre,
            janela=_janela(abertas),
        )
        return codigo

    assert rodar(url) == 2
    assert abertas == []
    assert rodar("https://site.invalid/login") == 1  # controle: o `_nao_abre` é que para


def test_login_abre_a_janela_antes_da_captura(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    abertas: list[Sequence[str]] = []
    eventos: list[str] = []
    janela = _janela(abertas)
    abrir = janela.abrir

    async def abrir_anotando(argumentos: Sequence[str], ambiente: Mapping[str, str]) -> Janela:
        eventos.append("janela")
        return await abrir(argumentos, ambiente)

    janela = JanelaComum(caminho=janela.caminho, abrir=abrir_anotando)
    url = "https://www.linkedin.com/login"
    codigo, _ = _capturar(
        tmp_path, monkeypatch, PAGINA, ["--login", url], eventos=eventos, janela=janela
    )
    assert codigo == 0
    assert eventos == ["janela", "navegar"]
    assert abertas[0][-1] == url
    assert "Entre no site e feche a janela quando terminar." in capsys.readouterr().out


@pytest.mark.parametrize(
    ("fim", "trecho"),
    [
        ("sem_navegador", "Não achei um navegador"),
        ("sem_tela", "Não há tela"),
        ("em_uso", "já está aberto"),
    ],
)
def test_login_que_nao_abre_a_janela_devolve_1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fim: str,
    trecho: str,
) -> None:
    abertas: list[Sequence[str]] = []
    eventos: list[str] = []
    if fim == "em_uso":
        perfil = pasta_do_perfil(tmp_path / "dados")
        (perfil / "SingletonLock").symlink_to(f"{socket.gethostname()}-{os.getpid()}")
    janela = _janela(abertas, None if fim == "sem_navegador" else Path("/x/chrome"))
    codigo, pasta = _capturar(
        tmp_path,
        monkeypatch,
        PAGINA,
        ["--login", "https://www.linkedin.com/login"],
        eventos=eventos,
        ambiente={} if fim == "sem_tela" else None,
        janela=janela,
    )
    assert codigo == 1
    assert abertas == []
    assert eventos == []  # a captura nem começa
    assert trecho in capsys.readouterr().err
