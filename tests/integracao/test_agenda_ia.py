"""Laço das habilidades (T412; desenho 5.4 da fase 4, D185.12).

Banco de verdade numa pasta temporária, `BackendFalso` com respostas prontas e `RelogioFalso`: sem
rede e sem esperar tempo real. A chamada ao backend roda em `asyncio.to_thread`, como em produção.
"""

import asyncio
import contextlib
import json
import re
import sqlite3
import threading
from collections.abc import Callable, Iterator, Sequence
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from apoio.relogio import RelogioFalso
from apoio.semear import AGORA, inserir_vaga
from jobot.agenda import ia as laco
from jobot.agenda.execucao import executar_busca
from jobot.banco.buscas import criar_busca
from jobot.banco.cadastros import gravar_config
from jobot.banco.conexao import abrir
from jobot.banco.ia import chamadas_do_dia
from jobot.banco.migrar import migrar
from jobot.banco.perfil import gravar_habilidades
from jobot.cli import servir
from jobot.nucleo.ia.anthropic import ClienteAnthropic
from jobot.nucleo.ia.compativel_openai import ClienteCompativel
from jobot.nucleo.ia.contrato import Falha, Pedido, Resposta
from jobot.nucleo.ia.falso import BackendFalso
from jobot.nucleo.ia.pedidos import pedido_encaixe, texto_encaixe
from jobot.nucleo.modelo import Busca
from jobot.sistema import llama
from jobot.sistema.cofre import Cofre
from jobot.sistema.llama import FalhaLlama
from jobot.sistema.pastas import PASTA_FERRAMENTAS

pytestmark = pytest.mark.anyio

HOJE = AGORA.astimezone().date()
LIMITES = {"max_por_rodada": 20, "max_tentativas": 2, "max_por_dia_fora": 200}
OK: dict[str, object] = {"pede": ["Python"]}


def _r(*pede: str) -> dict[str, object]:
    return {"pede": list(pede)}


PORTA = 47998


class Falso(BackendFalso):
    """O `BackendFalso` com `fechar` e um gancho chamado na thread do pedido."""

    def __init__(
        self,
        prontas: Sequence[dict[str, object] | Falha],
        ao_pedir: Callable[[Pedido], None] | None = None,
    ) -> None:
        super().__init__(list(prontas))
        self.ao_pedir = ao_pedir
        self.fechado = 0

    def pedir(self, pedido: Pedido) -> Resposta:
        if self.ao_pedir is not None:
            self.ao_pedir(pedido)
        return super().pedir(pedido)

    def fechar(self) -> None:
        self.fechado += 1


@pytest.fixture
def caminho(tmp_path: Path) -> Path:
    caminho = tmp_path / "jobot.db"
    with closing(abrir(caminho)) as con:
        migrar(con, caminho)
    return caminho


@pytest.fixture
def con(caminho: Path) -> Iterator[sqlite3.Connection]:
    c = abrir(caminho)
    yield c
    c.close()


def _ligar(con: sqlite3.Connection, backend: str = "openai", modelo: str = "m") -> None:
    tarefas = {"encaixe": {"ligada": True, "backend": backend, "modelo": modelo}}
    gravar_config(con, "ia_tarefas", tarefas)


def _vagas(con: sqlite3.Connection, n: int, descricao: str = "Python e Docker.") -> list[int]:
    """`n` vagas "Dev Python i" (a última é a mais nova), uma busca ativa por "python" (nível bom),
    o perfil com Python e a tarefa ligada."""
    ids = [
        inserir_vaga(
            con,
            titulo=f"Dev Python {i}",
            descricao_texto=descricao,
            primeira_vista_em=f"2026-11-{i + 1:02d}T10:00:00+00:00",
        )
        for i in range(n)
    ]
    con.commit()
    criar_busca(con, Busca(nome="b", cargos=("python",)), AGORA, regras_ligadas=True, hoje=HOJE)
    gravar_habilidades(con, ["Python"], AGORA)
    _ligar(con)
    return ids


def _titulo(pedido: Pedido) -> str:
    achado = re.search(r"Dev Python \d+", pedido.mensagens[1].texto)
    assert achado is not None
    return achado.group()


