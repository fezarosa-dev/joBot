"""Teste ao ligar da aba IA (desenho 6.1 e 5.6 da fase 4; plano T416; D185.21, D203).

Ligar uma tarefa (ou trocar o par, a chave ou o endereço) grava, responde na hora e põe o par
(backend, modelo) numa fila: um teste por par, em ordem. Passou, ✓; falhou, o motivo, e a tarefa
fica desligada. A fábrica de backends (`app.state.ia`) é falsa: nada sai da máquina.
"""

import asyncio
import html as html_lib
import logging
import re
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import closing
from datetime import timedelta
from pathlib import Path
from typing import Any, get_args

import pytest
from fastapi.testclient import TestClient
from selectolax.lexbor import LexborHTMLParser

from apoio.cofre_falso import CofreFalso
from apoio.relogio import RelogioFalso
from jobot.banco import cadastros
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.cli import servir
from jobot.nucleo.ia.contrato import Falha, Motivo, Pedido, Resposta, conferir, limites
from jobot.painel.app import criar_app
from jobot.painel.i18n import carregar
from jobot.painel.rotas import ia
from jobot.painel.seguranca import CAMPO_CSRF
from jobot.sistema.cofre import Cofre

PORTA = 47619
BASE = f"http://127.0.0.1:{PORTA}"
IA = "/configuracoes/ia"
FRAGMENTO = IA + "/teste/encaixe"
CHAVE = "sk-ant-AbCd1234EfGh5678IjKl9012"
LOCAL = "Qwen3.5-4B-Q4_K_M"
ENDERECO = "http://127.0.0.1:11434/v1"
COMPATIVEL = ("compativel", "qwen3:4b")

Par = tuple[str, str]


class Fabrica:
    """`app.state.ia` falsa: um backend por par. Com `soltar` armado, cada pedido espera por ele;
    `erros[par]` é levantado no pedido e `ao_montar[par]` ao montar o backend."""

    def __init__(self, relogio: RelogioFalso) -> None:
        self.relogio = relogio
        self.pedidos: list[tuple[Par, Pedido]] = []
        self.erros: dict[Par, BaseException | list[BaseException]] = {}
        self.ao_montar: dict[Par, Falha] = {}
        self.soltar: threading.Event | None = None
        self.catraca: threading.Semaphore | None = None  # solta um pedido por `release`
        self.dentro = threading.Event()
        self.fechados = 0
        self.demora_s = 0.0  # quanto o relógio anda em cada pedido

    def __call__(self, backend: str, modelo: str) -> _Backend:
        par = (backend, modelo)
        if par in self.ao_montar:
            raise self.ao_montar[par]
        return _Backend(self, par)

    def encerrar(self) -> None:
        """O fim de `vida` chama (a `FabricaIA` derruba ali o `llama-server`)."""


class _Backend:
    def __init__(self, fabrica: Fabrica, par: Par) -> None:
        self.fabrica, self.par = fabrica, par

    def pedir(self, pedido: Pedido) -> Resposta:
        f = self.fabrica
        f.pedidos.append((self.par, pedido))
        f.dentro.set()
        if f.soltar is not None:
            assert f.soltar.wait(5)
        if f.catraca is not None:
            assert f.catraca.acquire(timeout=5)
        f.relogio._agora += timedelta(seconds=f.demora_s)
        erro = f.erros.get(self.par)
        if isinstance(erro, list):  # uma por pedido; acabou a lista, responde
            erro = erro.pop(0) if erro else None
        if erro is not None:
            raise erro
        return conferir(pedido, {"pede": ["Python"]}, self.par[0])

    def fechar(self) -> None:
        self.fabrica.fechados += 1


