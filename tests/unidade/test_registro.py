import json
import sys
from collections.abc import AsyncIterator, Callable, Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from jobot.nucleo.coletores import registro
from jobot.nucleo.coletores.base import (
    SEM_MUDANCA,
    Item,
    LimiteEscopo,
    ResultadoEscopo,
    UrlListada,
    juntar_paginas,
)
from jobot.nucleo.http import (
    Bloqueio,
    ErroDeRede,
    HttpEducado,
    LimiteAtingido,
    OrcamentoGasto,
    Parou429,
)
from jobot.nucleo.modelo import VagaColetada

pytestmark = pytest.mark.anyio

LEVA_A = (
    "github_issues remotive remoteok jobicy himalayas wwr hn_algolia greenhouse lever ashby "
    "smartrecruiters gupy"
)
LEVA_B = (
    "inhire quickin recrutei solides abler ciee iel super_estagios cia_de_talentos eureca usp "
    "workday eightfold oracle_hcm google amazon"
)
CREDITO = {"remotive", "remoteok", "jobicy", "himalayas", "wwr"}
# (intervalo_min, max_pedidos, espera_s) das Global Constraints e do apêndice;
# quem não está aqui é (None, None, 1.0)
LIMITES: dict[str, tuple[int | None, int | None, float]] = {
    "remotive": (360, None, 1.0),
    "remoteok": (360, None, 1.0),
    "amazon": (360, None, 2.0),
    "jobicy": (60, None, 1.0),
    "wwr": (60, None, 1.0),
    "google": (1440, None, 1.0),
    "himalayas": (1440, 30, 2.0),
    "gupy": (None, 30, 2.0),
    "abler": (None, None, 2.0),
    "eureca": (None, None, 2.0),
}
MICROSOFT = "apply.careers.microsoft.com"


def _vaga(**campos: Any) -> VagaColetada:
    base: dict[str, Any] = {
        "fonte": "f",
        "escopo": "",
        "url": "https://exemplo.com/v/1",
        "titulo": "Dev",
        "empresa": "Acme",
        "descricao_formato": "texto",
    }
    return VagaColetada(**(base | campos))


class HttpFalso:
    pedidos = 3


def _http() -> HttpEducado:
    return cast(HttpEducado, HttpFalso())


async def _paginas(*itens: Sequence[Item] | Exception) -> AsyncIterator[Sequence[Item]]:
    for item in itens:
        if isinstance(item, Exception):
            raise item
        yield item


def test_fontes_json_tem_28_fontes_e_os_limites() -> None:
    bruto = json.loads((Path(registro.__file__).parents[1] / "dados" / "fontes.json").read_text())
    assert list(bruto) == (LEVA_A + " " + LEVA_B).split()
    assert len(bruto) == 28
    for chave in bruto:
        lim = registro.limites(chave)
        assert lim.leva == ("A" if chave in LEVA_A.split() else "B"), chave
        assert (lim.intervalo_min, lim.max_pedidos, lim.espera_s) == LIMITES.get(
            chave, (None, None, 1.0)
        ), chave
        assert lim.credito_obrigatorio == (chave in CREDITO), chave
        assert lim.por_escopo == (
            {MICROSOFT: LimiteEscopo(1440, 5.0, True)} if chave == "eightfold" else {}
        )
    assert sum(registro.limites(c).credito_obrigatorio for c in bruto) == 5


def test_limites_de_chave_desconhecida() -> None:
    with pytest.raises(KeyError):
        registro.limites("nao_existe")


@pytest.fixture
def pacote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[str, str], None]]:
    """Cria o pacote `pac_registro` com os módulos dados e o põe no sys.path."""
    raiz = tmp_path / "pac_registro"
    raiz.mkdir()
    (raiz / "__init__.py").write_text("")
    monkeypatch.syspath_prepend(str(tmp_path))

    def criar(modulo: str, codigo: str) -> None:
        (raiz / f"{modulo}.py").write_text(codigo)

    yield criar
    for nome in [n for n in sys.modules if n.split(".")[0] == "pac_registro"]:
        del sys.modules[nome]


def test_descobrir_le_o_atributo_coletor(pacote: Callable[[str, str], None]) -> None:
    pacote("a", "from types import SimpleNamespace\nCOLETOR = SimpleNamespace(chave='a')\n")
    pacote("b", "from types import SimpleNamespace\nCOLETOR = SimpleNamespace(chave='b')\n")
    pacote("sem", "X = 1\n")
    achados = registro.descobrir("pac_registro")
    assert sorted(achados) == ["a", "b"]


def test_descobrir_acha_coletor_em_subpacote(
    pacote: Callable[[str, str], None], tmp_path: Path
) -> None:
    sub = tmp_path / "pac_registro" / "portais"
    sub.mkdir()
    (sub / "__init__.py").write_text("")
    (sub / "c.py").write_text(
        "from types import SimpleNamespace\nCOLETOR = SimpleNamespace(chave='c')\n"
    )
    assert list(registro.descobrir("pac_registro")) == ["c"]


