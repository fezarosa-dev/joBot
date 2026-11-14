"""Link "reportar problema": conjunto fechado de motivos, URL montada com `urlencode` (T50)."""

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.http import ClienteEducado, Validadores
from jobot.nucleo.quebra import (
    FORA_DO_LINK,
    MOTIVOS_DE_QUEBRA,
    URL_REPOSITORIO,
    link_reportar,
)

RAIZ = Path(__file__).resolve().parents[2]
COMUM_PT = RAIZ / "src" / "jobot" / "painel" / "i18n" / "pt" / "comum.json"
MODELO = RAIZ / ".github" / "ISSUE_TEMPLATE" / "fonte-quebrou.yml"

CONTADORES_E_LIMITES = (
    "saude.excecao",
    "saude.parcial_n",
    "saude.sem_detalhe_n",
    "saude.cota",
    "saude.intervalo",
    "saude.parou_429",
    "saude.limite_atingido",
    "saude.orcamento",
)


def _consulta(url: str) -> dict[str, list[str]]:
    return parse_qs(urlsplit(url).query, keep_blank_values=True)


def test_link_so_leva_a_chave_e_um_motivo_do_conjunto_fechado() -> None:
    assert len(MOTIVOS_DE_QUEBRA) == 8
    for motivo in sorted(MOTIVOS_DE_QUEBRA):
        url = link_reportar("remotive", motivo)
        assert url is not None, motivo
        partes = urlsplit(url)
        assert f"{partes.scheme}://{partes.netloc}{partes.path}" == f"{URL_REPOSITORIO}/issues/new"
        assert _consulta(url) == {
            "template": ["fonte-quebrou.yml"],
            "fonte": ["remotive"],
            "motivo": [motivo],
        }


def test_link_com_identificador_malicioso_leva_so_os_tres_parametros() -> None:
    identificador = 'acme&motivo=x#y%0A "aspas" \n=&template=outro'
    fonte = f"greenhouse/{identificador}"
    url = link_reportar(fonte, "saude.formato_mudou")
    assert url is not None
    assert urlsplit(url).fragment == ""
    consulta = _consulta(url)
    assert set(consulta) == {"template", "fonte", "motivo"}
    assert consulta["fonte"] == [fonte]
    assert consulta["template"] == ["fonte-quebrou.yml"]
    assert consulta["motivo"] == ["saude.formato_mudou"]
    assert "\n" not in url and " " not in url


def test_estados_de_limite_e_contadores_nao_geram_link() -> None:
    assert set(CONTADORES_E_LIMITES) == FORA_DO_LINK
    for chave in sorted(FORA_DO_LINK):
        assert link_reportar("remotive", chave) is None, chave
    assert link_reportar("remotive", "saude.inventada") is None
    assert link_reportar("remotive", "") is None


def test_motivo_com_parametro_e_comparado_pela_chave() -> None:
    url = link_reportar("remotive", "saude.formato_mudou:x")
    assert url is not None
    assert _consulta(url)["motivo"] == ["saude.formato_mudou"]
    assert link_reportar("remotive", "saude.sem_detalhe_n:3") is None
    assert link_reportar("remotive", "saude.excecao:KeyError") is None
    # só a parte antes do primeiro ":" vale: um motivo fechado vindo depois dele não conta
    assert link_reportar("remotive", "saude.excecao:saude.formato_mudou") is None


def test_toda_chave_saude_do_catalogo_esta_classificada() -> None:
    catalogo = json.loads(COMUM_PT.read_text(encoding="utf-8"))
    chaves = {c for c in catalogo if c.startswith("saude.")}
    assert chaves, "catálogo sem chaves saude.*"
    assert not MOTIVOS_DE_QUEBRA & FORA_DO_LINK
    assert chaves == MOTIVOS_DE_QUEBRA | FORA_DO_LINK


def test_modelo_fonte_quebrou_tem_os_campos_e_os_dois_idiomas() -> None:
    texto = MODELO.read_text(encoding="utf-8")
    assert "id: fonte\n" in texto
    assert "id: motivo\n" in texto
    assert "labels: [fonte-quebrada]" in texto
    assert "Fonte quebrou" in texto  # português
    assert "Source broke" in texto  # inglês


class _SemValidadores:
    def ler(self, url: str) -> Validadores | None:
        return None


@pytest.mark.anyio
async def test_url_do_repositorio_bate_com_o_user_agent() -> None:
    vistos: list[str] = []

    def servidor(pedido: httpx.Request) -> httpx.Response:
        vistos.append(pedido.headers["User-Agent"])
        return httpx.Response(200, text="ok")

    cliente = ClienteEducado(
        httpx.MockTransport(servidor), RelogioFalso(), _SemValidadores(), "9.9.9"
    )
    try:
        await cliente.escopo().pedir("GET", "https://a.example/")
    finally:
        await cliente.fechar()
    assert len(vistos) == 1
    assert URL_REPOSITORIO in vistos[0]