class Painel:
    """O app com o lifespan de pé (`with TestClient`): a fila do teste é uma tarefa de fundo."""

    def __init__(self, tmp_path: Path, http: TestClient, app: Any) -> None:
        self.banco = tmp_path / "jobot.db"
        self.http, self.app = http, app
        self.fabrica: Fabrica = getattr(app.state, "ia", None)  # type: ignore[assignment]
        self.cofre: Cofre = app.state.cofre
        self.token: str = app.state.csrf

    def post(self, dados: dict[str, Any], url: str = IA) -> Any:
        return self.http.post(url, data={CAMPO_CSRF: self.token} | dados)

    def ligar(self, backend: str, modelo: str, ligada: bool = True) -> Any:
        dados = {"encaixe_backend": backend, "encaixe_modelo": modelo}
        if ligada:
            dados["encaixe_ligada"] = "on"
        resposta = self.post(dados | ({"confirmar": "1"} if backend == "anthropic" else {}))
        assert resposta.status_code == 303
        return resposta

    def config(self, chave: str, valor: object) -> None:
        with closing(abrir(self.banco)) as con:
            cadastros.gravar_config(con, chave, valor)

    def tarefas(self) -> object:
        with closing(abrir(self.banco)) as con:
            return cadastros.ler_config(con, "ia_tarefas")

    def testes(self) -> dict[Par, Any]:
        testes: dict[Par, Any] = self.app.state.ia_testes
        return testes

    def parado(self) -> bool:
        """A fila andou até o fim: nenhum par esperando nem rodando."""
        return not getattr(self.app.state, "ia_fila", [])


def _app(tmp_path: Path) -> Any:
    banco = tmp_path / "jobot.db"
    with closing(abrir(banco)) as con:
        migrar(con, banco)
        cadastros.semear(con)
    app = criar_app(tmp_path, PORTA)
    relogio = RelogioFalso()
    app.state.cofre = Cofre(tmp_path, CofreFalso())
    app.state.relogio = relogio
    app.state.modelo_local = lambda: LOCAL
    app.state.ia_acordar = asyncio.Event()
    app.state.ia_pessoa = set()
    app.state.ia = Fabrica(relogio)
    return app


@pytest.fixture
def painel(tmp_path: Path) -> Iterator[Painel]:
    app = _app(tmp_path)
    with TestClient(
        app, base_url=BASE, follow_redirects=False, headers={"Accept-Language": "pt"}
    ) as http:
        p = Painel(tmp_path, http, app)
        p.config("ia_compativel", {"endereco": ENDERECO})
        p.cofre.gravar("ia_anthropic", CHAVE)
        yield p
        if p.fabrica.soltar is not None:
            p.fabrica.soltar.set()  # nenhum pedido preso no fim
        assert _esperar(p.parado)


def _esperar(condicao: Callable[[], bool], s: float = 5.0) -> bool:
    fim = time.monotonic() + s
    while not condicao():
        if time.monotonic() >= fim:
            return False
        time.sleep(0.01)
    return True


def _texto(html: str) -> str:
    html = re.sub(r'<dialog id="paleta".*?</dialog>', "", html, flags=re.S)
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", html)))


def pt(chave: str, **params: object) -> str:
    texto = carregar()["pt"][chave]
    return texto.format(**params) if params else texto


def _encaixe(ligada: bool, backend: str, modelo: str) -> dict[str, object]:
    return {"encaixe": {"ligada": ligada, "backend": backend, "modelo": modelo}}


# ------------------------------------------------------------------ fila e resposta


def test_ligar_responde_sem_esperar_e_poe_o_par_na_fila(painel: Painel) -> None:
    painel.fabrica.soltar = threading.Event()
    painel.ligar(*COMPATIVEL)  # responde com o pedido do teste ainda preso
    assert painel.fabrica.dentro.wait(5)
    assert painel.tarefas() == _encaixe(True, *COMPATIVEL)  # a escolha já está gravada
    assert painel.testes()[COMPATIVEL].estado == "testando"
    assert pt("configuracoes.ia.teste.testando") in _texto(painel.http.get(IA).text)
    painel.fabrica.soltar.set()
    assert _esperar(painel.parado)
    assert painel.testes()[COMPATIVEL].estado == "ok"
    assert [par for par, _ in painel.fabrica.pedidos] == [COMPATIVEL]
    assert painel.fabrica.fechados == 1  # o cliente do teste é fechado