def _titulos(falso: BackendFalso) -> list[str]:
    return [_titulo(p) for p in falso.pedidos]


def _linha(con: sqlite3.Connection, vaga_id: int) -> dict[str, Any] | None:
    cur = con.execute("SELECT * FROM habilidades_vaga WHERE vaga_id = ?", (vaga_id,))
    nomes = [d[0] for d in cur.description]
    linha = cur.fetchone()
    return None if linha is None else dict(zip(nomes, linha, strict=True))


async def _rodada(
    con: sqlite3.Connection,
    falso: Falso,
    relogio: RelogioFalso | None = None,
    **kw: Any,
) -> list[tuple[str, str]]:
    obtidos: list[tuple[str, str]] = []

    def obter(backend: str, modelo: str) -> Falso:
        obtidos.append((backend, modelo))
        return falso

    kw.setdefault("limites", LIMITES)
    await laco.rodada(con, obter, relogio or RelogioFalso(AGORA), **kw)
    return obtidos


# --- quando nada roda ---


async def test_tarefa_desligada_ou_perfil_sem_habilidades_nao_pede_nada(
    con: sqlite3.Connection,
) -> None:
    _vagas(con, 1)
    gravar_config(
        con, "ia_tarefas", {"encaixe": {"ligada": False, "backend": "openai", "modelo": "m"}}
    )
    falso = Falso([OK])
    assert await _rodada(con, falso) == []
    _ligar(con)
    gravar_habilidades(con, [], AGORA)
    assert await _rodada(con, falso) == []
    assert falso.pedidos == []
    # controle: ligada e com habilidades, pede, com o backend e o modelo da tarefa
    gravar_habilidades(con, ["Python"], AGORA)
    assert await _rodada(con, falso) == [("openai", "m")]
    assert _titulos(falso) == ["Dev Python 0"]
    assert falso.fechado == 1


# --- a fila ---


async def test_fila_so_abertas_nao_ocultas_de_nivel_base_bom_ou_medio_das_mais_novas(
    con: sqlite3.Connection,
) -> None:
    ids = _vagas(con, 9)
    # numa busca desativada, o nível bom não vale
    outra = criar_busca(
        con, Busca(nome="c", cargos=("python",)), AGORA, regras_ligadas=True, hoje=HOJE
    )
    con.execute(
        "UPDATE encaixe SET nivel_base = 'fraco' WHERE vaga_id = ? AND busca_id <> ?",
        (ids[1], outra),
    )
    con.execute("UPDATE busca SET ativa = 0 WHERE id = ?", (outra,))
    con.execute("UPDATE vaga SET fechada_em = ? WHERE id = ?", (AGORA.isoformat(), ids[8]))
    con.execute("UPDATE vaga SET oculta_manual = 1 WHERE id = ?", (ids[7],))
    con.execute("UPDATE encaixe SET oculta_motivo = 'regra' WHERE vaga_id = ?", (ids[6],))
    # escondida pela regra, mas a pessoa pediu "mostrar mesmo assim": entra
    con.execute("UPDATE encaixe SET oculta_motivo = 'regra' WHERE vaga_id = ?", (ids[5],))
    con.execute("UPDATE vaga SET oculta_manual = -1 WHERE id = ?", (ids[5],))
    con.execute("UPDATE encaixe SET nivel_base = 'fraco' WHERE vaga_id = ?", (ids[4],))
    con.execute("UPDATE encaixe SET nivel_base = NULL WHERE vaga_id = ?", (ids[3],))
    con.execute("UPDATE encaixe SET nivel_base = 'medio' WHERE vaga_id = ?", (ids[2],))
    con.commit()
    falso = Falso([OK] * 9)
    await _rodada(con, falso)
    assert _titulos(falso) == ["Dev Python 5", "Dev Python 2", "Dev Python 0"]


async def test_ate_max_por_rodada_das_mais_novas(con: sqlite3.Connection) -> None:
    _vagas(con, 3)
    falso = Falso([OK] * 3)
    await _rodada(con, falso, limites=LIMITES | {"max_por_rodada": 2})
    assert _titulos(falso) == ["Dev Python 2", "Dev Python 1"]
    await _rodada(con, falso, limites=LIMITES | {"max_por_rodada": 2})
    assert _titulos(falso)[2:] == ["Dev Python 0"]


