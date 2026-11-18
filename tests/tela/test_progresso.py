"""Componente de progresso na barra do topo, no navegador (plano T252; desenho 5.9).

A busca é montada direto no banco (execução `rodando` com andamento); a casca a mostra na carga e
a pergunta de 2 s traz as mudanças. O relógio do painel fica parado: o valor só muda com o banco.
"""

import asyncio
import re
import threading
from collections.abc import Mapping
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from playwright.sync_api import Page, expect

from apoio.console import anotar_erros
from apoio.relogio import RelogioFalso
from jobot.banco.andamento import abrir_andamento, marcar_fonte, mudar_etapa, planejar
from jobot.banco.cadastros import semear as semear_fontes
from jobot.banco.conexao import abrir
from jobot.banco.execucoes import abrir_execucao, fechar_execucao
from jobot.painel.rotas import execucao as rota

pytestmark = pytest.mark.tela

AGORA = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
ETAPAS = ("coleta", "detalhes", "cotacoes", "encaixe")

# largura do preenchimento em % do trilho, e o aria-valuenow, lidos na página
LARGURA = """() => {
  const trilho = document.querySelector("#andamento [role=progressbar]");
  const preenchimento = document.getElementById("andamento-preenchimento");
  if (!trilho || !preenchimento) return null;
  const total = trilho.getBoundingClientRect().width;
  return {
    valor: trilho.getAttribute("aria-valuenow"),
    largura: (preenchimento.getBoundingClientRect().width / total) * 100,
  };
}"""


@pytest.fixture
def app_painel(app_painel: FastAPI) -> FastAPI:
    app_painel.state.relogio = RelogioFalso(AGORA)
    app_painel.state.travas = {"busca": asyncio.Lock()}
    app_painel.state.cliente = None
    return app_painel


def _busca(banco: Path, totais: Mapping[str, int] | None = None) -> int:
    with closing(abrir(banco)) as con:
        semear_fontes(con)  # andamento_fonte aponta para fonte(chave)
        id_ = abrir_execucao(con, "busca", "agenda", AGORA)
        assert id_ is not None
        abrir_andamento(con, id_, ETAPAS, AGORA)
        if totais is not None:
            planejar(con, id_, totais, AGORA)
    return id_


def _etapa(banco: Path, id_: int, etapa: str, feitas: int, total: int) -> None:
    with closing(abrir(banco)) as con:
        mudar_etapa(con, id_, etapa, feitas, total, 0.0, AGORA)


def _medir(page: Page) -> dict[str, Any]:
    medida = page.evaluate(LARGURA)
    assert medida is not None, "sem a barra na página"
    return medida  # type: ignore[no-any-return]


def _esperar_valor_novo(page: Page, antes: str) -> dict[str, Any]:
    """A primeira medida, quadro a quadro, depois que o aria-valuenow muda."""
    achado = page.wait_for_function(
        f"""() => {{
          const m = ({LARGURA})();
          return m && m.valor !== null && m.valor !== {antes!r} ? m : null;
        }}""",
        polling="raf",
    )
    return achado.json_value()  # type: ignore[no-any-return]


def _amostrar(page: Page) -> None:
    """Guarda em window.__amostras a medida de cada quadro, até `_parar`."""
    page.evaluate(
        f"""() => {{
          window.__amostras = [];
          const medir = {LARGURA};
          const passo = () => {{
            window.__amostras.push(medir());
            if (!window.__parar) requestAnimationFrame(passo);
          }};
          requestAnimationFrame(passo);
        }}"""
    )


def _parar(page: Page) -> list[dict[str, Any] | None]:
    return page.evaluate("() => { window.__parar = true; return window.__amostras; }")  # type: ignore[no-any-return]