def test_um_teste_por_par_em_ordem_com_o_prazo_de_cada_um(painel: Painel) -> None:
    """Prazo contado do começo de cada teste: o primeiro gasta 25 s do relógio, e o seguinte
    ainda tem o prazo inteiro (30 s fora, 180 s no local)."""
    painel.fabrica.soltar = threading.Event()
    painel.fabrica.demora_s = 25
    painel.ligar(*COMPATIVEL)
    assert painel.fabrica.dentro.wait(5)
    painel.ligar("local", LOCAL)  # entra atrás, enquanto o primeiro roda
    painel.ligar("compativel", "outro:1b")
    assert painel.app.state.ia_fila == [COMPATIVEL, ("local", LOCAL), ("compativel", "outro:1b")]
    painel.fabrica.soltar.set()
    assert _esperar(painel.parado)
    pedidos = painel.fabrica.pedidos
    assert [par for par, _ in pedidos] == [COMPATIVEL, ("local", LOCAL), ("compativel", "outro:1b")]
    prazo = limites()["prazo_teste_s"]
    assert [p.prazo_s for _, p in pedidos] == [prazo["fora"], prazo["local"], prazo["fora"]]
    assert prazo == {"fora": 30, "local": 180}


def test_pedido_do_teste_e_curto_com_exemplo_ficticio(painel: Painel) -> None:
    painel.ligar(*COMPATIVEL)
    assert _esperar(painel.parado)
    (_, pedido), *_ = painel.fabrica.pedidos
    assert pedido.tarefa == "encaixe"
    assert pedido.modelo == COMPATIVEL[1]
    assert pedido.max_tokens == limites()["max_tokens_teste"] == 256
    assert pedido.max_tokens < limites()["tarefas"]["encaixe"]["max_tokens"]["local"]
    assert "Python" in pedido.mensagens[1].texto  # o exemplo fixo, nenhuma vaga do banco


