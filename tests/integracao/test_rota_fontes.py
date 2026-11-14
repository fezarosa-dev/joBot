"""Rota das fontes: saúde por fonte e escopo, ligar, desligar e link de reportar (T50)."""

import re
import time
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime, timedelta
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from apoio.relogio import RelogioFalso
from jobot.banco.cadastros import adicionar_empresa, semear
from jobot.banco.conexao import abrir
from jobot.banco.execucoes import abrir_execucao, fechar_execucao, gravar_saude
from jobot.banco.migrar import migrar
from jobot.nucleo.modelo import Empresa
from jobot.painel.app import criar_app
from jobot.painel.seguranca import CAMPO_CSRF

PORTA = 47618
AGORA = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
OK = ("ok", None)
MICROSOFT = "apply.careers.microsoft.com"


@pytest.fixture(autouse=True)
def _fuso_utc(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """O painel mostra a hora local: o teste fixa o fuso para o texto não depender da máquina."""
    monkeypatch.setenv("TZ", "UTC")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


class Painel:
    def __init__(self, tmp_path: Path, relogio: RelogioFalso | None = None) -> None:
        self.banco = tmp_path / "jobot.db"
        with closing(abrir(self.banco)) as con:
            migrar(con, self.banco)
            semear(con)
        self.app = criar_app(tmp_path, PORTA)
        self.app.state.relogio = relogio or RelogioFalso(AGORA)
        self.token: str = self.app.state.csrf
        self.http = TestClient(
            self.app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False
        )

    def execucao(
        self, inicio: datetime, *linhas: tuple[str, str, str, str | None, dict[str, Any]]
    ) -> None:
        """Uma busca concluída com as linhas de saúde (fonte, escopo, estado, motivo, extras)."""
        with closing(abrir(self.banco)) as con:
            id_ = abrir_execucao(con, "busca", "agenda", inicio)
            assert id_ is not None
            for fonte, escopo, estado, motivo, extras in linhas:
                gravar_saude(con, id_, fonte, escopo, estado, motivo=motivo, **extras)  # type: ignore[arg-type]
            fechar_execucao(con, id_, inicio + timedelta(minutes=5))

    def empresa(self, fonte: str, identificador: str) -> None:
        """Cadastra a empresa: só o identificador cadastrado pode ir no link de reportar."""
        with closing(abrir(self.banco)) as con:
            adicionar_empresa(
                con, Empresa(nome=identificador, fonte=fonte, identificador=identificador)
            )

    def sql(self, texto: str, *params: Any) -> list[tuple[Any, ...]]:
        with closing(abrir(self.banco)) as con:
            linhas = con.execute(texto, params).fetchall()
            con.commit()
        return [tuple(linha) for linha in linhas]

    def get(self, url: str = "/fontes", **cabecalhos: str) -> Any:
        return self.http.get(url, headers=cabecalhos)

    def post(self, url: str, dados: dict[str, Any] | None = None) -> Any:
        return self.http.post(url, data={CAMPO_CSRF: self.token, **(dados or {})})

    def cartao(self, chave: str) -> str:
        """O HTML do cartão da fonte: do `id` dela até o começo do cartão seguinte."""
        resposta = self.get()
        assert resposta.status_code == 200
        pagina: str = resposta.text
        inicio = pagina.find(f'id="fonte-{chave}"')
        assert inicio >= 0, f"sem cartão para {chave}"
        fim = pagina.find('<li class="cartao', inicio)
        return pagina[inicio : fim if fim >= 0 else len(pagina)]


def _texto(html: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).strip()


def _links_de_reporte(html: str) -> list[str]:
    return [unescape(h) for h in re.findall(r'<a [^>]*href="([^"]*issues/new[^"]*)"', html)]


@pytest.fixture
def painel(tmp_path: Path) -> Painel:
    return Painel(tmp_path)


def test_lista_toda_fonte_cadastrada_sem_execucao(painel: Painel) -> None:
    resposta = painel.get()
    assert resposta.status_code == 200
    total = painel.sql("SELECT count(*) FROM fonte")[0][0]
    assert len(re.findall(r'<li class="cartao[^"]*" id="fonte-', resposta.text)) == total
    assert "Ainda não rodou" in _texto(painel.cartao("remotive"))


def test_estado_motivo_traduzido_vagas_e_quando(painel: Painel) -> None:
    painel.execucao(
        AGORA - timedelta(hours=2),
        ("remotive", "", "ok", None, {"vagas": 42, "pedidos": 1, "duracao_ms": 1500}),
        ("jobicy", "", "falhou", "saude.formato_mudou", {"pedidos": 1, "duracao_ms": 300}),
        ("wwr", "geral", "parcial", "saude.excecao:KeyError", {"vagas": 3, "pedidos": 2}),
    )
    remotive = _texto(painel.cartao("remotive"))
    assert "Ok" in remotive
    assert "42" in remotive
    assert "1,5 s" in remotive
    assert "13/11 10:00" in remotive
    jobicy = _texto(painel.cartao("jobicy"))
    assert "Falhou" in jobicy
    assert "O formato da fonte mudou" in jobicy
    # a chave crua só aparece dentro da frase do link: é o que de fato vai na URL
    assert "saude.formato_mudou" not in jobicy.replace("o motivo (saude.formato_mudou)", "")
    assert "Erro inesperado: KeyError" in _texto(painel.cartao("wwr"))


def test_idioma_ingles_traduz_estado_e_motivo(painel: Painel) -> None:
    painel.execucao(
        AGORA - timedelta(hours=1),
        ("jobicy", "", "falhou", "saude.bloqueio", {"pedidos": 1}),
    )
    pagina = _texto(painel.get(**{"Accept-Language": "en"}).text)
    assert "Report a problem" in pagina
    assert "The source blocked access" in pagina
    assert "Failed" in pagina


def test_so_as_8_ultimas_execucoes_viram_pontos(painel: Painel) -> None:
    for n in range(10):
        estado = "falhou" if n == 9 else "ok"
        motivo = "saude.formato_mudou" if n == 9 else None
        painel.execucao(
            AGORA - timedelta(hours=10 - n), ("remotive", "", estado, motivo, {"pedidos": 1})
        )
    cartao = painel.cartao("remotive")
    pontos = re.findall(r'<li class="ponto ponto-(\w+)"', cartao)
    assert len(pontos) == 8
    assert pontos == ["ok"] * 7 + ["falhou"]  # da mais antiga para a mais recente


def test_execucao_sem_linha_da_fonte_vira_ponto_vazio(painel: Painel) -> None:
    painel.execucao(AGORA - timedelta(hours=3), ("remotive", "", "ok", None, {"pedidos": 1}))
    painel.execucao(AGORA - timedelta(hours=2), ("jobicy", "", "ok", None, {"pedidos": 1}))
    pontos = re.findall(r'<li class="ponto ponto-(\w+)"', painel.cartao("remotive"))
    assert pontos == ["ok", "vazio"]


def test_fonte_por_empresa_mostra_estado_de_cada_escopo(painel: Painel) -> None:
    # Eightfold aberto: a Microsoft tem intervalo próprio de 1440 min (fontes.json)
    painel.execucao(
        AGORA - timedelta(hours=20),
        (
            "eightfold",
            MICROSOFT,
            "ok",
            None,
            {"vagas": 9, "pedidos": 3},
        ),
        ("eightfold", "outra.example", "ok", None, {"vagas": 4, "pedidos": 2}),
    )
    painel.execucao(
        AGORA - timedelta(hours=1),
        ("eightfold", MICROSOFT, "no_limite", "saude.intervalo", {}),
        ("eightfold", "outra.example", "ok", None, {"vagas": 5, "pedidos": 2}),
        ("eightfold", "<b>negrito</b>", "ok", None, {"vagas": 1, "pedidos": 1}),
    )
    cartao = painel.cartao("eightfold")
    escopos = re.findall(r'<li class="escopo"[^>]*>(.*?)</li>', cartao, re.S)
    assert len(escopos) == 3
    por_nome = {_texto(e).split(" ")[0]: _texto(e) for e in escopos}
    microsoft = por_nome[MICROSOFT]
    assert "No limite" in microsoft
    # 20 h antes (16:00 do dia 12) + 1440 min = 16:00 do dia 13
    assert "pode rodar de novo em 13/11 16:00" in microsoft
    assert "Ok" in por_nome["outra.example"]
    assert "pode rodar" not in por_nome["outra.example"]
    # o escopo aparece como texto, como veio, sem separar, sem traduzir e sem virar HTML
    assert "&lt;b&gt;negrito&lt;/b&gt;" in cartao
    assert "<b>negrito</b>" not in cartao


def test_escopo_opaco_aparece_como_veio(painel: Painel) -> None:
    escopo = "empresa:acme:Carreiras da Acme|BR"
    painel.execucao(
        AGORA - timedelta(hours=1),
        ("gupy", escopo, "ok", None, {"vagas": 2, "pedidos": 1}),
        ("gupy", "cargo:python", "ok", None, {"vagas": 1, "pedidos": 1}),
    )
    texto = _texto(painel.cartao("gupy"))
    assert escopo in texto
    assert "cargo:python" in texto


def test_fonte_de_escopo_unico_nao_lista_escopos(painel: Painel) -> None:
    painel.execucao(AGORA - timedelta(hours=1), ("remotive", "", "ok", None, {"pedidos": 1}))
    assert 'class="escopo"' not in painel.cartao("remotive")


def test_no_limite_mostra_o_horario_em_que_a_fonte_pode_rodar(painel: Painel) -> None:
    # remotive: intervalo de 360 min; último pedido às 09:00 libera às 15:00
    painel.execucao(AGORA - timedelta(hours=3), ("remotive", "", "ok", None, {"pedidos": 1}))
    painel.execucao(
        AGORA - timedelta(minutes=30), ("remotive", "", "no_limite", "saude.intervalo", {})
    )
    texto = _texto(painel.cartao("remotive"))
    assert "No limite" in texto
    assert "pode rodar de novo em 13/11 15:00" in texto
    assert "O intervalo mínimo entre buscas ainda não passou" in texto


def test_mostra_proxima_execucao(painel: Painel) -> None:
    # busca completa iniciada às 10:30: a agenda roda de novo às 13:30 (3 h depois)
    painel.execucao(
        datetime(2026, 11, 13, 10, 30, tzinfo=UTC),
        ("remotive", "", "ok", None, {"pedidos": 1}),
        ("greenhouse", "acme", "ok", None, {"pedidos": 1}),
    )
    # remotive tem intervalo de 360 min: 10:30 + 6 h = 16:30, depois da agenda
    assert "Próxima execução 13/11 16:30" in _texto(painel.cartao("remotive"))
    # greenhouse não tem intervalo: vale a agenda
    assert "Próxima execução 13/11 13:30" in _texto(painel.cartao("greenhouse"))


def test_proxima_execucao_vencida_diz_na_proxima_busca(tmp_path: Path) -> None:
    painel = Painel(tmp_path, RelogioFalso(AGORA + timedelta(days=1)))
    painel.execucao(AGORA - timedelta(hours=5), ("greenhouse", "acme", "ok", None, {"pedidos": 1}))
    assert "Próxima execução na próxima busca" in _texto(painel.cartao("greenhouse"))


def test_relogio_voltou_conta_como_vencido(tmp_path: Path) -> None:
    painel = Painel(tmp_path, RelogioFalso(AGORA - timedelta(days=2)))  # última busca no futuro
    painel.execucao(AGORA, ("remotive", "", "ok", None, {"pedidos": 1}))
    assert "Próxima execução na próxima busca" in _texto(painel.cartao("remotive"))


def test_desligar_muda_para_desligada_e_ligar_volta(painel: Painel) -> None:
    painel.execucao(AGORA - timedelta(hours=1), ("remotive", "", "ok", None, {"pedidos": 1}))
    assert "Ok" in _texto(painel.cartao("remotive"))

    resposta = painel.post("/fontes/remotive/desligar")
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/fontes"
    assert painel.sql("SELECT ligada FROM fonte WHERE chave='remotive'") == [(0,)]
    cartao = _texto(painel.cartao("remotive"))
    assert "Desligada" in cartao
    assert "Ligar" in cartao
    assert "Próxima execução" not in cartao

    assert painel.post("/fontes/remotive/ligar").status_code == 303
    assert painel.sql("SELECT ligada FROM fonte WHERE chave='remotive'") == [(1,)]
    assert "Desligada" not in _texto(painel.cartao("remotive"))


def test_ligar_e_desligar_fonte_inexistente_404(painel: Painel) -> None:
    assert painel.post("/fontes/nao_existe/ligar").status_code == 404
    assert painel.post("/fontes/nao_existe/desligar").status_code == 404


def test_ligar_sem_token_csrf_403(painel: Painel) -> None:
    assert painel.http.post("/fontes/remotive/desligar").status_code == 403
    assert painel.sql("SELECT ligada FROM fonte WHERE chave='remotive'") == [(1,)]


def test_link_vem_com_a_frase_do_que_vai_na_url(painel: Painel) -> None:
    painel.empresa("greenhouse", "acme&motivo=x#y")
    painel.execucao(
        AGORA - timedelta(hours=1),
        ("greenhouse", "acme&motivo=x#y", "falhou", "saude.formato_mudou:3", {"pedidos": 1}),
        ("greenhouse", "beta", "ok", None, {"vagas": 1, "pedidos": 1}),
    )
    cartao = painel.cartao("greenhouse")
    (link,) = _links_de_reporte(cartao)
    consulta = parse_qs(urlsplit(link).query)
    assert set(consulta) == {"template", "fonte", "motivo"}
    assert consulta["fonte"] == ["greenhouse/acme&motivo=x#y"]
    assert consulta["motivo"] == ["saude.formato_mudou"]
    frase = (
        "Ao clicar, o GitHub abre com a fonte (greenhouse/acme&motivo=x#y)"
        " e o motivo (saude.formato_mudou) já preenchidos."
    )
    assert frase in _texto(cartao)


def test_link_na_tela_so_em_fonte_quebrada(painel: Painel) -> None:
    painel.execucao(
        AGORA - timedelta(hours=1),
        ("remotive", "", "ok", None, {"vagas": 1, "pedidos": 1}),
        ("remoteok", "", "falhou", "saude.formato_mudou", {"pedidos": 1}),
        ("jobicy", "", "parcial", "saude.erro_de_rede", {"vagas": 1, "pedidos": 1}),
        ("himalayas", "", "falhou", "saude.excecao:KeyError", {"pedidos": 1}),
        ("wwr", "", "parcial", "saude.sem_detalhe_n:3", {"vagas": 5, "pedidos": 1}),
        ("hn_algolia", "", "no_limite", "saude.intervalo", {}),
        ("lever", "", "no_limite", "saude.orcamento", {}),
        ("ashby", "", "falhou", "saude.parou_429", {"pedidos": 1}),
        ("gupy", "", "falhou", "saude.bloqueio", {"pedidos": 1}),
    )
    painel.post("/fontes/greenhouse/desligar")
    for chave in ("remoteok", "jobicy", "gupy"):
        (link,) = _links_de_reporte(painel.cartao(chave))
        assert parse_qs(urlsplit(link).query)["fonte"] == [chave]
    for chave in ("remotive", "himalayas", "wwr", "hn_algolia", "lever", "ashby", "greenhouse"):
        assert _links_de_reporte(painel.cartao(chave)) == [], chave
    pagina = painel.get().text
    for a in re.findall(r"<a [^>]*issues/new[^>]*>", pagina):
        assert 'rel="noopener noreferrer"' in a
        assert 'target="_blank"' in a


def test_fonte_desligada_com_ultimo_estado_falhou_nao_leva_link(painel: Painel) -> None:
    painel.execucao(
        AGORA - timedelta(hours=1), ("remoteok", "", "falhou", "saude.formato_mudou", {})
    )
    painel.post("/fontes/remoteok/desligar")
    assert _links_de_reporte(painel.cartao("remoteok")) == []


def test_pagina_nao_aponta_para_fora_nem_faz_pedido_sozinha(painel: Painel) -> None:
    painel.execucao(
        AGORA - timedelta(hours=1), ("remoteok", "", "falhou", "saude.formato_mudou", {})
    )
    pagina = painel.get().text
    # só `<a href>` aponta para fora (e só o de reportar); nada que o navegador busque sozinho
    assert not re.search(
        r'<(?:script|img|iframe|link|source|video|audio)[^>]+(?:src|href)="https?:', pagina
    )
    assert " ping=" not in pagina
    externos = re.findall(r'(?:src|href|action)="(https?://[^"]*)"', pagina)
    # o rodapé da casca leva o link "Apoie o projeto" (T87), da wiki: sem query, só clique
    externos = [
        u for u in externos if not u.startswith("https://github.com/fezarosa-dev/joBot/wiki/")
    ]
    assert externos
    assert all(u.startswith("https://github.com/fezarosa-dev/joBot/issues/new?") for u in externos)


def _reportes(html: str) -> list[str]:
    """O texto de cada bloco "reportar problema" (link e frase)."""
    return [_texto(b) for b in re.findall(r'<p class="reportar">(.*?)</p>', html, re.S)]


def test_escopo_de_busca_nao_vira_identificador_no_link(painel: Painel) -> None:
    # na Himalayas e na Gupy o escopo sai dos termos de busca da pessoa (D50): nunca vai na URL
    painel.execucao(
        AGORA - timedelta(hours=1),
        ("himalayas", "BR|desenvolvedor python", "falhou", "saude.formato_mudou", {}),
        ("himalayas", "US|engenheiro de dados", "falhou", "saude.formato_mudou", {}),
        ("gupy", "cargo:python", "falhou", "saude.bloqueio", {}),
        ("smartrecruiters", "acme|BR", "parcial", "saude.erro_de_rede", {}),
    )
    for chave in ("himalayas", "gupy", "smartrecruiters"):
        cartao = painel.cartao(chave)
        (link,) = _links_de_reporte(cartao)  # um só, não um por escopo
        assert parse_qs(urlsplit(link).query)["fonte"] == [chave]
        for termo in ("python", "BR", "dados", "cargo", "acme"):
            assert termo not in link
            assert not any(termo in b for b in _reportes(cartao))


def test_escopo_cadastrado_leva_o_identificador_e_o_de_busca_so_a_chave(painel: Painel) -> None:
    painel.empresa("greenhouse", "acme")
    painel.execucao(
        AGORA - timedelta(hours=1),
        ("greenhouse", "acme", "falhou", "saude.formato_mudou", {}),
        ("greenhouse", "nao-cadastrada", "falhou", "saude.bloqueio", {}),
        ("greenhouse", "beta", "ok", None, {"vagas": 1, "pedidos": 1}),
    )
    fontes = sorted(
        parse_qs(urlsplit(link).query)["fonte"][0]
        for link in _links_de_reporte(painel.cartao("greenhouse"))
    )
    assert fontes == ["greenhouse", "greenhouse/acme"]


def test_escopo_cadastrado_so_gera_link_do_cartao_se_algum_escopo_nao_e_empresa(
    painel: Painel,
) -> None:
    painel.empresa("greenhouse", "acme")
    painel.execucao(
        AGORA - timedelta(hours=1),
        ("greenhouse", "acme", "falhou", "saude.formato_mudou", {}),
        ("greenhouse", "beta", "ok", None, {"vagas": 1, "pedidos": 1}),
    )
    fontes = [
        parse_qs(urlsplit(link).query)["fonte"][0]
        for link in _links_de_reporte(painel.cartao("greenhouse"))
    ]
    assert fontes == ["greenhouse/acme"]


def test_fonte_com_escopos_desligada_nao_leva_link(painel: Painel) -> None:
    painel.empresa("greenhouse", "acme")
    painel.execucao(
        AGORA - timedelta(hours=1),
        ("greenhouse", "acme", "falhou", "saude.formato_mudou", {}),
        ("greenhouse", "outra", "falhou", "saude.bloqueio", {}),
    )
    assert len(_links_de_reporte(painel.cartao("greenhouse"))) == 2
    painel.post("/fontes/greenhouse/desligar")
    assert _links_de_reporte(painel.cartao("greenhouse")) == []


def test_cartao_ok_nao_mostra_o_motivo_de_um_escopo_no_limite(painel: Painel) -> None:
    painel.execucao(
        AGORA - timedelta(hours=1),
        ("eightfold", MICROSOFT, "no_limite", "saude.intervalo", {}),
        ("eightfold", "outra.example", "ok", None, {"vagas": 5, "pedidos": 2}),
    )
    cartao = painel.cartao("eightfold")
    assert 'class="selo selo-ok"' in cartao.split("<details")[0]
    assert '<p class="motivo">' not in cartao  # o motivo do escopo fica na lista de escopos
    assert "intervalo mínimo" in _texto(cartao)
