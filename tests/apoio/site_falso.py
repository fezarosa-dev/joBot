"""Site falso dos testes de navegador (desenho, seção 8): servidor em 127.0.0.1 e ::1.

Nada daqui vai à rede de fora: os dois servidores escutam só no loopback, e a rota do
`contexto_de_teste` recusa (e conta) todo pedido do navegador para outro endereço.

O servidor conta os POST (`posts`), as visitas por caminho (`visitas`) e os campos de formulário
que mudaram de valor (`campos_mudados`): cada página leva um vigia em JavaScript que avisa por
`GET /campo-mudou` quando um campo muda, fora o campo de resposta do widget de CAPTCHA.
"""

import asyncio
import json
import socket
import threading
from collections import Counter
from collections.abc import AsyncIterator, Iterator, Sequence
from dataclasses import dataclass, field, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlsplit

import pytest
from playwright.async_api import BrowserContext, Route, async_playwright
from selectolax.lexbor import LexborHTMLParser

from apoio.relogio import RelogioFalso
from jobot.navegador.abrir import abrir_contexto
from jobot.navegador.limites import MAX_RESPOSTA_BYTES, MAX_RESPOSTAS
from jobot.navegador.politica import Politica, dentro_dos_hosts
from jobot.nucleo.coletores.base import ContextoColeta
from jobot.nucleo.leitores.base import Captura, EscopoLogado, Leitura
from jobot.nucleo.modelo import VagaColetada

LOCAIS = frozenset({"127.0.0.1", "::1"})
CAMPOS_DE_RESPOSTA = ("g-recaptcha-response", "cf-turnstile-response")
CHAVE_V2 = "chave-v2-falsa"
CHAVE_TURNSTILE = "chave-turnstile-falsa"
CHAVE_INVISIVEL = "chave-invisivel-falsa"
CHAVE_V3 = "chave-v3-falsa"

# Avisa o servidor quando um campo de formulário muda de valor (por digitação ou por script).
_VIGIA = """<script>
(() => {
  const respostas = __RESPOSTAS__;
  const iniciais = new Map();
  const conferir = () => {
    for (const el of document.querySelectorAll('input, textarea, select')) {
      if (respostas.includes(el.name)) continue;
      if (!iniciais.has(el)) { iniciais.set(el, el.value); continue; }
      if (iniciais.get(el) !== el.value) {
        iniciais.set(el, el.value);
        fetch('/campo-mudou?nome=' + encodeURIComponent(el.name));
      }
    }
  };
  conferir();
  document.addEventListener('input', conferir, true);
  document.addEventListener('change', conferir, true);
  setInterval(conferir, 50);
})();
</script>""".replace("__RESPOSTAS__", json.dumps(list(CAMPOS_DE_RESPOSTA)))


def _pagina(titulo: str, corpo: str) -> bytes:
    return (
        f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><title>{titulo}</title>"
        f"</head><body>{corpo}{_VIGIA}</body></html>"
    ).encode()


def _itens(ids: Sequence[int], torto: Sequence[int] = ()) -> str:
    linhas = []
    for n in ids:
        if n in torto:
            linhas.append(f"<li class='vaga' data-id='{n}'></li>")
        else:
            linhas.append(
                f"<li class='vaga' data-id='{n}'><a href='/vaga/{n}'>Vaga {n}</a>"
                f"<span class='empresa'>Empresa {n}</span></li>"
            )
    return f"<ul id='vagas'>{''.join(linhas)}</ul>"


def _lista_html(ids: Sequence[int], proxima: str | None = None, torto: Sequence[int] = ()) -> str:
    link = f"<a id='proxima' href='{proxima}'>Próxima</a>" if proxima else ""
    return _itens(ids, torto) + link


def _json_vagas(ids: Sequence[int]) -> bytes:
    vagas = [{"id": str(n), "titulo": f"Vaga {n}", "empresa": f"Empresa {n}"} for n in ids]
    return json.dumps({"vagas": vagas}).encode()