async def test_chave_igual_pula_e_texto_mudado_refaz(con: sqlite3.Connection) -> None:
    [vaga] = _vagas(con, 1)
    falso = Falso([OK] * 4)
    await _rodada(con, falso)
    await _rodada(con, falso)
    assert len(falso.pedidos) == 1  # mesma chave: não pede de novo
    con.execute("UPDATE vaga SET descricao_texto = 'Python, Go e Docker.' WHERE id = ?", (vaga,))
    con.commit()
    await _rodada(con, falso)
    assert len(falso.pedidos) == 2  # o texto mudou: pede de novo
    _ligar(con, modelo="outro")
    await _rodada(con, falso)
    assert len(falso.pedidos) == 3  # o modelo entra na chave


async def test_pede_gravado_passa_pela_anti_invencao_no_texto_enviado(
    con: sqlite3.Connection,
) -> None:
    # o meio cortado (desenho 5.2) não foi enviado: o item que só está ali sai, e mudar só o meio
    # não muda a chave (a chave e a anti-invenção usam o mesmo `TextoVaga.texto`; D190.2)
    meio = "Rust " * 400
    descricao = "Python. " + "a" * 4000 + meio + "b" * 2000 + " Docker."
    [vaga] = _vagas(con, 1, descricao=descricao)
    falso = Falso([_r("Python", "Rust", "Docker", "Kotlin"), OK])
    await _rodada(con, falso)
    linha = _linha(con, vaga)
    assert linha is not None
    assert json.loads(linha["pede"]) == ["Python", "Docker"]
    assert (linha["backend"], linha["modelo"], linha["versao"]) == ("openai", "m", 1)
    assert linha["feito_em"] == AGORA.isoformat()
    assert "Rust Rust" not in falso.pedidos[0].mensagens[1].texto
    con.execute(
        "UPDATE vaga SET descricao_texto = ? WHERE id = ?",
        (descricao.replace("Rust", "Java"), vaga),
    )
    con.commit()
    await _rodada(con, falso)
    assert len(falso.pedidos) == 1


# --- falhas ---


async def test_falha_do_backend_para_a_rodada_e_nao_marca_a_vaga(
    con: sqlite3.Connection,
) -> None:
    ids = _vagas(con, 2)
    falso = Falso([Falha("limite"), OK, OK])
    await _rodada(con, falso)
    assert _titulos(falso) == ["Dev Python 1"]  # parou na primeira
    assert all(_linha(con, v) is None for v in ids)
    assert falso.fechado == 1
    await _rodada(con, falso)  # a próxima rodada tenta de novo
    assert _titulos(falso)[1:] == ["Dev Python 1", "Dev Python 0"]


async def test_falha_ao_montar_o_backend_para_a_rodada(con: sqlite3.Connection) -> None:
    [vaga] = _vagas(con, 1)

    def obter(backend: str, modelo: str) -> Falso:
        raise Falha("sem_chave")

    await laco.rodada(con, obter, RelogioFalso(AGORA), limites=LIMITES)
    assert _linha(con, vaga) is None
    await _rodada(con, Falso([OK]))  # controle: com o backend montado, grava
    assert _linha(con, vaga) is not None


async def test_falha_da_vaga_grava_e_so_volta_com_chave_nova_ate_max_tentativas(
    con: sqlite3.Connection,
) -> None:
    [vaga] = _vagas(con, 1)
    falso = Falso([Falha("formato")] * 4)
    await _rodada(con, falso)
    linha = _linha(con, vaga)
    assert linha is not None
    assert (linha["falha"], linha["tentativas"], linha["falha_backend"]) == ("formato", 1, "openai")
    assert linha["pede"] is None
    await _rodada(con, falso)
    await _rodada(con, falso)  # a segunda falha com a mesma chave foi a última
    assert len(falso.pedidos) == 2
    assert (_linha(con, vaga) or {})["tentativas"] == 2
    con.execute("UPDATE vaga SET titulo = 'Dev Python 0 sênior' WHERE id = ?", (vaga,))
    con.commit()
    await _rodada(con, falso)  # chave nova: volta
    assert len(falso.pedidos) == 3
    assert (_linha(con, vaga) or {})["tentativas"] == 1