def test_descobrir_recusa_chave_repetida(pacote: Callable[[str, str], None]) -> None:
    for modulo in ("a", "b"):
        pacote(modulo, "from types import SimpleNamespace\nCOLETOR = SimpleNamespace(chave='x')\n")
    with pytest.raises(ValueError, match="'x'"):
        registro.descobrir("pac_registro")


def test_todo_coletor_achado_esta_no_json() -> None:
    for chave, coletor in registro.descobrir().items():
        lim = registro.limites(chave)  # KeyError se a chave não estiver no JSON
        assert coletor.chave == chave
        assert (coletor.leva, coletor.credito_obrigatorio) == (lim.leva, lim.credito_obrigatorio)
        assert (coletor.intervalo_min, coletor.max_pedidos) == (lim.intervalo_min, lim.max_pedidos)
        assert (coletor.espera_s, dict(coletor.por_escopo)) == (lim.espera_s, dict(lim.por_escopo))


def test_chave_repetida_falha() -> None:
    with pytest.raises(ValueError, match="remotive"):
        registro.carregar_fontes('{"remotive": {"leva": "A"}, "remotive": {"leva": "A"}}')
    aninhada = '{"x": {"leva": "B", "por_escopo": {"h": {}, "h": {}}}}'
    with pytest.raises(ValueError, match="'h'"):
        registro.carregar_fontes(aninhada)


async def test_juntar_paginas_estados() -> None:
    http = _http()
    vaga = _vaga()
    uma, duas = (vaga,), (vaga, _vaga(url="https://exemplo.com/v/2"))

    ok = await juntar_paginas(http, _paginas(uma, duas))
    assert ok == ResultadoEscopo(uma + duas, "ok", None, 3)

    sem_mudanca = await juntar_paginas(http, _paginas(SEM_MUDANCA, SEM_MUDANCA))
    assert sem_mudanca == ResultadoEscopo((), "sem_mudanca", None, 3)

    # 304 misturado com 200: a lista não veio inteira, então nunca "ok" (ok fecha vagas)
    for ordem in ((SEM_MUDANCA, uma), (uma, SEM_MUDANCA)):
        misto = await juntar_paginas(http, _paginas(*ordem))
        assert (misto.estado, misto.vagas) == ("parcial", uma)

    vazio = await juntar_paginas(http, _paginas())
    assert (vazio.estado, vazio.vagas) == ("ok", ())

    # parcial: guarda o que veio antes; no_limite: idem; falhou: nada aproveitável
    parcial = await juntar_paginas(http, _paginas(uma, LimiteAtingido("x")))
    assert parcial == ResultadoEscopo(uma, "parcial", "saude.limite_atingido", 3)
    gasto = await juntar_paginas(http, _paginas(uma, OrcamentoGasto("x")))
    assert gasto == ResultadoEscopo(uma, "no_limite", "saude.orcamento", 3)
    parou = await juntar_paginas(http, _paginas(uma, Parou429("x")))
    assert parou == ResultadoEscopo(uma, "no_limite", "saude.parou_429", 3)
    bloqueio = await juntar_paginas(http, _paginas(uma, Bloqueio("x")))
    assert bloqueio == ResultadoEscopo((), "falhou", "saude.bloqueio", 3)
    rede = await juntar_paginas(http, _paginas(ErroDeRede("x", 500)))
    assert rede == ResultadoEscopo((), "falhou", "saude.erro_de_rede", 3)
    # erro de rede depois de >= 1 página: veio uma parte, fica parcial e guarda as vagas
    rede_depois = await juntar_paginas(http, _paginas(uma, ErroDeRede("x", 500)))
    assert rede_depois == ResultadoEscopo(uma, "parcial", "saude.erro_de_rede", 3)


async def test_juntar_paginas_deixa_subir_o_que_nao_conhece() -> None:
    with pytest.raises(RuntimeError):
        await juntar_paginas(_http(), _paginas(RuntimeError("x")))


async def test_juntar_paginas_sem_contador_de_pedidos() -> None:
    resultado = await juntar_paginas(cast(HttpEducado, object()), _paginas())
    assert resultado.pedidos == 0


def test_url_listada_so_http_https_e_data_com_fuso() -> None:
    with pytest.raises(ValueError):
        UrlListada(url="javascript:x")
    with pytest.raises(ValueError):
        UrlListada(url="ftp://exemplo.com/v")
    with pytest.raises(ValueError):
        UrlListada(url="https://exemplo.com/v", atualizada_em=datetime(2026, 11, 13))
    assert UrlListada(url="https://exemplo.com/v", atualizada_em=None).atualizada_em is None
    com_fuso = datetime(2026, 11, 13, tzinfo=UTC)
    assert UrlListada(url="http://exemplo.com/v", atualizada_em=com_fuso).atualizada_em == com_fuso


async def test_juntar_paginas_aceita_url_listada() -> None:
    p1 = (UrlListada(url="https://exemplo.com/a"), UrlListada("https://exemplo.com/b"))
    p2 = (UrlListada(url="https://exemplo.com/c", atualizada_em=datetime(2026, 11, 1, tzinfo=UTC)),)
    resultado = await juntar_paginas(_http(), _paginas(p1, p2))
    assert resultado.estado == "ok"
    assert resultado.vagas == p1 + p2
