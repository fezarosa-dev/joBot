"""`scripts/conferir_empresas.py`: confere ao vivo cada empresa; aqui por `MockTransport`."""

import importlib.util
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores.registro import descobrir
from jobot.nucleo.http import ClienteEducado, Validadores
from jobot.nucleo.modelo import Empresa

pytestmark = pytest.mark.anyio

RAIZ = Path(__file__).resolve().parents[2]


def _carregar() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "conferir_empresas_script", RAIZ / "scripts/conferir_empresas.py"
    )
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo  # o dataclass procura o módulo pelo nome
    spec.loader.exec_module(modulo)
    return modulo


conferir_empresas = _carregar()


class SemValidadores:
    def ler(self, url: str) -> Validadores | None:
        return None


def _vaga(n: int) -> dict[str, Any]:
    return {
        "id": n,
        "title": f"Dev {n}",
        "company_name": "Acme",
        "absolute_url": f"https://boards.greenhouse.io/acme/jobs/{n}",
        "content": "",
    }


def _servidor(pedido: httpx.Request) -> httpx.Response:
    quadro = pedido.url.path.split("/")[3]  # /v1/boards/<quadro>/jobs
    if quadro == "viva":
        return httpx.Response(200, json={"jobs": [_vaga(1), _vaga(2), _vaga(3)]})
    if quadro == "morta":
        return httpx.Response(404, json={"error": "Job not found"})
    raise httpx.ConnectError("sem rede", request=pedido)


def _gh(nome: str, quadro: str) -> Empresa:
    return Empresa(nome=nome, fonte="greenhouse", identificador=quadro)


async def _conferir(empresas: Sequence[Empresa], fontes: Sequence[str] | None = None) -> list[Any]:
    cliente = ClienteEducado(httpx.MockTransport(_servidor), RelogioFalso(), SemValidadores(), "9")
    try:
        linhas: list[Any] = await conferir_empresas.conferir(cliente, empresas, descobrir(), fontes)
    finally:
        await cliente.fechar()
    return linhas


async def _uma(empresa: Empresa) -> Any:
    linhas = await _conferir([empresa])
    assert len(linhas) == 1
    return linhas[0]


async def test_empresa_que_responde_traz_as_vagas() -> None:
    linha = await _uma(_gh("Viva", "viva"))
    assert (linha.empresa, linha.fonte, linha.estado, linha.vagas) == (
        "Viva",
        "greenhouse",
        "ok",
        3,
    )
    assert linha.responde


async def test_quadro_que_da_404_nao_responde() -> None:
    linha = await _uma(_gh("Morta", "morta"))
    assert linha.estado == "falhou"
    assert linha.motivo == "saude.empresa_nao_encontrada"
    assert linha.vagas == 0
    assert not linha.responde


async def test_erro_de_rede_nao_responde() -> None:
    linha = await _uma(_gh("Caida", "caida"))
    assert linha.estado == "falhou"
    assert linha.motivo == "saude.erro_de_rede"
    assert not linha.responde


async def test_empresa_sem_os_parametros_do_ats_nao_tem_escopo() -> None:
    sem_conta = Empresa(nome="Sem conta", fonte="quickin", identificador="semconta")
    linha = await _uma(sem_conta)
    assert (linha.estado, linha.vagas) == ("sem_escopo", 0)
    assert not linha.responde


async def test_uma_empresa_que_cai_nao_para_as_outras() -> None:
    linhas = await _conferir([_gh("Caida", "caida"), _gh("Viva", "viva"), _gh("Morta", "morta")])
    assert [(x.empresa, x.responde) for x in linhas] == [
        ("Caida", False),
        ("Viva", True),
        ("Morta", False),
    ]


async def test_filtro_de_fonte_pula_as_outras() -> None:
    empresas = [_gh("Viva", "viva")]
    assert len(await _conferir(empresas, fontes=["greenhouse"])) == 1  # controle
    assert await _conferir(empresas, fontes=["lever"]) == []


async def test_relatorio_traz_empresa_fonte_estado_e_vagas() -> None:
    linhas = await _conferir([_gh("Viva", "viva"), _gh("Morta", "morta")])
    texto = conferir_empresas.relatorio(linhas)
    por_linha = {x.split()[0]: x for x in texto.splitlines() if x.startswith(("Viva", "Morta"))}
    assert "greenhouse" in por_linha["Viva"] and "ok" in por_linha["Viva"]
    assert por_linha["Viva"].split()[-1] == "3"
    assert "falhou" in por_linha["Morta"] and "saude.empresa_nao_encontrada" in por_linha["Morta"]
    assert "1 de 2 respondem" in texto


def test_o_script_nao_escreve_no_empresas_json() -> None:
    codigo = (RAIZ / "scripts/conferir_empresas.py").read_text(encoding="utf-8")
    assert "write_text" not in codigo and "open(" not in codigo
    assert json.loads((RAIZ / "src/jobot/nucleo/dados/empresas.json").read_text("utf-8"))