async def test_tres_que_sempre_falham_na_frente_nao_impedem_a_quarta(
    con: sqlite3.Connection,
) -> None:
    ids = _vagas(con, 4)
    falso = Falso([Falha("recusa")] * 6 + [OK] * 4)
    limites = LIMITES | {"max_por_rodada": 3}
    for _ in range(3):
        await _rodada(con, falso, limites=limites)
    assert _titulos(falso)[-1:] == ["Dev Python 0"]
    assert len(falso.pedidos) == 7
    assert json.loads((_linha(con, ids[0]) or {})["pede"]) == ["Python"]


# --- teto do dia ---


async def test_teto_do_dia_num_backend_de_fora_e_nenhum_no_local(con: sqlite3.Connection) -> None:
    _vagas(con, 3)
    falso = Falso([OK] * 6)
    limites = LIMITES | {"max_por_dia_fora": 2}
    await _rodada(con, falso, limites=limites)
    assert len(falso.pedidos) == 2
    await _rodada(con, falso, limites=limites)
    assert len(falso.pedidos) == 2  # o dia acabou para o openai
    _ligar(con, backend="local")
    await _rodada(con, falso, limites=limites)
    assert len(falso.pedidos) == 5  # local: as três, sem teto


async def test_teto_do_dia_conta_cada_chamada_com_as_falhas(con: sqlite3.Connection) -> None:
    # D198.10: o teto conta chamadas, não vagas; a falha do backend e a segunda tentativa contam
    _vagas(con, 2)
    falso = Falso([Falha("tempo_esgotado")] + [Falha("formato")] * 4)
    limites = LIMITES | {"max_por_dia_fora": 4}
    await _rodada(con, falso, limites=limites)  # falha do backend: a rodada para, a chamada conta
    await _rodada(con, falso, limites=limites)  # as duas falham pela vaga
    await _rodada(con, falso, limites=limites)  # a segunda tentativa da primeira; o teto corta
    assert _titulos(falso) == ["Dev Python 1", "Dev Python 1", "Dev Python 0", "Dev Python 1"]
    assert chamadas_do_dia(con, "openai", AGORA) == 4


# --- pedido da pessoa, encaixe, transação ---


async def test_espera_enquanto_ha_pedido_da_pessoa(con: sqlite3.Connection) -> None:
    _vagas(con, 2)
    passos: list[str] = []
    ocupado = iter([False, True, True, False])

    def esta_ocupado() -> bool:
        valor = next(ocupado)
        passos.append("ocupado" if valor else "livre")
        return valor

    falso = Falso([OK, OK], ao_pedir=lambda p: passos.append(_titulo(p)))
    relogio = RelogioFalso(AGORA)
    await _rodada(con, falso, relogio, ocupado=esta_ocupado)
    assert passos == ["livre", "Dev Python 1", "ocupado", "ocupado", "livre", "Dev Python 0"]
    assert relogio.dormidas == [laco.ESPERA_PESSOA_S] * 2


async def test_tarefa_trocada_no_meio_para_a_rodada(con: sqlite3.Connection, caminho: Path) -> None:
    _vagas(con, 2)

    def trocar(_: Pedido) -> None:  # a pessoa troca o modelo na aba IA durante o 1º pedido
        with closing(abrir(caminho)) as outra:
            _ligar(outra, modelo="outro")

    falso = Falso([OK, OK], ao_pedir=trocar)
    await _rodada(con, falso)
    assert _titulos(falso) == ["Dev Python 1"]
    # controle: sem mudar a tarefa, as duas
    falso = Falso([OK, OK])
    await _rodada(con, falso)
    assert len(falso.pedidos) == 2


