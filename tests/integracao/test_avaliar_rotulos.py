import json
import re
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from jobot.cli import main
from jobot.cli.avaliar_rotulos import relatorio
from jobot.nucleo.tratamento.medicao import Acerto, Medicao

EXEMPLO = Path(__file__).parent.parent / "fixtures" / "gabarito_exemplo"
ROTULOS = ("area", "nivel", "modalidade", "contrato", "avisos", "pais", "uf")


def _gabarito(tmp_path: Path) -> Path:
    destino = tmp_path / "gabarito"
    shutil.copytree(EXEMPLO, destino)
    return destino


def _linhas(arquivo: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in arquivo.read_text(encoding="utf-8").splitlines() if x]


def _escrever(arquivo: Path, linhas: list[dict[str, Any]]) -> None:
    arquivo.write_text("".join(json.dumps(x) + "\n" for x in linhas), encoding="utf-8")


def _saida(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    codigo = main(["avaliar-rotulos", *argv])
    capturado = capsys.readouterr()
    return codigo, capturado.out, capturado.err


def test_le_o_caminho_passado(capsys: pytest.CaptureFixture[str]) -> None:
    codigo, out, _ = _saida(capsys, str(EXEMPLO))
    assert codigo == 0
    for rotulo in ROTULOS:
        assert re.search(rf"^{rotulo}\s+\d+/10\s+\d+,\d%$", out, re.MULTILINE), rotulo
    # país e UF do exemplo são inequívocos: acerto total
    assert re.search(r"^pais\s+10/10\s+100,0%$", out, re.MULTILINE)
    assert re.search(r"^uf\s+10/10\s+100,0%$", out, re.MULTILINE)


def test_erro_aparece_com_id_rotulo_esperado_e_obtido(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    gabarito = _gabarito(tmp_path)
    linhas = _linhas(gabarito / "rotulos.jsonl")
    linhas[0]["rotulos"]["area"] = "juridico"  # g01 é uma vaga de desenvolvimento
    _escrever(gabarito / "rotulos.jsonl", linhas)
    codigo, out, _ = _saida(capsys, str(gabarito))
    assert codigo == 0
    assert any(
        linha.split() == ["g01", "area", "juridico", "tecnologia"] for linha in out.splitlines()
    )


def test_caminho_inexistente_avisa_e_sai_com_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo, out, err = _saida(capsys, str(tmp_path / "nao_existe"))
    assert codigo == 0
    assert "não está neste computador" in out + err


def test_caminho_sem_bruto_ou_sem_rotulos_sai_com_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vazio = tmp_path / "vazio"
    vazio.mkdir()
    codigo, _, err = _saida(capsys, str(vazio))
    assert codigo == 1
    assert len(err.strip().splitlines()) == 1

    gabarito = _gabarito(tmp_path)
    (gabarito / "rotulos.jsonl").unlink()
    codigo, _, err = _saida(capsys, str(gabarito))
    assert codigo == 1
    assert "rotulos.jsonl" in err


def test_linha_quebrada_sai_com_1_e_diz_onde(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    gabarito = _gabarito(tmp_path)
    with (gabarito / "bruto" / "exemplo.jsonl").open("a", encoding="utf-8") as f:
        f.write("{isto nao e json\n")
    codigo, _, err = _saida(capsys, str(gabarito))
    assert codigo == 1
    assert "exemplo.jsonl" in err
    assert len(err.strip().splitlines()) == 1


def test_vaga_sem_rotulo_fica_fora_da_amostra(capsys: pytest.CaptureFixture[str]) -> None:
    # o exemplo tem 11 vagas no bruto e 10 linhas em rotulos.jsonl (g08 sem rótulo)
    _, out, _ = _saida(capsys, str(EXEMPLO))
    assert "/10" in out
    assert "/11" not in out
    assert "g08" not in out


def test_relatorio_sem_texto_de_vaga(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    relatorio = tmp_path / "medidos.md"
    codigo, _, _ = _saida(capsys, str(EXEMPLO), "--relatorio", str(relatorio))
    assert codigo == 0
    texto = relatorio.read_text(encoding="utf-8")
    assert texto
    for vaga in _linhas(EXEMPLO / "bruto" / "exemplo.jsonl"):
        assert vaga["titulo"] not in texto
        assert vaga["empresa"] not in texto
        assert vaga["descricao_texto"][:30] not in texto
    for rotulo in ROTULOS:
        assert re.search(rf"\|\s*{rotulo}\s*\|\s*[\d,]+%\s*\|\s*10\s*\|", texto), rotulo


def test_relatorio_tem_proporcao_brasil(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    relatorio = tmp_path / "medidos.md"
    _saida(capsys, str(EXEMPLO), "--relatorio", str(relatorio))
    # g01, g03, g05 e g11 são BR; g02 e g10 têm pais null; 4 sobre 10 rotulados
    assert "Vagas no Brasil: 40,0%" in relatorio.read_text(encoding="utf-8")


def test_relatorio_avisa_que_nao_usa_o_declarado(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    relatorio = tmp_path / "medidos.md"
    _saida(capsys, str(EXEMPLO), "--relatorio", str(relatorio))
    avisos = [
        linha
        for linha in relatorio.read_text(encoding="utf-8").splitlines()
        if "declarado" in linha
    ]
    assert len(avisos) == 1
    assert "modalidade" in avisos[0].lower()
    assert "contrato" in avisos[0]


def test_le_todo_jsonl_da_pasta_e_ignora_subpasta(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    gabarito = _gabarito(tmp_path)
    bruto = gabarito / "bruto"
    vagas = _linhas(bruto / "exemplo.jsonl")
    _escrever(bruto / "exemplo.jsonl", vagas[:5])
    _escrever(bruto / "outro.jsonl", vagas[5:])
    # uma vaga e o rótulo dela dentro de bruto/cache/: se fosse lida, a amostra iria a 11
    (bruto / "cache").mkdir()
    _escrever(bruto / "cache" / "velho.jsonl", [vagas[0] | {"id": "c01"}])
    com_rotulo = _linhas(gabarito / "rotulos.jsonl")
    _escrever(gabarito / "rotulos.jsonl", [*com_rotulo, com_rotulo[0] | {"id": "c01"}])
    _, out, _ = _saida(capsys, str(gabarito))
    assert "/10" in out
    assert "/5" not in out
    assert "/11" not in out


def test_metadados_livres_nao_quebram(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, referencia, _ = _saida(capsys, str(EXEMPLO))
    gabarito = _gabarito(tmp_path)
    vagas = _linhas(gabarito / "bruto" / "exemplo.jsonl")
    vagas[0]["metadados"] = {"chave_nova": [1, 2, {"a": None}], "workplaceType": "hybrid"}
    vagas[1]["metadados"] = {}
    for vaga in vagas[2:]:
        vaga["metadados"] = {"outra": "coisa"}
    _escrever(gabarito / "bruto" / "exemplo.jsonl", vagas)
    codigo, out, _ = _saida(capsys, str(gabarito))
    assert codigo == 0
    assert "/10" in out
    assert out == referencia


def test_chave_a_mais_no_rotulos_e_ignorada(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    gabarito = _gabarito(tmp_path)
    linhas = _linhas(gabarito / "rotulos.jsonl")
    assert any("divergencias" in linha for linha in linhas)  # o exemplo já traz uma
    _, com, _ = _saida(capsys, str(gabarito))
    _escrever(
        gabarito / "rotulos.jsonl",
        [{k: v for k, v in linha.items() if k != "divergencias"} for linha in linhas],
    )
    _, sem, _ = _saida(capsys, str(gabarito))
    assert "/10" in com
    assert com == sem


def test_abaixo_de_90_nao_falha(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    gabarito = _gabarito(tmp_path)
    linhas = _linhas(gabarito / "rotulos.jsonl")
    for linha in linhas:
        linha["rotulos"]["area"] = "juridico"
    _escrever(gabarito / "rotulos.jsonl", linhas)
    codigo, out, _ = _saida(capsys, str(gabarito))
    assert codigo == 0
    assert re.search(r"^area\s+0/10\s+0,0%$", out, re.MULTILINE)


def test_relatorio_traz_a_data_e_o_tamanho_da_amostra() -> None:
    medicao = Medicao(por_rotulo={"area": Acerto(certos=9, total=10)}, erros=(), proporcao_br=0.4)
    texto = relatorio(medicao, 10, date(2026, 11, 14))
    assert "| area | 90,0% | 10 | 2026-11-14 |" in texto.splitlines()


def test_amostra_vazia_sai_com_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    gabarito = _gabarito(tmp_path)
    primeira = _linhas(gabarito / "rotulos.jsonl")[0]
    _escrever(gabarito / "rotulos.jsonl", [primeira | {"id": "sem_vaga"}])
    codigo, _, err = _saida(capsys, str(gabarito))
    assert codigo == 1
    assert err.strip()