# Lista montada pela própria página com o JSON que ela pede depois de carregar.
_LISTA_JSON = """<ul id='vagas'></ul>
<script>
async function carregar(pagina) {
  const resposta = await fetch('/api/vagas?pagina=' + pagina);
  const dados = await resposta.json();
  for (const v of dados.vagas) {
    const li = document.createElement('li');
    li.textContent = v.titulo;
    document.getElementById('vagas').appendChild(li);
  }
}
window.addEventListener('load', () => setTimeout(() => {
  carregar(1);
  %s
}, 100));
</script>"""

_ROLAR = """<div style='height: 5000px'></div>
<script>
let carregou = false;
window.addEventListener('scroll', () => {
  if (!carregou) { carregou = true; carregar(2); }
});
</script>"""

_RECAPTCHA = (
    "<div class='g-recaptcha' data-sitekey='{chave}' data-callback='{retorno}'{extra}></div>"
    "<textarea name='g-recaptcha-response' style='display:none'></textarea>"
)
_TURNSTILE = (
    "<div class='cf-turnstile' data-sitekey='{chave}' data-callback='{retorno}'></div>"
    "<input type='hidden' name='cf-turnstile-response'>"
)
# Função de retorno que confere o token no servidor (um GET, nunca POST).
_RETORNO = """<script>
function recebeu(token) { fetch('/conferir-token?token=' + encodeURIComponent(token)); }
</script>"""
_RETORNO_VOLTA = """<script>
function recebeu(token) { location.href = '/desafio-volta?depois=1'; }
</script>"""

_FORM_LOGIN = (
    "<form method='post' action='/login'>"
    "<input type='text' name='usuario' value=''>"
    "<input type='password' name='senha' value=''>"
    "{extra}<button type='submit'>Entrar</button></form>"
)
_ENVIAR = "<script>function enviar(token) { document.forms[0].submit(); }</script>"

_CLOUDFLARE = (
    "<h1>Verificando o navegador</h1>"
    "<script src='/cdn-cgi/challenge-platform/h/b/orchestrate/jsch/v1'></script>{extra}"
)
_CLOUDFLARE_SAI = (
    "<script>setTimeout(() => { document.cookie = 'cf_ok=1; path=/'; location.reload(); }, 50);"
    "</script>"
)


def _cloudflare_vai(destino: str) -> bytes:
    """Desafio que, ao sair, leva a página para outro lugar (login, SSO)."""
    script = f"<script>setTimeout(() => {{ location.href = '{destino}'; }}, 50);</script>"
    return _pagina("Just a moment...", _CLOUDFLARE.format(extra=script))


@dataclass
class _Resposta:
    status: int = 200
    corpo: bytes = b""
    tipo: str = "text/html; charset=utf-8"
    cabecalhos: dict[str, str] = field(default_factory=dict)
    sem_tamanho: bool = False  # sem Content-Length: o corpo termina quando a conexão fecha