async def test_encaixe_recalculado_so_para_a_vaga(con: sqlite3.Connection) -> None:
    feita, outra = _vagas(con, 2)
    con.execute(
        "UPDATE encaixe SET nivel_base = 'fraco', motivos = '[]' WHERE vaga_id = ?", (outra,)
    )
    con.commit()
    gravar_habilidades(con, ["Docker"], AGORA)
    falso = Falso([_r("Python", "Docker")])
    await _rodada(con, falso)
    motivos = con.execute("SELECT motivos FROM encaixe WHERE vaga_id = ?", (feita,)).fetchone()[0]
    chaves = [m["chave"] for m in json.loads(motivos)]
    assert "encaixe.habilidades_tem" in chaves
    assert con.execute(
        "SELECT nivel_base, motivos FROM encaixe WHERE vaga_id = ?", (outra,)
    ).fetchone() == ("fraco", "[]")


def _escrita_livre(caminho: Path) -> bool:
    """Outra conexão consegue pegar a escrita agora (sem esperar)."""
    with closing(sqlite3.connect(caminho, timeout=0)) as outra:
        try:
            outra.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError:
            return False
        outra.rollback()
        return True


async def test_chamada_ao_backend_fora_da_transacao(con: sqlite3.Connection, caminho: Path) -> None:
    _vagas(con, 2)
    vistas: list[bool] = []
    falso = Falso([OK, OK], ao_pedir=lambda _: vistas.append(_escrita_livre(caminho)))
    await _rodada(con, falso)
    assert vistas == [True, True]
    # controle: com a escrita aberta, o falso vê
    con.execute("BEGIN IMMEDIATE")
    try:
        assert await asyncio.to_thread(_escrita_livre, caminho) is False
    finally:
        con.rollback()


# --- o laço ---


class _Laco:
    """O laço numa tarefa, com o evento e a contagem de rodadas."""

    def __init__(self, caminho: Path, falso: Falso, **kw: Any) -> None:
        self.acordar = asyncio.Event()
        self.rodadas = 0
        self.fim = asyncio.Event()

        def depois() -> None:
            self.rodadas += 1
            self.fim.set()

        self.tarefa = asyncio.create_task(
            laco.laco_ia(
                caminho,
                lambda b, m: falso,
                RelogioFalso(AGORA),
                self.acordar,
                depois_da_rodada=depois,
                **kw,
            )
        )

    async def esperar_rodada(self) -> None:
        await asyncio.wait_for(self.fim.wait(), 5)
        self.fim.clear()

    async def parar(self) -> None:
        self.tarefa.cancel()
        with pytest.raises(asyncio.CancelledError):
            await self.tarefa


async def test_nao_roda_ao_subir_so_quando_acordado(con: sqlite3.Connection, caminho: Path) -> None:
    _vagas(con, 1)
    falso = Falso([OK])
    tarefa = _Laco(caminho, falso)
    for _ in range(5):
        await asyncio.sleep(0)
    assert (tarefa.rodadas, falso.pedidos) == (0, [])
    tarefa.acordar.set()  # controle: acordado, roda
    await tarefa.esperar_rodada()
    assert len(falso.pedidos) == 1
    await tarefa.parar()


async def test_duas_rodadas_pedidas_juntas_viram_uma(
    con: sqlite3.Connection, caminho: Path
) -> None:
    _vagas(con, 1)
    falso = Falso([Falha("formato")] * 3)
    tarefa = _Laco(caminho, falso)
    tarefa.acordar.set()
    tarefa.acordar.set()
    await tarefa.esperar_rodada()
    assert not tarefa.acordar.is_set()  # nada pendente: o laço volta a esperar
    await asyncio.sleep(0)
    assert tarefa.rodadas == 1
    await tarefa.parar()


async def test_pedidos_durante_a_rodada_viram_uma_rodada_depois(
    con: sqlite3.Connection, caminho: Path
) -> None:
    _vagas(con, 1)
    ciclo = asyncio.get_running_loop()
    tarefa: _Laco

    def pedir_de_novo(_: Pedido) -> None:
        if not tarefa.rodadas:  # só na primeira: dois pedidos durante a rodada
            ciclo.call_soon_threadsafe(tarefa.acordar.set)
            ciclo.call_soon_threadsafe(tarefa.acordar.set)

    falso = Falso([Falha("formato")] * 3, ao_pedir=pedir_de_novo)
    tarefa = _Laco(caminho, falso)
    tarefa.acordar.set()
    await tarefa.esperar_rodada()
    await tarefa.esperar_rodada()
    await asyncio.sleep(0)
    assert tarefa.rodadas == 2
    assert len(falso.pedidos) == 2  # a segunda rodada pediu de novo (tentativa 2)
    await tarefa.parar()