def test_tudo_offline_faz_um_teste_so_e_as_tarefas_dividem_o_resultado(
    painel: Painel, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Duas tarefas no mesmo par (a segunda só existe na 0.6.0: posta no `ia.json` aqui)."""
    monkeypatch.setitem(limites()["tarefas"], "outra", limites()["tarefas"]["encaixe"])
    painel.fabrica.erros[("local", LOCAL)] = Falha("contexto")
    assert painel.post({"atalho": "offline"}).status_code == 303
    assert _esperar(painel.parado)
    assert [par for par, _ in painel.fabrica.pedidos] == [("local", LOCAL)]
    desligada = {"ligada": False, "backend": "local", "modelo": LOCAL}
    assert painel.tarefas() == {"encaixe": desligada, "outra": desligada}  # as duas caem juntas


def test_sem_fabrica_nada_e_testado(tmp_path: Path) -> None:
    """(guarda) O app sem o `serve` não tem `app.state.ia`: grava como antes, sem fila."""
    app = _app(tmp_path)
    del app.state.ia
    with TestClient(app, base_url=BASE, follow_redirects=False) as http:
        p = Painel(tmp_path, http, app)
        p.config("ia_compativel", {"endereco": ENDERECO})
        p.ligar(*COMPATIVEL)
        assert p.tarefas() == _encaixe(True, *COMPATIVEL)
        assert getattr(app.state, "ia_fila", []) == []
        assert getattr(app.state, "ia_testes", {}) == {}
        assert app.state.ia_pessoa == set()


# ------------------------------------------------------------------ resultado


def test_estado_comeca_em_falha_e_so_vira_ok_no_fim(painel: Painel) -> None:
    """Um falso que levanta fora do contrato não deixa ✓: o estado começou em falha."""
    painel.fabrica.erros[COMPATIVEL] = RuntimeError("bug")
    painel.ligar(*COMPATIVEL)
    assert _esperar(painel.parado)
    teste = painel.testes()[COMPATIVEL]
    assert (teste.estado, teste.motivo) == ("falhou", "servico_fora")
    assert painel.tarefas() == _encaixe(False, *COMPATIVEL)
    assert painel.fabrica.fechados == 1  # fechado também na exceção


def test_controle_falso_que_responde_vira_ok(painel: Painel) -> None:
    painel.ligar(*COMPATIVEL)
    assert _esperar(painel.parado)
    assert painel.testes()[COMPATIVEL].estado == "ok"
    assert painel.tarefas() == _encaixe(True, *COMPATIVEL)
    assert pt("configuracoes.ia.teste.ok") in _texto(painel.http.get(IA).text)


@pytest.mark.parametrize("motivo", get_args(Motivo))
def test_falhou_a_tarefa_fica_desligada_com_o_motivo(painel: Painel, motivo: Motivo) -> None:
    painel.fabrica.erros[COMPATIVEL] = Falha(motivo)
    painel.ligar(*COMPATIVEL)
    assert _esperar(painel.parado)
    assert painel.tarefas() == _encaixe(False, *COMPATIVEL)  # o par fica, a tarefa desliga
    texto = _texto(painel.http.get(IA).text)
    assert pt("configuracoes.ia.teste.falhou", motivo=pt(f"configuracoes.ia.falha.{motivo}")) in (
        texto
    )


def test_falha_ao_montar_o_backend_tambem_desliga(painel: Painel) -> None:
    painel.fabrica.ao_montar[("openai", "gpt-5-mini")] = Falha("sem_chave")
    painel.cofre.gravar("ia_openai", "sk-1234567890")
    painel.post(
        {
            "encaixe_ligada": "on",
            "encaixe_backend": "openai",
            "encaixe_modelo": "gpt-5-mini",
            "confirmar": "1",
        }
    )
    assert _esperar(painel.parado)
    assert painel.tarefas() == _encaixe(False, "openai", "gpt-5-mini")
    assert painel.testes()[("openai", "gpt-5-mini")].motivo == "sem_chave"


def test_chave_recusada_na_anthropic_fala_do_workspace(painel: Painel) -> None:
    par = ("anthropic", "claude-haiku-5-5")
    painel.fabrica.erros[par] = Falha("chave_recusada")
    painel.ligar(*par)
    assert _esperar(painel.parado)
    texto = _texto(painel.http.get(IA).text)
    especial = pt("configuracoes.ia.falha.chave_recusada.anthropic")
    assert pt("configuracoes.ia.teste.falhou", motivo=especial) in texto
    assert pt("configuracoes.ia.falha.chave_recusada") not in texto


def test_falha_de_um_par_velho_nao_desliga_a_tarefa_ja_trocada(painel: Painel) -> None:
    painel.fabrica.soltar = threading.Event()
    painel.fabrica.erros[COMPATIVEL] = Falha("sem_rede")
    painel.ligar(*COMPATIVEL)
    assert painel.fabrica.dentro.wait(5)
    painel.ligar("local", LOCAL)  # trocou antes do resultado
    painel.fabrica.soltar.set()
    assert _esperar(painel.parado)
    assert painel.tarefas() == _encaixe(True, "local", LOCAL)


def test_cancelar_no_meio_nao_desliga_a_tarefa(painel: Painel) -> None:
    """O fim do servidor cancela a fila: a tarefa gravada fica como a pessoa deixou."""
    painel.fabrica.soltar = threading.Event()
    painel.ligar(*COMPATIVEL)
    assert painel.fabrica.dentro.wait(5)
    assert painel.http.portal is not None
    for tarefa in list(painel.app.state.tarefas):
        painel.http.portal.call(tarefa.cancel)
    assert _esperar(lambda: painel.testes()[COMPATIVEL].estado != "testando")
    painel.fabrica.soltar.set()
    assert painel.testes()[COMPATIVEL].estado == "falhou"  # nunca ✓ sem terminar
    assert painel.tarefas() == _encaixe(True, *COMPATIVEL)
    assert painel.app.state.ia_pessoa == set()


def test_teste_preso_vira_tempo_esgotado_e_a_fila_anda(
    painel: Painel, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Uma thread presa (cofre travado, servidor mudo) não segura a fila nem o laço: o teste
    inteiro tem prazo, e o par seguinte é testado."""
    monkeypatch.setitem(limites()["prazo_teste_s"], "fora", 0)
    monkeypatch.setattr(ia, "FOLGA_TESTE_S", 0.05)
    painel.fabrica.soltar = threading.Event()
    painel.ligar(*COMPATIVEL)
    assert painel.fabrica.dentro.wait(5)
    assert _esperar(lambda: painel.testes()[COMPATIVEL].estado != "testando")
    assert painel.testes()[COMPATIVEL].motivo == "tempo_esgotado"
    assert painel.tarefas() == _encaixe(False, *COMPATIVEL)
    assert painel.app.state.ia_pessoa == set()
    # fecha sem esperar a thread, que só solta com `soltar` (ou em 5 s)
    assert _esperar(lambda: painel.fabrica.fechados == 1, s=2)
    painel.fabrica.soltar.set()


# ------------------------------------------------------------------ quando repete


def test_teste_so_repete_quando_o_par_a_chave_ou_o_endereco_mudam(painel: Painel) -> None:
    def feitos() -> list[Par]:
        assert _esperar(painel.parado)
        return [par for par, _ in painel.fabrica.pedidos]

    painel.ligar(*COMPATIVEL)
    assert feitos() == [COMPATIVEL]
    painel.ligar(*COMPATIVEL)  # salvar de novo, igual
    painel.ligar(*COMPATIVEL, ligada=False)
    painel.ligar(*COMPATIVEL)  # desligar e religar o par que passou
    assert feitos() == [COMPATIVEL]
    painel.ligar("compativel", "outro:1b")  # o par mudou
    assert feitos() == [COMPATIVEL, ("compativel", "outro:1b")]
    painel.ligar(*COMPATIVEL)  # de volta ao par que já passou
    assert feitos() == [COMPATIVEL, ("compativel", "outro:1b")]
    painel.testes().clear()  # o servidor reiniciou: o resultado ficou na memória dele
    painel.ligar(*COMPATIVEL)  # salvar igual não testa
    assert feitos() == [COMPATIVEL, ("compativel", "outro:1b")]
    painel.ligar(*COMPATIVEL, ligada=False)
    painel.ligar(*COMPATIVEL)  # religar, sim
    assert feitos() == [COMPATIVEL, ("compativel", "outro:1b"), COMPATIVEL]

    servicos = "/configuracoes/servicos"
    antes = feitos()
    painel.post({"servico": "compativel", "endereco": ENDERECO}, servicos)  # o mesmo endereço
    assert feitos() == antes
    novo = "http://127.0.0.1:1234/v1"
    painel.post({"servico": "compativel", "endereco": novo}, servicos)
    assert feitos() == [*antes, COMPATIVEL]
    painel.post({"servico": "compativel", "endereco": "", "chave": "chave-nova-123"}, servicos)
    assert feitos() == [*antes, COMPATIVEL]  # 422: nada muda
    painel.post({"servico": "compativel", "endereco": novo, "chave": "chave-nova-123"}, servicos)
    assert feitos() == [*antes, COMPATIVEL, COMPATIVEL]


def test_chave_nova_do_servico_repete_so_os_pares_dele(painel: Painel) -> None:
    par = ("anthropic", "claude-haiku-5-5")
    painel.ligar(*par)
    assert _esperar(painel.parado)
    servicos = "/configuracoes/servicos"
    painel.post({"servico": "openai", "chave": "sk-0987654321"}, servicos)  # outro serviço
    assert _esperar(painel.parado)
    painel.ligar(*par, ligada=False)
    painel.ligar(*par)  # o ✓ da Anthropic continua valendo
    assert _esperar(painel.parado)
    assert [p for p, _ in painel.fabrica.pedidos] == [par]
    painel.post({"servico": "anthropic", "chave": "sk-ant-nova-12345678"}, servicos)
    assert _esperar(painel.parado)
    assert [p for p, _ in painel.fabrica.pedidos] == [par, par]


def test_chave_trocada_no_meio_do_teste_testa_de_novo_e_vale_o_segundo(painel: Painel) -> None:
    par = ("anthropic", "claude-haiku-5-5")
    painel.fabrica.catraca = threading.Semaphore(0)
    painel.fabrica.erros[par] = [Falha("chave_recusada")]  # a chave velha; a nova passa
    painel.ligar(*par)
    assert painel.fabrica.dentro.wait(5)
    painel.post(
        {"servico": "anthropic", "chave": "sk-ant-nova-12345678"}, "/configuracoes/servicos"
    )
    assert painel.app.state.ia_fila == [par, par]
    painel.fabrica.dentro.clear()
    painel.fabrica.catraca.release()  # o primeiro falha com a chave velha
    assert painel.fabrica.dentro.wait(5)  # o segundo já pediu e está preso
    assert painel.testes()[par].estado == "testando"  # o resultado velho não aparece
    assert par in painel.app.state.ia_pessoa  # o laço segue esperando
    assert painel.tarefas() == _encaixe(True, *par)  # a falha da chave velha não desligou
    painel.fabrica.catraca.release()
    assert _esperar(painel.parado)
    assert [p for p, _ in painel.fabrica.pedidos] == [par, par]
    assert painel.testes()[par].estado == "ok"
    assert painel.tarefas() == _encaixe(True, *par)
    assert painel.app.state.ia_pessoa == set()


def test_religar_depois_de_falhar_testa_de_novo(painel: Painel) -> None:
    """Falhou (sem rede, por exemplo): ligar outra vez é como a pessoa tenta de novo."""
    painel.fabrica.erros[COMPATIVEL] = Falha("sem_rede")
    painel.ligar(*COMPATIVEL)
    assert _esperar(painel.parado)
    del painel.fabrica.erros[COMPATIVEL]
    painel.ligar(*COMPATIVEL)
    assert _esperar(painel.parado)
    assert [par for par, _ in painel.fabrica.pedidos] == [COMPATIVEL, COMPATIVEL]
    assert painel.tarefas() == _encaixe(True, *COMPATIVEL)


# ------------------------------------------------------------------ tela


def _fieldset(html: str) -> Any:
    return LexborHTMLParser(html).css_first("fieldset#ia-encaixe")


def test_polling_de_2s_enquanto_testa(painel: Painel) -> None:
    painel.fabrica.soltar = threading.Event()
    painel.ligar(*COMPATIVEL)
    assert painel.fabrica.dentro.wait(5)
    grupo = _fieldset(painel.http.get(IA).text)
    assert grupo is not None
    assert grupo.attributes.get("hx-get") == FRAGMENTO
    assert grupo.attributes.get("hx-trigger") == "every 2s"
    assert grupo.attributes.get("hx-swap") == "outerHTML"
    assert painel.http.get(FRAGMENTO).status_code == 204  # enquanto testa, nada troca
    painel.fabrica.soltar.set()
    assert _esperar(painel.parado)
    fim = painel.http.get(FRAGMENTO)
    assert fim.status_code == 200
    grupo = _fieldset(fim.text)
    assert grupo is not None
    assert "hx-trigger" not in grupo.attributes  # o polling para
    resultado = LexborHTMLParser(fim.text).css_first("[data-foco-se-livre]")
    assert resultado is not None
    assert resultado.text().strip() == pt("configuracoes.ia.teste.ok")


def test_pagina_sem_teste_nao_pergunta(painel: Painel) -> None:
    grupo = _fieldset(painel.http.get(IA).text)
    assert grupo is not None
    assert "hx-trigger" not in grupo.attributes
    assert pt("configuracoes.ia.teste.testando") not in _texto(painel.http.get(IA).text)


def test_sem_javascript_o_testando_leva_a_recarregar(painel: Painel) -> None:
    painel.fabrica.soltar = threading.Event()
    painel.ligar(*COMPATIVEL)
    assert painel.fabrica.dentro.wait(5)
    noscript = LexborHTMLParser(painel.http.get(IA).text).css_first("fieldset noscript")
    assert noscript is not None
    miolo = html_lib.unescape(noscript.html or "")
    assert 'href="/configuracoes/ia"' in miolo
    assert pt("configuracoes.ia.teste.recarregar") in miolo


def test_fragmento_de_tarefa_desconhecida_e_404(painel: Painel) -> None:
    assert painel.http.get(IA + "/teste/nada").status_code == 404


@pytest.mark.parametrize("lingua", ["pt", "en"])
def test_textos_do_teste_nos_dois_catalogos(lingua: str) -> None:
    catalogo = carregar()[lingua]
    for chave in ("testando", "recarregar", "ok", "falhou"):
        assert catalogo.get(f"configuracoes.ia.teste.{chave}")
    assert "{motivo}" in catalogo["configuracoes.ia.teste.falhou"]


def test_log_do_teste_sem_a_chave(painel: Painel, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    par = ("anthropic", "claude-haiku-5-5")
    painel.fabrica.erros[par] = Falha("chave_recusada")
    painel.ligar(*par)
    assert _esperar(painel.parado)
    assert "chave_recusada" in caplog.text  # o motivo vai ao log
    assert CHAVE not in caplog.text


# ------------------------------------------------------------------ o laço espera


def test_pessoa_marcada_antes_de_acordar_o_laco_e_solta_no_fim(painel: Painel) -> None:
    painel.fabrica.soltar = threading.Event()
    painel.fabrica.erros[COMPATIVEL] = RuntimeError("bug")
    painel.ligar(*COMPATIVEL)
    assert painel.app.state.ia_acordar.is_set()
    assert COMPATIVEL in painel.app.state.ia_pessoa  # o laço já acorda esperando
    painel.fabrica.soltar.set()
    assert _esperar(painel.parado)
    assert painel.app.state.ia_pessoa == set()  # solto mesmo com a exceção


@pytest.mark.usefixtures("laco_versao_parado")
def test_o_laco_do_serve_espera_enquanto_o_teste_roda(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ocupados: list[Callable[[], bool]] = []

    async def laco_ia_falso(*_: Any, ocupado: Callable[[], bool]) -> None:
        ocupados.append(ocupado)
        await asyncio.Event().wait()

    async def parado(*_: object, **__: object) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(servir, "laco_ia", laco_ia_falso)
    monkeypatch.setattr(servir, "laco", parado)
    dados = tmp_path / "dados"
    dados.mkdir()
    relogio = RelogioFalso()
    app, _ = servir.montar(dados, PORTA, relogio=relogio)
    with TestClient(app, base_url=BASE, follow_redirects=False) as http:
        assert _esperar(lambda: bool(ocupados))
        fabrica = Fabrica(relogio)
        fabrica.soltar = threading.Event()
        app.state.ia = fabrica
        app.state.modelo_local = lambda: LOCAL
        dados_form = {"encaixe_ligada": "on", "encaixe_backend": "local", "encaixe_modelo": ""}
        assert http.post(IA, data={CAMPO_CSRF: app.state.csrf} | dados_form).status_code == 303
        assert fabrica.dentro.wait(5)
        assert ocupados[0]() is True  # o laço espera entre uma vaga e outra
        fabrica.soltar.set()
        assert _esperar(lambda: not app.state.ia_fila)
        assert ocupados[0]() is False


# ------------------------------------------------------------------ revisão da T416


def test_erro_ao_montar_o_pedido_nao_prende_a_fila(
    painel: Painel, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Um bug antes do pedido (montar o exemplo) não deixa o par em "testando" para sempre: a
    fila anda, os dois pares saem e o laço fica livre."""
    original = ia.pedido_de_teste

    def montar(backend: str, modelo: str) -> Pedido:
        if (backend, modelo) == COMPATIVEL:
            raise RuntimeError("bug")
        return original(backend, modelo)

    monkeypatch.setattr(ia, "pedido_de_teste", montar)
    painel.fabrica.soltar = threading.Event()
    painel.ligar("local", LOCAL)
    assert painel.fabrica.dentro.wait(5)
    painel.ligar(*COMPATIVEL)  # entra atrás do local, que está preso
    painel.fabrica.soltar.set()
    assert _esperar(painel.parado)
    assert painel.testes()[COMPATIVEL].estado == "falhou"
    assert painel.tarefas() == _encaixe(False, *COMPATIVEL)
    assert painel.app.state.ia_pessoa == set()
    assert painel.http.get(FRAGMENTO).status_code == 200  # o polling para


def test_erro_ao_desligar_nao_prende_a_fila(
    painel: Painel, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Erro fora do `sqlite3` ao desligar (disco) vai ao log: o par seguinte ainda é testado."""

    def quebrado(*_: object) -> None:
        raise OSError("disco")

    painel.fabrica.soltar = threading.Event()
    painel.fabrica.erros[COMPATIVEL] = Falha("sem_rede")
    painel.ligar(*COMPATIVEL)
    assert painel.fabrica.dentro.wait(5)
    painel.ligar("local", LOCAL)  # entra atrás
    monkeypatch.setattr(ia, "abrir", quebrado)
    painel.fabrica.soltar.set()
    assert _esperar(painel.parado)
    assert [par for par, _ in painel.fabrica.pedidos] == [COMPATIVEL, ("local", LOCAL)]
    assert painel.app.state.ia_pessoa == set()


def test_chave_nova_acorda_o_laco(painel: Painel) -> None:
    """A rodada em curso montou o cliente com a chave velha: acordar faz o laço refazer a rodada
    depois do teste, sem esperar a próxima busca."""
    par = ("anthropic", "claude-haiku-5-5")
    painel.ligar(*par)
    assert _esperar(painel.parado)
    painel.app.state.ia_acordar.clear()
    painel.post({"servico": "openai", "chave": "sk-0987654321"}, "/configuracoes/servicos")
    assert not painel.app.state.ia_acordar.is_set()  # nada ligado no serviço: não acorda
    painel.post(
        {"servico": "anthropic", "chave": "sk-ant-nova-12345678"}, "/configuracoes/servicos"
    )
    assert painel.app.state.ia_acordar.is_set()
    assert _esperar(painel.parado)


def test_resultado_e_anunciado_fora_da_tarefa_e_o_modo_atualiza(painel: Painel) -> None:
    """A região `#status-ia` fica fora do `fieldset` trocado e recebe o resultado em OOB; o "Modo"
    do topo vem junto, porque a tarefa pode ter desligado."""
    painel.fabrica.soltar = threading.Event()
    painel.fabrica.erros[("local", LOCAL)] = Falha("contexto")
    assert painel.post({"atalho": "offline"}).status_code == 303
    assert painel.fabrica.dentro.wait(5)
    pagina = LexborHTMLParser(painel.http.get(IA).text)
    regiao = pagina.css_first("#status-ia")
    assert regiao is not None
    assert regiao.attributes.get("role") == "status"
    assert regiao.text().strip() == ""
    assert pagina.css_first("fieldset #status-ia") is None
    assert pagina.css_first("fieldset [aria-live], fieldset [role=status]") is None
    modo = pagina.css_first("#ia-modo")
    assert modo is not None
    offline = pt("configuracoes.ia.modo", modo=pt("configuracoes.ia.modo.offline"))
    assert modo.text().strip() == offline
    painel.fabrica.soltar.set()
    assert _esperar(painel.parado)
    fim = LexborHTMLParser(painel.http.get(FRAGMENTO).text)
    anuncio = fim.css_first('[hx-swap-oob="innerHTML:#status-ia"]')
    assert anuncio is not None
    falhou = pt("configuracoes.ia.teste.falhou", motivo=pt("configuracoes.ia.falha.contexto"))
    assert _texto(anuncio.html or "").strip() == falhou
    modo = fim.css_first("p#ia-modo")
    assert modo is not None
    assert modo.attributes.get("hx-swap-oob") == "true"
    desligada = pt("configuracoes.ia.modo", modo=pt("configuracoes.ia.modo.desligada"))
    assert modo.text().strip() == desligada
