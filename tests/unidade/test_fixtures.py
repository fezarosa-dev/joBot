import hashlib
import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType

import pytest

from jobot.nucleo.coletores.registro import descobrir

RAIZ = Path(__file__).resolve().parents[2]
FIXTURES = RAIZ / "tests" / "fixtures"
LIMITE = 50 * 1024
EMAIL = re.compile(r"[^\s\"'<>@/\[\]()]+@[^\s\"'<>@/\[\]()]+\.[A-Za-z]{2,}")


def _carregar() -> ModuleType:
    spec = importlib.util.spec_from_file_location("capturar_script", RAIZ / "scripts/capturar.py")
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


capturar = _carregar()


def _caso(pasta: Path, nome: str = "normal", conteudo: str = '{"a": 1}') -> Path:
    """Um caso como o `capturar.py` grava: arquivo mais `.meta.json` com o sha256 certo."""
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / f"{nome}.json"
    arquivo.write_text(conteudo, encoding="utf-8")
    meta = {
        "url": "https://exemplo.test/x",
        "data": "2026-11-13T12:00:00+00:00",
        "codigo": 200,
        "cabecalhos": {"Content-Type": "application/json"},
        "sha256": hashlib.sha256(arquivo.read_bytes()).hexdigest(),
        "versao": "0.1.0",
    }
    (pasta / f"{nome}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return arquivo


def _arquivos() -> list[Path]:
    return [p for p in sorted(FIXTURES.rglob("*")) if p.is_file()]


def test_todo_coletor_tem_fixture_com_meta(tmp_path: Path) -> None:
    pasta = tmp_path / "a"
    pasta.mkdir()
    (pasta / "normal.json").write_text("{}", encoding="utf-8")
    assert any("meta" in p for p in capturar.problemas(pasta))  # caso sem .meta.json
    (pasta / "normal.meta.json").write_text('{"url": "https://exemplo.test"}', encoding="utf-8")
    faltas = " ".join(capturar.problemas(pasta))
    assert all(campo in faltas for campo in ("data", "codigo", "cabecalhos", "sha256", "versao"))
    assert capturar.problemas(tmp_path / "ausente")  # fonte sem pasta
    assert capturar.problemas(tmp_path / "vazia_nao_existe_ainda")
    (tmp_path / "vazia").mkdir()
    assert capturar.problemas(tmp_path / "vazia")  # pasta sem nenhum caso
    _caso(tmp_path / "boa")
    assert capturar.problemas(tmp_path / "boa") == []
    for chave in descobrir():
        assert capturar.problemas(FIXTURES / chave) == [], chave


def test_fixtures_sem_email_telefone_nem_nome(tmp_path: Path) -> None:
    _caso(tmp_path / "ruim", conteudo='{"contato": "ana@empresa.com.br"}')
    assert any("email" in p for p in capturar.problemas(tmp_path / "ruim"))
    for arquivo in _arquivos():
        texto = arquivo.read_text(encoding="utf-8", errors="replace")
        assert capturar.achar_pessoais(texto) == [], arquivo.name
        achados = [e for e in EMAIL.findall(texto) if not e.endswith("@exemplo.invalid")]
        assert achados == [], arquivo.name


@pytest.mark.parametrize(
    ("amostra", "tipo"),
    [
        ('{"contato": "ana@empresa.com.br"}', "email"),
        ('{"d": "ligue +55 11 98765-4321"}', "telefone"),
        ('{"d": "ligue (11) 98765-4321"}', "telefone"),
        ('{"d": "cpf 123.456.789-09"}', "cpf"),
        ('{"user": {"login": "maria-silva"}}', "login"),
        ('{"by": "joao"}', "by"),
        ('{"recruiter": "Ana Souza"}', "recruiter"),
        ('{"autor": "Pedro"}', "autor"),
        ("<item><dc:creator>Maria Silva</dc:creator></item>", "creator"),
    ],
)
def test_detector_acha_cada_tipo_de_dado_pessoal(amostra: str, tipo: str) -> None:
    achados = capturar.achar_pessoais(amostra)
    assert achados and tipo in " ".join(achados)
    assert capturar.achar_pessoais(capturar.limpar_pessoais(amostra)) == []


def test_detector_deixa_passar_o_que_nao_e_pessoal() -> None:
    limpo = '{"user": {"login": "exemplo"}, "by": null, "titulo": "Dev", "data": "2026-11-13"}'
    assert capturar.achar_pessoais(limpo) == []


def test_fixture_ate_50_kb(tmp_path: Path) -> None:
    _caso(tmp_path / "gorda", conteudo=json.dumps({"d": "x" * (LIMITE + 1)}))
    assert any("50 KB" in p for p in capturar.problemas(tmp_path / "gorda"))
    _caso(tmp_path / "justa", conteudo=json.dumps({"d": "x" * (LIMITE - 100)}))
    assert capturar.problemas(tmp_path / "justa") == []
    for arquivo in _arquivos():
        assert arquivo.stat().st_size <= LIMITE, arquivo.name


def test_copia_editada_tem_nome_editado(tmp_path: Path) -> None:
    pasta = tmp_path / "fonte"
    original = _caso(pasta)
    assert capturar.problemas(pasta) == []
    # mexer à mão no arquivo capturado: o sha256 do meta denuncia
    original.write_text('{"a": 2}', encoding="utf-8")
    assert any("editado" in p and "sha256" in p for p in capturar.problemas(pasta))
    # a cópia editada é um arquivo à parte, com `.editado.` no nome e sem meta
    original.write_text('{"a": 1}', encoding="utf-8")
    (pasta / "formato_mudou.editado.json").write_text('{"b": 1}', encoding="utf-8")
    assert capturar.problemas(pasta) == []
    # a mesma cópia sem o marcador no nome é recusada
    (pasta / "formato_mudou.json").write_text('{"b": 1}', encoding="utf-8")
    assert any("formato_mudou.json" in p and "editado" in p for p in capturar.problemas(pasta))


@pytest.mark.parametrize(
    "texto",
    [
        "[@angular/common](https://github.com/angular/angular)",
        "updates [@angular-devkit/build-angular](https://github.com/angular/angular-cli)",
    ],
)
def test_regex_email_ignora_mencao_de_pacote_em_markdown(texto: str) -> None:
    assert EMAIL.findall(texto) == []


@pytest.mark.parametrize(
    "email", ["ana@empresa.com.br", "fulano.silva+x@gmail.com", "contato@sub.empresa.io"]
)
def test_regex_email_casa_email_inteiro(email: str) -> None:
    assert EMAIL.findall(f"fale com {email}.") == [email]