async def test_erro_na_rodada_nao_derruba_o_laco(con: sqlite3.Connection, caminho: Path) -> None:
    _vagas(con, 1)
    falso = Falso([])  # sem resposta pronta: o falso levanta IndexError
    tarefa = _Laco(caminho, falso)
    tarefa.acordar.set()
    fim = asyncio.ensure_future(tarefa.fim.wait())
    await asyncio.wait({tarefa.tarefa, fim}, timeout=5, return_when=asyncio.FIRST_COMPLETED)
    assert not tarefa.tarefa.done()  # o erro foi ao log; a tarefa segue
    assert fim.done()
    tarefa.fim.clear()
    falso.prontas.append(OK)
    tarefa.acordar.set()  # controle: o laço segue de pé
    await tarefa.esperar_rodada()
    assert len(falso.pedidos) == 2
    assert falso.fechado == 2
    await tarefa.parar()


async def test_cancelar_fecha_o_backend_com_o_pedido_em_curso(
    con: sqlite3.Connection, caminho: Path
) -> None:
    _vagas(con, 1)
    ciclo = asyncio.get_running_loop()
    comecou = asyncio.Event()
    solto = threading.Event()

    class Preso(Falso):
        def pedir(self, pedido: Pedido) -> Resposta:
            ciclo.call_soon_threadsafe(comecou.set)
            solto.wait(5)  # só a guarda: o `fechar` solta na hora
            raise Falha("sem_rede")

        def fechar(self) -> None:
            super().fechar()
            solto.set()

    falso = Preso([])
    tarefa = _Laco(caminho, falso)
    tarefa.acordar.set()
    await asyncio.wait_for(comecou.wait(), 5)
    assert falso.fechado == 0
    await tarefa.parar()
    assert falso.fechado == 1
    assert solto.is_set()


async def test_execucao_da_busca_acorda_o_laco_sem_esperar_por_ele(
    con: sqlite3.Connection, caminho: Path
) -> None:
    _vagas(con, 1)
    gravar_config(con, "enriquecimento_ligado", False)
    gravar_config(con, "conversao_moeda_ligada", False)
    ciclo = asyncio.get_running_loop()
    comecou = asyncio.Event()
    solto = threading.Event()

    def preso(_: Pedido) -> None:
        ciclo.call_soon_threadsafe(comecou.set)
        solto.wait(5)

    falso = Falso([OK], ao_pedir=preso)
    tarefa = _Laco(caminho, falso)
    tarefa.acordar.set()
    await asyncio.wait_for(comecou.wait(), 5)  # o laço está preso num pedido
    try:
        with closing(abrir(caminho)) as outra:
            execucao = await executar_busca(
                outra,
                object(),  # type: ignore[arg-type]
                RelogioFalso(AGORA),
                "agora",
                coletores={},
                ao_fim=tarefa.acordar,
            )
        assert execucao is not None  # terminou com o laço ainda no pedido
        assert tarefa.acordar.is_set()
    finally:
        solto.set()
    await tarefa.esperar_rodada()
    await tarefa.parar()


# --- `cli/servir.py`: a fábrica dos backends e o laço em `vida` ---


class _Chaveiro:
    """O cofre do sistema em memória (o `keyring` falso)."""

    def __init__(self) -> None:
        self.guardado: dict[str, str] = {}

    def get_password(self, service: str, username: str, /) -> str | None:
        return self.guardado.get(username)

    def set_password(self, service: str, username: str, password: str, /) -> None:
        self.guardado[username] = password

    def delete_password(self, service: str, username: str, /) -> None:
        self.guardado.pop(username, None)


def _fabrica(tmp_path: Path, **chaves: str) -> servir.FabricaIA:
    chaveiro = _Chaveiro()
    chaveiro.guardado.update(chaves)
    return servir.FabricaIA(tmp_path, tmp_path / "jobot.db", Cofre(tmp_path, chaveiro))


