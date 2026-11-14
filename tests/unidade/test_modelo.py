import asyncio
import dataclasses
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.modelo import (
    Area,
    Aviso,
    Contrato,
    Modalidade,
    Nivel,
    SalarioBruto,
    VagaColetada,
    VagaTratada,
)
from jobot.nucleo.relogio import Relogio, RelogioReal
from jobot.nucleo.texto import normalizar


def _vaga(**campos: Any) -> VagaColetada:
    base: dict[str, Any] = {
        "fonte": "remotive",
        "escopo": "",
        "url": "https://exemplo.com/vaga/1",
        "titulo": "Dev Python",
        "empresa": "Acme",
        "descricao_formato": "html",
    }
    return VagaColetada(**(base | campos))


def test_url_so_http_https() -> None:
    with pytest.raises(ValueError):
        _vaga(url="javascript:x")
    with pytest.raises(ValueError):
        _vaga(url="file:///etc/passwd")
    assert _vaga(url="http://exemplo.com/a").url == "http://exemplo.com/a"


def test_url_candidatura_so_http_https() -> None:
    for ruim in ("javascript:alert(1)", "data:text/html,x", "https://"):
        with pytest.raises(ValueError):
            _vaga(url_candidatura=ruim)
    link = "https://exemplo.com/aplicar?x=1&y=%20"
    assert _vaga(url_candidatura=link).url_candidatura == link  # sem nenhuma mudança
    assert _vaga(url_candidatura=None).url_candidatura is None


def _tratada(**campos: Any) -> VagaTratada:
    base: dict[str, Any] = {
        "fonte": "remotive",
        "escopo": "",
        "url": "https://exemplo.com/vaga/1",
        "titulo": "Dev Python",
        "empresa": "Acme",
        "descricao_formato": "html",
        "descricao": "",
        "id_externo": None,
        "url_candidatura": None,
        "modalidade_declarada": None,
        "contrato_declarado": None,
        "salario_texto": None,
        "salario_estruturado": None,
        "publicada_em": None,
        "prazo": None,
        "inicio": None,
        "etiquetas": (),
        "url_canonica": "https://exemplo.com/vaga/1",
        "url_hash": "abc",
        "descricao_texto": "",
        "idioma": "pt",
        "locais": (),
        "area": Area.OUTRA,
        "nivel": Nivel.NAO_INFORMADO,
        "modalidade": Modalidade.NAO_INFORMADO,
        "contrato": Contrato.NAO_INFORMADO,
        "avisos": (),
        "salario": None,
        "requisitos_estagio": None,
        "versao_regras": "1",
    }
    return VagaTratada(**(base | campos))


def test_vaga_tratada_confere_url_e_fuso() -> None:
    assert _tratada().url.startswith("https://")
    with pytest.raises(ValueError):
        _tratada(url="javascript:x")
    with pytest.raises(ValueError):
        _tratada(publicada_em=datetime(2026, 11, 13, 12, 0))
    with pytest.raises(ValueError):
        _tratada(url_candidatura="javascript:x")


def test_publicada_em_exige_fuso() -> None:
    with pytest.raises(ValueError):
        _vaga(publicada_em=datetime(2026, 11, 13, 12, 0))
    ok = _vaga(publicada_em=datetime(2026, 11, 13, 12, 0, tzinfo=UTC))
    assert ok.publicada_em is not None


def test_enums_tem_os_valores_do_desenho() -> None:
    assert [a.value for a in Area] == [
        "tecnologia", "dados", "design", "produto", "marketing", "vendas", "financas",
        "rh", "juridico", "operacoes", "engenharia", "saude", "educacao",
        "administrativo", "atendimento", "pesquisa", "outra",
    ]  # fmt: skip
    assert [n.value for n in Nivel] == [
        "estagio", "trainee", "junior", "pleno", "senior", "especialista", "lideranca",
        "nao_informado",
    ]  # fmt: skip
    assert [m.value for m in Modalidade] == ["presencial", "hibrido", "remoto", "nao_informado"]
    assert [c.value for c in Contrato] == [
        "clt", "pj", "estagio", "trainee", "temporario", "aprendiz", "bolsa_pesquisa",
        "programa", "concurso", "freelance", "nao_informado",
    ]  # fmt: skip
    assert [a.value for a in Aviso] == ["exige_visto", "exige_doutorado", "restrito_a_pais"]


def test_normalizar() -> None:
    assert normalizar("  São  PAULO ") == "sao paulo"


def test_vaga_coletada_vai_e_volta_em_json() -> None:
    vaga = _vaga(
        url_candidatura="https://exemplo.com/aplicar?x=1",
        descricao="<p>Oi</p>",
        locais=("São Paulo - SP", "Remote"),
        modalidade_declarada="remote",
        salario_texto="$50/hr",
        salario_estruturado=SalarioBruto(
            moeda="USD", minimo_unidades=50.0, maximo_unidades=70.5, periodo="hora"
        ),
        publicada_em=datetime(2026, 11, 13, 9, 30, tzinfo=timezone(timedelta(hours=-3))),
        prazo=date(2026, 12, 1),
        inicio=date(2027, 1, 10),
        etiquetas=("python", "backend"),
    )
    volta = VagaColetada.de_json(vaga.para_json())
    assert volta == vaga
    assert dataclasses.is_dataclass(volta)
    assert VagaColetada.de_json(_vaga().para_json()) == _vaga()


def test_relogio_falso_avanca_sem_esperar() -> None:
    relogio: Relogio = RelogioFalso()
    inicio = relogio.agora()
    asyncio.run(relogio.dormir(3600))
    assert relogio.agora() - inicio == timedelta(hours=1)
    assert isinstance(relogio, RelogioFalso)
    assert relogio.dormidas == [3600]


def test_relogio_real_tem_fuso_e_cumpre_o_protocolo() -> None:
    relogio: Relogio = RelogioReal()
    assert relogio.agora().tzinfo is not None
    asyncio.run(relogio.dormir(0))
