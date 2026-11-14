"""`empresas.json` (desenho 8.6): formato, `parametros` do ATS e as empresas do apêndice."""

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from jobot.banco.cadastros import empresas_iniciais
from jobot.nucleo.coletores.base import ContextoColeta
from jobot.nucleo.coletores.registro import descobrir, limites
from jobot.nucleo.modelo import Empresa

ARQUIVO = (
    Path(__file__).resolve().parents[2] / "src" / "jobot" / "nucleo" / "dados" / "empresas.json"
)
BRUTO: dict[str, Any] = json.loads(ARQUIVO.read_text(encoding="utf-8"))
LISTA: list[dict[str, Any]] = BRUTO["empresas"]
CAMPOS = {"nome", "area", "fonte", "identificador", "pais", "parametros", "conferida_em"}
# Chaves de `parametros` por ATS (desenho 8.6). A leva A só tem `careerPageName` (Gupy, opcional).
OBRIGATORIAS = {
    "quickin": {"account_id"},
    "workday": {"wd"},
    "eightfold": {"dominio", "geracao"},
    "oracle_hcm": {"site_number", "site"},
}
OPCIONAIS = {"gupy": {"careerPageName"}}
# Empresas que o apêndice (3.1, 3.3 e 3.4 da conferência) viu responder, por fonte.
DO_APENDICE = {
    "inhire": {"riachuelo", "carreiras"},
    "quickin": {"connectforpeople", "quickin"},
    "recrutei": {"ucm-business-solutions", "daguilar-consultoria-rh"},
    "solides": {"diefra", "bamex"},
    "workday": {"mastercard/CorporateCareers", "santander/SantanderCareers"},
    "eightfold": {
        "mercadolibre.eightfold.ai",
        "jobs.nvidia.com",
        "apply.careers.microsoft.com",
        "bayer.eightfold.ai",
    },
    "oracle_hcm": {"eeho.fa.us2.oraclecloud.com", "jpmc.fa.oraclecloud.com"},
}


def _id(e: dict[str, Any]) -> str:
    return f"{e['fonte']}/{e['identificador']}"


def test_formato_do_arquivo() -> None:
    assert BRUTO["versao"] == 1
    assert LISTA
    for e in LISTA:
        assert set(e) == CAMPOS, _id(e)
        assert e["nome"].strip() and e["area"].strip() and e["identificador"].strip(), _id(e)
        assert e["pais"] is None or re.fullmatch(r"[A-Z]{2}", e["pais"]), _id(e)
        assert isinstance(e["parametros"], dict), _id(e)


def test_conferida_em_e_data_iso() -> None:
    for e in LISTA:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", e["conferida_em"]), _id(e)
        date.fromisoformat(e["conferida_em"])  # ValueError se o dia não existe


def test_fonte_existe_no_registro() -> None:
    coletores = descobrir()
    for e in LISTA:
        assert e["fonte"] in coletores, _id(e)
        limites(e["fonte"])  # a fonte também tem limites em fontes.json


def test_sem_repeticao_de_fonte_e_identificador() -> None:
    # a carga procura por lower(identificador): caixa diferente também é repetição
    chaves = [(e["fonte"], e["identificador"].lower()) for e in LISTA]
    assert len(chaves) == len(set(chaves))


def test_cada_empresa_tem_so_os_parametros_do_seu_ats() -> None:
    for e in LISTA:
        obrigatorias = OBRIGATORIAS.get(e["fonte"], set())
        chaves = set(e["parametros"])
        assert obrigatorias <= chaves <= obrigatorias | OPCIONAIS.get(e["fonte"], set()), _id(e)
        assert all(isinstance(v, str) and v.strip() for v in e["parametros"].values()), _id(e)
        if e["fonte"] == "eightfold":
            assert e["parametros"]["geracao"] in {"pcsx", "v2"}, _id(e)


@pytest.mark.parametrize(
    "empresa", empresas_iniciais(), ids=lambda e: f"{e.fonte}/{e.identificador}"
)
def test_o_coletor_da_fonte_le_os_parametros(empresa: Empresa) -> None:
    # `escopos` devolve vazio se faltar ou estiver errado o que o coletor lê (a empresa ficaria
    # de fora da coleta em silêncio)
    coletor = descobrir()[empresa.fonte]
    ctx = ContextoColeta((empresa,), ("developer",), ("BR",))
    assert list(coletor.escopos(ctx)), f"{empresa.fonte}/{empresa.identificador}"


def test_as_empresas_vistas_no_apendice_entram() -> None:
    entradas = {(e["fonte"], e["identificador"]) for e in LISTA}
    esperadas = {(f, i) for f, ids in DO_APENDICE.items() for i in ids}
    assert esperadas - entradas == set()