def test_fabrica_monta_cada_backend_com_a_chave_do_cofre(tmp_path: Path, caminho: Path) -> None:
    fabrica = _fabrica(caminho.parent, ia_openai="o", ia_gemini="g", ia_anthropic="a")
    with closing(abrir(caminho)) as con:
        gravar_config(con, "ia_compativel", {"endereco": "http://127.0.0.1:11434/v1"})
    montados = {
        nome: fabrica(nome, "m") for nome in ("openai", "gemini", "anthropic", "compativel")
    }
    try:
        for nome in ("openai", "gemini", "compativel"):
            assert isinstance(montados[nome], ClienteCompativel)
            assert cast(ClienteCompativel, montados[nome]).backend == nome
        assert isinstance(montados["anthropic"], ClienteAnthropic)
    finally:
        for montado in montados.values():
            montado.fechar()


def test_fabrica_sem_chave_ou_sem_modelo_local_falha_como_backend(tmp_path: Path) -> None:
    fabrica = _fabrica(tmp_path)
    for nome in ("openai", "gemini", "anthropic"):
        with pytest.raises(Falha) as erro:
            fabrica(nome, "m")
        assert erro.value.motivo == "sem_chave"
    with pytest.raises(Falha) as erro:
        fabrica("local", "m")
    assert erro.value.motivo == "modelo_ausente"
    with pytest.raises(ValueError, match="desconhecido"):
        fabrica("Manual", "m")
    # controle: com a chave, monta
    _fabrica(tmp_path, ia_openai="o")("openai", "m").fechar()


def test_fabrica_le_o_compativel_do_banco_que_recebe(tmp_path: Path) -> None:
    banco = tmp_path / "outro.db"
    with closing(abrir(banco)) as con:
        migrar(con, banco)
        gravar_config(con, "ia_compativel", {"endereco": "http://127.0.0.1:11434/v1"})
    fabrica = servir.FabricaIA(tmp_path, banco, Cofre(tmp_path, _Chaveiro()))
    cliente = cast(ClienteCompativel, fabrica("compativel", "m"))
    try:
        assert cliente._url == "http://127.0.0.1:11434/v1/chat/completions"
    finally:
        cliente.fechar()


def _anotar_local(dados: Path) -> None:
    pasta = dados / PASTA_FERRAMENTAS
    pasta.mkdir()
    anotacao = {"programa": "llama/b1/llama-server", "modelo": "4b", "arquivo": "q.gguf"}
    (pasta / "ia_local.json").write_text(json.dumps(anotacao), encoding="utf-8")


def test_local_sobe_uma_llama_so_e_traduz_a_falha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _anotar_local(tmp_path)
    criadas: list[tuple[Path, ...]] = []
    respostas: list[tuple[str, str] | FalhaLlama] = [
        FalhaLlama("programa_ausente"),
        ("http://127.0.0.1:9/v1", "k"),
    ]

    class LlamaFalsa:
        def __init__(self, dados: Path, programa: Path, modelo: Path) -> None:
            criadas.append((dados, programa, modelo))

        def subir(self) -> tuple[str, str]:
            pronta = respostas.pop(0)
            if isinstance(pronta, FalhaLlama):
                raise pronta
            return pronta

        def encerrar(self) -> None:
            pass

    clientes: list[tuple[str, str, str | None]] = []

    class ClienteFalso:
        def __init__(self, backend: str, endereco: str, chave: str | None) -> None:
            clientes.append((backend, endereco, chave))

        def pedir(self, pedido: Pedido) -> Resposta:
            return Resposta({"pede": []}, "local", pedido.modelo, 1)

        def fechar(self) -> None:
            pass

    monkeypatch.setattr(servir, "Llama", LlamaFalsa)
    monkeypatch.setattr(servir, "ClienteCompativel", ClienteFalso)
    fabrica = _fabrica(tmp_path)
    pedido = pedido_encaixe(texto_encaixe("Dev", "Python"), "local", "qwen")
    with pytest.raises(Exception) as erro:  # noqa: PT011 (o tipo é conferido abaixo)
        fabrica("local", "qwen").pedir(pedido)
    assert type(erro.value) is Falha
    assert erro.value.motivo == "programa_ausente"
    assert fabrica("local", "qwen").pedir(pedido).dados == {"pede": []}
    ferramentas = tmp_path / PASTA_FERRAMENTAS
    assert criadas == [
        (tmp_path, ferramentas / "llama/b1/llama-server", ferramentas / "modelos/q.gguf")
    ]
    assert clientes == [("local", "http://127.0.0.1:9/v1", "k")]
    assert fabrica.llama is not None