class SiteFalso:
    """Os dois servidores e os contadores; `url()` aponta para 127.0.0.1 e `url6()` para ::1."""

    def __init__(self) -> None:
        self.posts = 0
        self.visitas: Counter[str] = Counter()
        self.campos_mudados = 0
        self.tokens: list[str] = []
        self._trava = threading.Lock()
        self._servidores: list[ThreadingHTTPServer] = []
        self._linhas: list[threading.Thread] = []

    # --- ciclo de vida ---------------------------------------------------------------------
    def subir(self) -> None:
        site = self

        class Tratador(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:  # sem barulho nos testes
                pass

            def do_GET(self) -> None:
                self._responder(site._get(self))

            def do_POST(self) -> None:
                self._responder(site._post(self))

            def _responder(self, resposta: _Resposta) -> None:
                self.send_response(resposta.status)
                self.send_header("Content-Type", resposta.tipo)
                if not resposta.sem_tamanho:
                    self.send_header("Content-Length", str(len(resposta.corpo)))
                for nome, valor in resposta.cabecalhos.items():
                    self.send_header(nome, valor)
                self.end_headers()
                self.wfile.write(resposta.corpo)

        class Servidor6(ThreadingHTTPServer):
            address_family = socket.AF_INET6

        for classe, host in ((ThreadingHTTPServer, "127.0.0.1"), (Servidor6, "::1")):
            servidor = classe((host, 0), Tratador)
            servidor.daemon_threads = True
            linha = threading.Thread(target=servidor.serve_forever, daemon=True)
            linha.start()
            self._servidores.append(servidor)
            self._linhas.append(linha)

    def parar(self) -> None:
        for servidor in self._servidores:
            servidor.shutdown()
            servidor.server_close()
        for linha in self._linhas:
            linha.join(5)

    def __enter__(self) -> SiteFalso:
        self.subir()
        return self

    def __exit__(self, *_: object) -> None:
        self.parar()

    # --- endereços -------------------------------------------------------------------------
    def url(self, caminho: str) -> str:
        return f"http://127.0.0.1:{self._servidores[0].server_address[1]}{caminho}"

    def url6(self, caminho: str) -> str:
        return f"http://[::1]:{self._servidores[1].server_address[1]}{caminho}"

    # --- páginas ---------------------------------------------------------------------------
    def _post(self, pedido: BaseHTTPRequestHandler) -> _Resposta:
        tamanho = int(pedido.headers.get("Content-Length") or 0)
        pedido.rfile.read(tamanho)
        with self._trava:
            self.posts += 1
        return _Resposta(
            303, cabecalhos={"Location": "/logado", "Set-Cookie": "falso_sessao=1; Path=/"}
        )

    def _get(self, pedido: BaseHTTPRequestHandler) -> _Resposta:
        partes = urlsplit(pedido.path)
        caminho = partes.path
        query = parse_qs(partes.query)
        with self._trava:
            self.visitas[caminho] += 1
            vez = self.visitas[caminho]
            if caminho == "/campo-mudou":
                self.campos_mudados += 1
            if caminho == "/conferir-token":
                self.tokens.extend(query.get("token", []))
        cookie = pedido.headers.get("Cookie") or ""
        return self._rota(caminho, query, vez, cookie)

    def _rota(self, caminho: str, query: dict[str, list[str]], vez: int, cookie: str) -> _Resposta:
        pagina = int((query.get("p") or ["1"])[0])
        match caminho:
            # login e entrada
            case "/login":
                return _Resposta(corpo=_pagina("Entrar", _FORM_LOGIN.format(extra="")))
            case "/login-recaptcha":
                widget = _RECAPTCHA.format(
                    chave=CHAVE_INVISIVEL, retorno="enviar", extra=" data-size='invisible'"
                )
                return _Resposta(
                    corpo=_pagina("Entrar", _FORM_LOGIN.format(extra=widget) + _ENVIAR)
                )
            case "/logado":
                return _Resposta(corpo=_pagina("Início", "<div id='conta'>Conta</div>"))
            case "/entrar/sem-senha":
                return _Resposta(corpo=_pagina("Entrar", "<p>Escolha como entrar</p>"))
            case "/sso/entrar":
                return _Resposta(corpo=_pagina("SSO", _FORM_LOGIN.format(extra="")))
            case "/qualquer":
                return _Resposta(corpo=_pagina("Outro host", "<p>Outro lugar</p>"))
            # listas
            case "/lista":
                corpo = _LISTA_JSON % "fetch('/api/outra');"
                return _Resposta(corpo=_pagina("Vagas", corpo))
            case "/rolar":
                return _Resposta(corpo=_pagina("Vagas", (_LISTA_JSON % "") + _ROLAR))
            case "/grande":
                corpo = _LISTA_JSON % "fetch('/api/grande-com-tamanho'); fetch('/api/grande-sem');"
                return _Resposta(corpo=_pagina("Vagas", corpo))
            case "/lista-html":
                return _Resposta(corpo=_pagina("Vagas", _lista_html([1, 2])))
            case "/paginada":
                proxima = "/paginada?p=2" if pagina == 1 else None
                ids = [1, 2] if pagina == 1 else [3, 4]
                return _Resposta(corpo=_pagina("Vagas", _lista_html(ids, proxima)))
            case "/paginada-torta":
                if pagina == 1:
                    return _Resposta(corpo=_pagina("Vagas", _lista_html([1, 2], "?p=2")))
                return _Resposta(corpo=_pagina("Vagas", "<p>Nada por aqui</p>"))
            case "/vazia":
                return _Resposta(corpo=_pagina("Vagas", _lista_html([])))
            case "/proxima-fora":
                return _Resposta(corpo=_pagina("Vagas", _lista_html([1], self.url6("/qualquer"))))
            case "/sem-lista":
                return _Resposta(corpo=_pagina("Vagas", "<p>Página nova</p>"))
            case "/item-torto":
                return _Resposta(corpo=_pagina("Vagas", _lista_html([1, 2, 3], torto=[2])))
            case "/so-tortos":
                return _Resposta(corpo=_pagina("Vagas", _lista_html([1, 2], torto=[1, 2])))
            case "/muitas":
                pedidos = f"for (let i = 0; i < {MAX_RESPOSTAS + 10}; i++) fetch('/api/vagas');"
                return _Resposta(corpo=_pagina("Vagas", _LISTA_JSON % pedidos))
            case "/api/vagas":
                ids = [3, 4] if (query.get("pagina") or ["1"])[0] == "2" else [1, 2]
                return _Resposta(corpo=_json_vagas(ids), tipo="application/json")
            case "/api/outra":
                return _Resposta(corpo=_json_vagas([9]), tipo="application/json")
            case "/api/grande-com-tamanho" | "/api/grande-sem":
                grande = b'{"x": "' + b"a" * MAX_RESPOSTA_BYTES + b'"}'
                sem = caminho == "/api/grande-sem"
                return _Resposta(corpo=grande, tipo="application/json", sem_tamanho=sem)
            # paradas
            case "/bloqueio":
                return _Resposta(
                    corpo=_pagina("Aviso", "<div id='bloqueio'>Atividade incomum</div>")
                )
            case "/403":
                return _Resposta(403, _pagina("Proibido", "<p>Proibido</p>"))
            case "/429":
                if vez == 1:
                    return _Resposta(
                        429, _pagina("Calma", "<p>Calma</p>"), cabecalhos={"Retry-After": "7"}
                    )
                return _Resposta(corpo=_pagina("Vagas", _lista_html([1, 2])))
            case "/429-sempre":
                return _Resposta(
                    429, _pagina("Calma", "<p>Calma</p>"), cabecalhos={"Retry-After": "7"}
                )
            case "/429-sem-tempo":
                if vez == 1:
                    return _Resposta(429, _pagina("Calma", "<p>Calma</p>"))
                return _Resposta(corpo=_pagina("Vagas", _lista_html([1, 2])))
            case "/429-longo":
                return _Resposta(
                    429, _pagina("Calma", "<p>Calma</p>"), cabecalhos={"Retry-After": "601"}
                )
            case "/salto-sso":
                return _Resposta(302, cabecalhos={"Location": self.url6("/sso/entrar")})
            case "/salto-fora":
                return _Resposta(302, cabecalhos={"Location": self.url6("/qualquer")})
            # desafios
            case "/cloudflare-sai":
                if "cf_ok=1" in cookie:
                    return _Resposta(corpo=_pagina("Vagas", _lista_html([1, 2])))
                return _Resposta(
                    403, _pagina("Just a moment...", _CLOUDFLARE.format(extra=_CLOUDFLARE_SAI))
                )
            case "/cloudflare-login":
                return _Resposta(403, _cloudflare_vai("/login"))
            case "/cloudflare-sso":
                return _Resposta(403, _cloudflare_vai(self.url6("/sso/entrar")))
            case "/cloudflare-fragmento":  # page.url com #, a resposta sem
                return _Resposta(403, _cloudflare_vai("/lista#topo"))
            case "/cloudflare-429":
                if "cf_ok=1" not in cookie:
                    return _Resposta(
                        403, _pagina("Just a moment...", _CLOUDFLARE.format(extra=_CLOUDFLARE_SAI))
                    )
                if vez == 2:  # a página que o desafio recarrega pede calma
                    return _Resposta(
                        429, _pagina("Calma", "<p>Calma</p>"), cabecalhos={"Retry-After": "7"}
                    )
                return _Resposta(corpo=_pagina("Vagas", _lista_html([1, 2])))
            case "/cloudflare-fica":
                iframe = "<iframe src='/turnstile-quadro' title='Turnstile'></iframe>"
                return _Resposta(403, _pagina("Just a moment...", _CLOUDFLARE.format(extra=iframe)))
            case "/cdn-cgi/challenge-platform/h/b/orchestrate/jsch/v1" | "/recaptcha/api.js":
                return _Resposta(corpo=b"", tipo="text/javascript")
            case "/turnstile-quadro":
                return _Resposta(corpo=_pagina("Turnstile", "<p>Verificando</p>"))
            case "/recaptcha-v2":
                widget = _RECAPTCHA.format(chave=CHAVE_V2, retorno="recebeu", extra="")
                return _Resposta(corpo=_pagina("Desafio", widget + _RETORNO))
            case "/turnstile":
                widget = _TURNSTILE.format(chave=CHAVE_TURNSTILE, retorno="recebeu")
                return _Resposta(corpo=_pagina("Desafio", widget + _RETORNO))
            case "/403-turnstile":
                widget = _TURNSTILE.format(chave=CHAVE_TURNSTILE, retorno="recebeu")
                return _Resposta(403, _pagina("Desafio", widget + _RETORNO))
            case "/429-recaptcha":
                widget = _RECAPTCHA.format(chave=CHAVE_V2, retorno="recebeu", extra="")
                return _Resposta(429, _pagina("Desafio", widget + _RETORNO))
            case "/desafio-volta":
                widget = _RECAPTCHA.format(chave=CHAVE_V2, retorno="recebeu", extra="")
                return _Resposta(corpo=_pagina("Desafio", widget + _RETORNO_VOLTA))
            case "/recaptcha-v3":
                script = f"<script src='/recaptcha/api.js?render={CHAVE_V3}'></script>"
                return _Resposta(corpo=_pagina("Desafio", script))
            case "/callback-torto":
                widget = _RECAPTCHA.format(chave=CHAVE_V2, retorno="alert(1)", extra="")
                return _Resposta(corpo=_pagina("Desafio", widget))
            # vagas e ajudantes
            case "/campo-mudou" | "/conferir-token":
                return _Resposta(204)
            case _ if caminho.startswith("/vaga/"):
                n = caminho.removeprefix("/vaga/")
                corpo = f"<h1>Vaga {n}</h1><div id='descricao'>Descrição da vaga {n}</div>"
                return _Resposta(corpo=_pagina(f"Vaga {n}", corpo))
        return _Resposta(404, _pagina("Não achei", "<p>Não achei</p>"))


@dataclass
class LeitorFalso:
    """Leitor de exemplo do site falso: lê o JSON capturado ou, sem ele, a lista em HTML."""

    base: str  # http://127.0.0.1:<porta>
    chave: str = "falso_logado"
    nome: str = "Site falso"
    hosts: tuple[str, ...] = ("127.0.0.1",)
    prefixos_login: tuple[str, ...] = ("::1/sso",)
    respostas: tuple[str, ...] = (r"127\.0\.0\.1/api/vagas",)
    campos_conta: tuple[str, ...] = ("#conta",)
    rolar: bool = False
    lista_tem_descricao: bool = True
    url_login: str = ""
    url_entrada: str = ""

    def __post_init__(self) -> None:
        self.url_login = self.url_login or f"{self.base}/login"
        self.url_entrada = self.url_entrada or f"{self.base}/logado"

    @classmethod
    def para(cls, site: SiteFalso, **mudancas: Any) -> LeitorFalso:
        return cls(base=site.url(""), **mudancas)

    def escopos(self, ctx: ContextoColeta) -> Sequence[EscopoLogado]:
        return [EscopoLogado(termo, f"{self.base}/lista-html?q={termo}") for termo in ctx.termos]

    def e_login(self, captura: Captura) -> bool:
        return "id='login'" in captura.html or 'id="login"' in captura.html

    def pagina_logada(self, html: str, url: str) -> bool:
        return 'id="conta"' in html or "id='conta'" in html

    def pagina_bloqueada(self, html: str, url: str) -> bool:
        return 'id="bloqueio"' in html or "id='bloqueio'" in html

    def proxima(self, captura: Captura) -> str | None:
        link = LexborHTMLParser(captura.html).css_first("#proxima")
        href = link.attributes.get("href") if link is not None else None
        return None if href is None else urljoin(captura.url, href)

    def ler(self, captura: Captura, escopo: EscopoLogado) -> Leitura:
        if captura.respostas:
            vagas: list[VagaColetada] = []
            for resposta in captura.respostas:
                for item in json.loads(resposta.texto)["vagas"]:
                    vagas.append(self._vaga(escopo, item["id"], item["titulo"], item["empresa"]))
            return Leitura(tuple(vagas), 0, False)
        lista = LexborHTMLParser(captura.html).css_first("#vagas")
        if lista is None:
            return Leitura((), 0, True)
        boas: list[VagaColetada] = []
        pulados = 0
        for li in lista.css("li.vaga"):
            link = li.css_first("a")
            empresa = li.css_first(".empresa")
            if link is None or empresa is None:
                pulados += 1
                continue
            boas.append(
                self._vaga(escopo, li.attributes.get("data-id") or "", link.text(), empresa.text())
            )
        if pulados and not boas:
            return Leitura((), pulados, True)
        return Leitura(tuple(boas), pulados, False)

    def detalhar(self, captura: Captura, vaga: VagaColetada) -> VagaColetada | None:
        descricao = LexborHTMLParser(captura.html).css_first("#descricao")
        if descricao is None:
            return None
        return replace(vaga, descricao=descricao.text())

    def _vaga(self, escopo: EscopoLogado, id_: str, titulo: str, empresa: str) -> VagaColetada:
        return VagaColetada(
            fonte=self.chave,
            escopo=escopo.id,
            url=f"{self.base}/vaga/{id_}",
            titulo=titulo,
            empresa=empresa,
            descricao_formato="texto",
            id_externo=id_,
        )


class RelogioDoNavegador(RelogioFalso):
    """Guarda as dormidas e avança a hora como o `RelogioFalso`, mas dorme de verdade até
    0,05 s, para os timers da página (JavaScript) andarem enquanto o navegador espera."""

    async def dormir(self, s: float) -> None:
        await super().dormir(s)
        await asyncio.sleep(min(s, 0.05))


# --- fixtures (importadas no `tests/navegador/conftest.py`) ----------------------------------
@pytest.fixture
def site() -> Iterator[SiteFalso]:
    with SiteFalso() as s:
        yield s


@pytest.fixture
def politica_local() -> Politica:
    """Aceita só o site falso em 127.0.0.1; o ::1 fica de fora, como um host que não é do leitor."""
    return lambda url: dentro_dos_hosts(url, ("127.0.0.1",))


@pytest.fixture
async def contexto_de_teste(tmp_path: Path) -> AsyncIterator[BrowserContext]:
    """Navegador sem tela pelo `lancar` injetado, com a rota que recusa tudo fora do loopback."""
    recusados: list[str] = []

    async def filtrar(route: Route) -> None:
        if urlsplit(route.request.url).hostname in LOCAIS:
            await route.continue_()
        else:
            recusados.append(route.request.url)
            await route.abort()

    async with async_playwright() as playwright:

        async def lancar(**argumentos: Any) -> BrowserContext:
            argumentos.pop("channel", None)  # sempre o Chromium do Playwright, igual no CI
            return await playwright.chromium.launch_persistent_context(**argumentos, headless=True)

        contexto = await abrir_contexto(tmp_path, {"DISPLAY": ":0"}, lancar)
        await contexto.route("**/*", filtrar)
        try:
            yield contexto
        finally:
            await contexto.close()
    assert recusados == [], f"pedido para fora do loopback: {recusados}"
