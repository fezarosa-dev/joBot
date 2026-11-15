import asyncio
import json
import shutil
import subprocess
from typing import cast

import pytest
from playwright.async_api import Page

from jobot.navegador import js

pytestmark = pytest.mark.anyio


class PaginaFalsa:
    """Guarda cada `evaluate` e devolve o que o teste mandou."""

    def __init__(self, devolve: object = None) -> None:
        self.chamadas: list[tuple[str, object]] = []
        self.devolve = devolve

    async def evaluate(self, expressao: str, arg: object = None) -> object:
        self.chamadas.append((expressao, arg))
        return self.devolve


def _pagina(falsa: PaginaFalsa) -> Page:
    return cast(Page, falsa)


@pytest.mark.parametrize("nome", ["a.b.c", "_x", "$cb", "cb", "a1.$b_2"])
def test_nome_de_retorno_valido(nome: str) -> None:
    assert js.nome_de_retorno_valido(nome)


@pytest.mark.parametrize("nome", ["alert(1)", "a..b", "1a", "a b", "", "a.", "a\n", "é"])
def test_nome_de_retorno_recusado(nome: str) -> None:
    assert not js.nome_de_retorno_valido(nome)


def test_scripts_sao_os_tres_do_desenho() -> None:
    assert js.ROLAR == "() => window.scrollBy(0, document.body.scrollHeight)"
    assert js.USER_AGENT == "() => navigator.userAgent"
    assert "=>" in js.ENTREGAR_TOKEN
    assert "eval" not in js.ENTREGAR_TOKEN.replace("native code", "")


async def test_rolar_manda_so_o_script() -> None:
    falsa = PaginaFalsa()
    async with asyncio.timeout(5):
        await js.rolar(_pagina(falsa))
    assert falsa.chamadas == [(js.ROLAR, None)]


async def test_entregar_token_leva_os_dados_como_argumento() -> None:
    falsa = PaginaFalsa(devolve=True)
    async with asyncio.timeout(5):
        chamou = await js.entregar_token(_pagina(falsa), "g-recaptcha-response", "tok'en", "a.cb")
    assert chamou is True
    assert falsa.chamadas == [(js.ENTREGAR_TOKEN, ["g-recaptcha-response", "tok'en", "a.cb"])]


async def test_entregar_token_sem_funcao_de_retorno() -> None:
    falsa = PaginaFalsa(devolve=False)
    async with asyncio.timeout(5):
        chamou = await js.entregar_token(_pagina(falsa), "cf-turnstile-response", "tok", None)
    assert chamou is False
    assert falsa.chamadas == [(js.ENTREGAR_TOKEN, ["cf-turnstile-response", "tok", None])]


@pytest.mark.parametrize("devolvido", [None, 1, "true", [True]])
async def test_entregar_token_so_aceita_true_de_verdade(devolvido: object) -> None:
    falsa = PaginaFalsa(devolve=devolvido)
    async with asyncio.timeout(5):
        assert await js.entregar_token(_pagina(falsa), "c", "t", "cb") is False


@pytest.mark.parametrize("nome", ["alert(1)", "a..b", "", "a b"])
async def test_entregar_token_nome_invalido_nao_toca_a_pagina(nome: str) -> None:
    falsa = PaginaFalsa(devolve=True)
    async with asyncio.timeout(5):
        assert await js.entregar_token(_pagina(falsa), "c", "t", nome) is False
    assert falsa.chamadas == []


_NODE = shutil.which("node")


def _roda_script(preparo: str, retorno: str | None) -> object:
    """Roda ENTREGAR_TOKEN no node com `window` e `document` falsos (preparo é JS do teste)."""
    codigo = (
        f"{preparo}\n"
        f"const f = eval('(' + {json.dumps(js.ENTREGAR_TOKEN)} + ')');\n"
        f"console.log(JSON.stringify(f(['c', 'tok', {json.dumps(retorno)}])));"
    )
    saida = subprocess.run([str(_NODE), "-e", codigo], capture_output=True, text=True, timeout=20)
    assert saida.returncode == 0, saida.stderr
    return json.loads(saida.stdout)


_DOC = "globalThis.document = {getElementsByName: () => []};\n"


@pytest.mark.skipif(_NODE is None, reason="precisa do node")
@pytest.mark.parametrize(
    ("preparo", "retorno", "esperado"),
    [
        # a função do site foi chamada e lançou: já entregou, continua True
        (_DOC + "globalThis.window = {cb: () => { throw new Error('x'); }};", "cb", True),
        (_DOC + "globalThis.window = {cb: () => {}};", "cb", True),
        # getter hostil no caminho: não leva a função, False e sem exceção
        (
            _DOC + "globalThis.window = {get a() { throw new Error('x'); }};",
            "a.b",
            False,
        ),
        # Proxy revogado: tratado como nativo ou o toString lança (conforme o motor);
        # em qualquer caso False e sem exceção
        (
            _DOC + "const r = Proxy.revocable(function () {}, {}); r.revoke();"
            "globalThis.window = {cb: r.proxy};",
            "cb",
            False,
        ),
        # a página trocou getElementsByName por algo que lança: nada entregue, False
        (
            "globalThis.document = {getElementsByName: () => { throw new Error('x'); }};"
            "globalThis.window = {cb: () => {}};",
            "cb",
            False,
        ),
        # campo com setter de value que lança: nada entregue, False e função do site não chamada
        (
            "globalThis.document = {getElementsByName: () => [{tagName: 'INPUT',"
            " set value(v) { throw new Error('x'); }}]};"
            "globalThis.window = {cb: () => { globalThis.chamou = true; }};",
            "cb",
            False,
        ),
        (_DOC + "globalThis.window = {};", "cb", False),
        (_DOC + "globalThis.window = {cb: eval};", "cb", False),
    ],
)
def test_script_de_entrega_nunca_lanca_erro_da_pagina(
    preparo: str, retorno: str, esperado: bool
) -> None:
    assert _roda_script(preparo, retorno) is esperado