def test_fabrica_encerrada_nao_sobe_o_local(tmp_path: Path) -> None:
    _anotar_local(tmp_path)
    assert isinstance(_fabrica(tmp_path)("local", "qwen"), servir._Local)  # controle
    fabrica = _fabrica(tmp_path)
    fabrica.encerrar()
    with pytest.raises(Falha) as erro:
        fabrica("local", "qwen")
    assert erro.value.motivo == "servico_fora"
    assert fabrica.llama is None


@pytest.fixture
def dados(tmp_path: Path) -> Path:
    pasta = tmp_path / "dados"
    pasta.mkdir()
    return pasta


async def _parado(*_: object, **__: object) -> None:
    await asyncio.Event().wait()


@pytest.mark.usefixtures("laco_versao_parado")
def test_vida_cria_o_laco_e_a_busca_da_agenda_o_acorda(
    dados: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recebidos: list[tuple[Any, ...]] = []
    ocupados: list[bool] = []

    async def laco_ia_falso(*args: Any, ocupado: Callable[[], bool]) -> None:
        recebidos.append(args)
        ocupados.append(ocupado())
        await asyncio.Event().wait()

    acordados: list[Any] = []

    async def busca_falsa(*_: Any, ao_fim: asyncio.Event | None = None, **__: Any) -> int:
        acordados.append(ao_fim)
        return 1

    async def laco_que_busca(tarefas: Any, *_: Any, **__: Any) -> None:
        await tarefas["busca"]()
        await asyncio.Event().wait()

    monkeypatch.setattr(servir, "laco_ia", laco_ia_falso)
    monkeypatch.setattr(servir, "executar_busca", busca_falsa)
    monkeypatch.setattr(servir, "laco", laco_que_busca)
    app, _ = servir.montar(dados, PORTA, relogio=RelogioFalso(AGORA))
    with TestClient(app, base_url=f"http://127.0.0.1:{PORTA}"):
        assert _esperar(lambda: bool(recebidos) and bool(acordados))
        caminho, obter, _, acordar = recebidos[0]
        assert caminho == dados / "jobot.db"
        assert obter is app.state.ia
        assert isinstance(obter, servir.FabricaIA)
        assert acordar is app.state.ia_acordar
        assert acordados == [acordar]  # a busca da agenda marca o evento no fim
        assert ocupados == [False]


@pytest.mark.usefixtures("laco_versao_parado")
def test_fim_de_vida_encerra_a_llama_antes_da_sobra(
    dados: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ordem: list[str] = []
    monkeypatch.setattr(llama, "encerrar_sobra", lambda _: ordem.append("sobra"))
    monkeypatch.setattr(servir, "laco", _parado)

    def encerrar_quebrado() -> None:
        ordem.append("llama")
        raise OSError("não saiu")

    for encerrar in (lambda: ordem.append("llama"), encerrar_quebrado):
        ordem.clear()
        app, _ = servir.montar(dados, PORTA, relogio=RelogioFalso(AGORA))
        with (
            contextlib.suppress(OSError),
            TestClient(app, base_url=f"http://127.0.0.1:{PORTA}"),
        ):
            app.state.ia.llama = SimpleNamespace(encerrar=encerrar)
        # o erro de encerrar a instância não impede a sobra anotada de sair
        assert ordem == ["sobra", "llama", "sobra"]


def _esperar(condicao: Callable[[], bool]) -> bool:
    """O lifespan roda noutra thread no `TestClient`: espera a condição por até 5 s."""
    for _ in range(500):
        if condicao():
            return True
        threading.Event().wait(0.01)
    return False