def _carregar(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    expect(page.locator("#andamento").get_by_role("progressbar")).to_be_visible()


def _terminar_animacoes(page: Page) -> None:
    """Põe a animação da largura no fim: ela anda no relógio do navegador, que `page.clock` não
    move. A indeterminada (infinita) fica de fora."""
    page.evaluate(
        """() => document.getElementById("andamento-preenchimento")
          ?.getAnimations().filter((a) => a.effect.getComputedTiming().endTime !== Infinity)
          .forEach((a) => a.finish())"""
    )


def _proxima_pergunta(page: Page) -> None:
    """Adianta o relógio da página até a pergunta de 2 em 2 s do andamento
    (`hx-trigger="every 2s"`), sem esperar os 2 s de verdade. Cada teste instala o relógio
    (`page.clock.install()`) antes do `goto`."""
    page.clock.fast_forward(2000)


def _assentar(page: Page) -> dict[str, Any]:
    """Leva a largura ao aria-valuenow (a animação de entrada, de até 2 s, termina na hora)."""
    _terminar_animacoes(page)
    page.wait_for_function(
        f"() => {{ const m = ({LARGURA})(); return m && Math.abs(m.largura - m.valor) < 0.5; }}"
    )
    return _medir(page)


def test_largura_anda_entre_perguntas(page: Page, painel: str, app_painel: FastAPI) -> None:
    banco = app_painel.state.banco
    id_ = _busca(banco, {"gupy": 10})
    _etapa(banco, id_, "coleta", 1, 10)
    page.clock.install()
    _carregar(page, painel)
    antes = _assentar(page)
    _etapa(banco, id_, "coleta", 9, 10)
    _proxima_pergunta(page)
    depois = _esperar_valor_novo(page, antes["valor"])
    alvo = float(depois["valor"])
    assert alvo > float(antes["valor"]) + 10
    # logo depois da troca, a largura ainda está no caminho: a transição de 2 s anda
    assert float(antes["valor"]) - 1 <= depois["largura"] < alvo - 2, (antes, depois)
    _terminar_animacoes(page)  # o fim da animação, sem esperar os 2 s dela
    assert abs(_medir(page)["largura"] - alvo) < 0.5


def test_barra_continua_entre_perguntas(page: Page, painel: str, app_painel: FastAPI) -> None:
    banco = app_painel.state.banco
    id_ = _busca(banco, {"gupy": 10})
    _etapa(banco, id_, "coleta", 4, 10)
    page.clock.install()
    _carregar(page, painel)
    antes = _assentar(page)
    _amostrar(page)
    _etapa(banco, id_, "coleta", 6, 10)
    _proxima_pergunta(page)
    novo = _esperar_valor_novo(page, antes["valor"])
    # amostras de quadros já com o valor novo, com a animação ainda andando (espera por estado)
    page.wait_for_function(
        "(v) => window.__amostras.filter((a) => a && a.valor === v).length >= 3", arg=novo["valor"]
    )
    _terminar_animacoes(page)
    assert abs(_medir(page)["largura"] - float(novo["valor"])) < 0.5
    amostras = _parar(page)
    # a barra nunca some nem volta a zero na troca da pergunta
    assert amostras and all(a is not None for a in amostras)
    assert min(a["largura"] for a in amostras if a) >= float(antes["valor"]) - 1


def test_regiao_viva_e_o_mesmo_no(page: Page, painel: str, app_painel: FastAPI) -> None:
    banco = app_painel.state.banco
    id_ = _busca(banco, {"gupy": 4})
    _etapa(banco, id_, "coleta", 1, 4)
    page.clock.install()
    _carregar(page, painel)
    viva = page.locator("#andamento-etapa")
    expect(viva).to_have_text("Lendo as fontes")
    page.evaluate('() => { window.__no = document.getElementById("andamento-etapa"); }')
    _etapa(banco, id_, "detalhes", 0, 3)
    _proxima_pergunta(page)
    expect(viva).to_have_text("Completando os detalhes das vagas")
    assert page.evaluate('() => document.getElementById("andamento-etapa") === window.__no')
    expect(viva).to_have_attribute("role", "status")
    expect(viva).to_have_attribute("aria-live", "polite")


def test_ver_detalhes_abre_e_esc_fecha(page: Page, painel: str, app_painel: FastAPI) -> None:
    banco = app_painel.state.banco
    id_ = _busca(banco, {"gupy": 3, "lever": 2})
    with closing(abrir(banco)) as con:
        marcar_fonte(con, id_, "gupy", "pronto", feitas=3)
        marcar_fonte(con, id_, "lever", "lendo", feitas=1)
    _etapa(banco, id_, "coleta", 4, 5)
    _carregar(page, painel)
    botao = page.get_by_role("button", name="Ver detalhes do andamento")
    detalhes = page.locator("#andamento-detalhes")
    botao.click()
    expect(detalhes).to_be_visible()
    linha_lever = detalhes.locator("li").filter(has_text="Lever")
    expect(linha_lever).to_contain_text("Lendo")
    expect(linha_lever).to_contain_text("1 de 2")
    expect(linha_lever.locator('[data-icone="book-open"]')).to_have_count(1)
    expect(detalhes.locator("li").filter(has_text="Gupy")).to_contain_text("Pronto")
    page.keyboard.press("Escape")
    expect(detalhes).to_be_hidden()
    expect(botao).to_be_focused()
    # clique fora também fecha
    botao.click()
    expect(detalhes).to_be_visible()
    page.locator("#conteudo").click(position={"x": 5, "y": 5})
    expect(detalhes).to_be_hidden()


def test_espera_curta_nao_mostra(
    page: Page, painel: str, app_painel: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    banco = app_painel.state.banco

    async def curta(con: Any, cliente: Any, relogio: Any, motivo: str, **kw: Any) -> int:
        with closing(abrir(banco)) as propria:
            id_ = abrir_execucao(propria, "busca", "agora", datetime.now(UTC))
            assert id_ is not None
            fechar_execucao(propria, id_, datetime.now(UTC))
        return id_

    monkeypatch.setattr(rota, "executar_busca", curta)
    page.goto(f"{painel}/vagas?aba=todas")
    # quadro a quadro: a linha "Preparando" nunca fica visível
    page.evaluate(
        """() => {
          window.__viu = [];
          const passo = () => {
            const linha = document.querySelector("#andamento .progresso-linha");
            if (linha && linha.checkVisibility({ opacityProperty: true, visibilityProperty: true }))
              window.__viu.push(linha.textContent.trim());
            if (!window.__parar) requestAnimationFrame(passo);
          };
          requestAnimationFrame(passo);
        }"""
    )
    page.get_by_role("banner").get_by_role("button", name="Buscar agora").click()
    regiao = page.locator("#andamento")
    expect(regiao.locator(".progresso-linha")).to_have_text(
        re.compile(r"Pronto\. Vagas novas: \d+\.")
    )
    expect(regiao.locator(".progresso-linha")).to_be_visible()
    vistos = page.evaluate("() => { window.__parar = true; return window.__viu; }")
    assert "Preparando as consultas" not in vistos, vistos


def test_movimento_reduzido_sem_transicao(page: Page, painel: str, app_painel: FastAPI) -> None:
    page.emulate_media(reduced_motion="reduce")
    banco = app_painel.state.banco
    id_ = _busca(banco)  # sem total: indeterminada
    page.clock.install()
    _carregar(page, painel)
    preenchimento = page.locator("#andamento-preenchimento")
    expect(preenchimento).to_have_class("progresso-preenchimento indeterminado")
    parada = page.evaluate(
        """() => {
          const p = document.getElementById("andamento-preenchimento");
          const trilho = p.parentElement.getBoundingClientRect().width;
          return {
            largura: (p.getBoundingClientRect().width / trilho) * 100,
            opacidade: getComputedStyle(p).opacity,
            animacoes: p.getAnimations().length,
          };
        }"""
    )
    # a indeterminada fica parada, com o trilho cheio a 40%
    assert abs(parada["largura"] - 100) < 0.5
    assert parada["opacidade"] == "0.4"
    assert parada["animacoes"] == 0
    with closing(abrir(banco)) as con:
        planejar(con, id_, {"gupy": 10}, AGORA)
    _etapa(banco, id_, "coleta", 5, 10)
    _proxima_pergunta(page)
    depois = _esperar_valor_novo(page, "")
    # sem transição: a largura já chega no valor no primeiro quadro
    assert abs(depois["largura"] - float(depois["valor"])) < 0.5, depois


def test_um_clique_acompanha_ate_o_fim(
    page: Page, painel: str, app_painel: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Um só clique: a pergunta de 2 s continua depois da entrada e o fim aparece sem trocar de
    página. Dois cliques escondem o caminho, porque a resposta do segundo troca o envoltório."""
    banco = app_painel.state.banco
    liberar = threading.Event()
    fechou = threading.Event()
    ids: list[int] = []

    async def lenta(con: Any, cliente: Any, relogio: Any, motivo: str, **kw: Any) -> int:
        id_ = _busca(banco, {"gupy": 10})
        _etapa(banco, id_, "coleta", 1, 10)
        ids.append(id_)
        while not liberar.is_set():
            await asyncio.sleep(0.02)
        with closing(abrir(banco)) as con_:
            fechar_execucao(con_, id_, AGORA + timedelta(minutes=1))
        fechou.set()
        return id_

    monkeypatch.setattr(rota, "executar_busca", lenta)
    erros = anotar_erros(page)
    page.clock.install()
    page.goto(f"{painel}/vagas?aba=todas")
    page.get_by_role("banner").get_by_role("button", name="Buscar agora").click()
    barra = page.locator("#andamento").get_by_role("progressbar")
    expect(barra).to_have_attribute("aria-valuenow", re.compile(r"\d"))
    antes = barra.get_attribute("aria-valuenow")
    assert ids
    _etapa(banco, ids[0], "coleta", 9, 10)
    _proxima_pergunta(page)  # só a pergunta de 2 s traz o valor novo
    expect(barra).not_to_have_attribute("aria-valuenow", antes or "")
    liberar.set()
    assert fechou.wait(5)
    _proxima_pergunta(page)
    expect(page.locator("#andamento .progresso-linha")).to_have_text(
        re.compile(r"Pronto\. Vagas novas: \d+\.")
    )
    assert erros == []


def test_ver_detalhes_dentro_da_janela(page: Page, painel: str, app_painel: FastAPI) -> None:
    """T301 item 7: o popover inteiro à vista, a 8px da borda; estado e contagem numa linha cada;
    o gatilho da etapa responde ao hover."""
    page.set_viewport_size({"width": 1280, "height": 800})
    banco = app_painel.state.banco
    id_ = _busca(banco, {"gupy": 10, "lever": 6, "greenhouse": 4})
    with closing(abrir(banco)) as con:
        marcar_fonte(con, id_, "gupy", "pronto", feitas=10)
        marcar_fonte(
            con,
            id_,
            "lever",
            "esperando",
            feitas=2,
            espera_ate=AGORA + timedelta(seconds=40),
            espera_motivo="limite",
        )
        marcar_fonte(con, id_, "greenhouse", "lendo", feitas=1)
    _etapa(banco, id_, "coleta", 13, 20)
    _carregar(page, painel)
    gatilho = page.get_by_role("button", name="Ver detalhes do andamento")
    fundo = gatilho.evaluate("el => getComputedStyle(el).backgroundColor")
    borda = gatilho.evaluate("el => getComputedStyle(el).borderTopStyle")
    gatilho.hover()
    page.wait_for_function(
        "([f, b]) => { const s = getComputedStyle(document.querySelector('.progresso-ver'));"
        " return s.backgroundColor !== f || s.borderTopStyle !== b; }",
        arg=[fundo, borda],
    )
    gatilho.click()
    detalhes = page.locator("#andamento-detalhes")
    expect(detalhes).to_be_visible()
    x, topo, direita, base = detalhes.evaluate(
        "el => { const r = el.getBoundingClientRect(); return [r.x, r.y, r.right, r.bottom]; }"
    )
    assert x >= 0 and topo >= 0 and base <= 800
    ancora_x, _, ancora_direita, _ = gatilho.evaluate(
        "el => { const r = el.closest('.progresso').getBoundingClientRect();"
        " return [r.x, r.y, r.right, r.bottom]; }"
    )
    # alinhado à esquerda do componente ele passaria da margem de 8px: o teste prova a virada
    assert ancora_x + (direita - x) + 8 > 1280
    assert abs(direita - ancora_direita) <= 1
    assert direita <= 1280 - 8
    linhas = detalhes.locator(".progresso-estado, .progresso-conta").evaluate_all(
        "es => es.map(e => [e.getBoundingClientRect().height,"
        " parseFloat(getComputedStyle(e).lineHeight)])"
    )
    assert len(linhas) >= 6
    for altura, entrelinha in linhas:
        assert altura <= 1.5 * entrelinha
