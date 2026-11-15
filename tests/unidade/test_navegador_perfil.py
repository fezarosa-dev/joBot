import json
import logging
import os
import stat
from pathlib import Path

import pytest

from jobot.navegador.perfil import (
    PREFERENCIAS,
    apagar_perfil,
    pasta_do_perfil,
    preparar_preferencias,
)
from jobot.sistema.pastas import PASTA_NAVEGADOR

TRES = {
    "credentials_enable_service": False,
    "profile": {"password_manager_enabled": False},
    "autofill": {"profile_enabled": False},
}


def _modo(p: Path) -> int:
    return stat.S_IMODE(p.stat().st_mode)


def _prefs(perfil: Path) -> Path:
    return perfil / "Default" / "Preferences"


def _lido(perfil: Path) -> object:
    assert _prefs(perfil).exists(), "Preferences não foi gravado"
    try:
        return json.loads(_prefs(perfil).read_text(encoding="utf-8"))
    except ValueError, RecursionError:
        return None  # ilegível: o assert do teste reprova


def _com(perfil: Path, conteudo: bytes) -> None:
    _prefs(perfil).parent.mkdir(parents=True)
    _prefs(perfil).write_bytes(conteudo)


def test_preferencias_sao_as_tres_chaves() -> None:
    assert PREFERENCIAS == TRES


def test_pasta_do_perfil_nasce_0700(tmp_path: Path) -> None:
    pasta = pasta_do_perfil(tmp_path / "dados")
    assert pasta == tmp_path / "dados" / PASTA_NAVEGADOR
    assert pasta.is_dir()
    assert _modo(pasta) == 0o700
    assert pasta_do_perfil(tmp_path / "dados") == pasta  # de novo: sem erro


def test_pasta_do_perfil_symlink_e_recusada(tmp_path: Path) -> None:
    fora = tmp_path / "fora"
    fora.mkdir()
    dados = tmp_path / "dados"
    dados.mkdir()
    (dados / PASTA_NAVEGADOR).symlink_to(fora)
    with pytest.raises(OSError):
        pasta_do_perfil(dados)
    assert list(fora.iterdir()) == []


def test_preferencias_em_perfil_vazio(tmp_path: Path) -> None:
    perfil = tmp_path / "perfil"
    perfil.mkdir()
    preparar_preferencias(perfil)
    assert _lido(perfil) == TRES
    assert _modo(_prefs(perfil)) == 0o600
    assert sorted(p.name for p in _prefs(perfil).parent.iterdir()) == ["Preferences"]


def test_preferencias_preservam_outras_chaves(tmp_path: Path) -> None:
    perfil = tmp_path / "perfil"
    antigo = {
        "profile": {"name": "x", "password_manager_enabled": True},
        "autofill": {"credit_card_enabled": True},
        "credentials_enable_service": True,
        "outra": 1,
    }
    _com(perfil, json.dumps(antigo).encode())
    preparar_preferencias(perfil)
    assert _lido(perfil) == {
        "profile": {"name": "x", "password_manager_enabled": False},
        "autofill": {"credit_card_enabled": True, "profile_enabled": False},
        "credentials_enable_service": False,
        "outra": 1,
    }


def test_preferencias_com_bloco_que_nao_e_objeto(tmp_path: Path) -> None:
    perfil = tmp_path / "perfil"
    _com(perfil, json.dumps({"profile": 5, "autofill": [1], "outra": 1}).encode())
    preparar_preferencias(perfil)
    assert _lido(perfil) == {**TRES, "outra": 1}


def test_preferencias_arquivo_torto_reescreve(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    perfil = tmp_path / "perfil"
    _com(perfil, b"{quebrado SEGREDO")
    with caplog.at_level(logging.WARNING):
        preparar_preferencias(perfil)
    assert _lido(perfil) == TRES
    assert "reescrito" in caplog.text
    assert "SEGREDO" not in caplog.text


@pytest.mark.parametrize("conteudo", [b"\xff\xfe", b"[1, 2]", b'"texto"', b"[" * 100_000])
def test_preferencias_nao_utf8_ou_lista_reescreve(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, conteudo: bytes
) -> None:
    perfil = tmp_path / "perfil"
    _com(perfil, conteudo)
    with caplog.at_level(logging.WARNING):
        preparar_preferencias(perfil)
    assert _lido(perfil) == TRES
    assert "reescrito" in caplog.text


def test_preferencias_sem_arquivo_nao_loga_reescrita(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    perfil = tmp_path / "perfil"
    perfil.mkdir()
    with caplog.at_level(logging.WARNING):
        preparar_preferencias(perfil)
    assert "reescrito" not in caplog.text


def test_preferencias_symlink_e_recusado(tmp_path: Path) -> None:
    perfil = tmp_path / "perfil"
    alvo = tmp_path / "fora.json"
    alvo.write_text('{"intacto": 1}', encoding="utf-8")
    _prefs(perfil).parent.mkdir(parents=True)
    _prefs(perfil).symlink_to(alvo)
    with pytest.raises(OSError):
        preparar_preferencias(perfil)
    assert alvo.read_text(encoding="utf-8") == '{"intacto": 1}'
    assert _prefs(perfil).is_symlink()


def test_preferencias_default_symlink_e_recusado(tmp_path: Path) -> None:
    perfil = tmp_path / "perfil"
    perfil.mkdir()
    fora = tmp_path / "fora"
    fora.mkdir()
    (perfil / "Default").symlink_to(fora)
    with pytest.raises(OSError):
        preparar_preferencias(perfil)
    assert list(fora.iterdir()) == []


def test_preferencias_leitura_nao_segue_symlink_que_aparece_depois_da_checagem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    perfil = tmp_path / "perfil"
    alvo = tmp_path / "fora.json"
    alvo.write_text('{"intacto": 1}', encoding="utf-8")
    _prefs(perfil).parent.mkdir(parents=True)
    _prefs(perfil).symlink_to(alvo)
    real = Path.is_symlink
    # o link surge depois de a checagem passar: só a leitura sem seguir link o pega
    monkeypatch.setattr(
        Path, "is_symlink", lambda self: False if self.name == "Preferences" else real(self)
    )
    with pytest.raises(OSError):
        preparar_preferencias(perfil)
    assert alvo.read_text(encoding="utf-8") == '{"intacto": 1}'


def test_preferencias_falha_na_gravacao_nao_afirma_reescrita(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    perfil = tmp_path / "perfil"
    _com(perfil, b"{quebrado")

    def quebra(origem: object, destino: object) -> None:
        raise OSError("disco")

    monkeypatch.setattr(os, "replace", quebra)
    with caplog.at_level(logging.WARNING), pytest.raises(OSError):
        preparar_preferencias(perfil)
    assert "reescrito" not in caplog.text


def test_preferencias_gravam_pelo_tmp_0600(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    perfil = tmp_path / "perfil"
    vistos: list[tuple[Path, int, bool]] = []
    real = os.replace

    def espia(origem: str | Path, destino: str | Path) -> None:
        vistos.append((Path(origem), _modo(Path(origem)), Path(destino) == _prefs(perfil)))
        real(origem, destino)

    monkeypatch.setattr(os, "replace", espia)
    _prefs(perfil).parent.mkdir(parents=True)
    anterior = os.umask(0o277)  # um open(…, 0o600) sozinho sairia 0400
    try:
        preparar_preferencias(perfil)
    finally:
        os.umask(anterior)
    assert len(vistos) == 1
    origem, modo, para_o_arquivo = vistos[0]
    assert origem.parent == _prefs(perfil).parent
    assert origem != _prefs(perfil)
    assert modo == 0o600
    assert para_o_arquivo
    assert _lido(perfil) == TRES


def test_preferencias_falha_na_troca_mantem_o_antigo_e_limpa_o_tmp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    perfil = tmp_path / "perfil"
    _com(perfil, b'{"outra": 1}')

    def quebra(origem: object, destino: object) -> None:
        raise OSError("disco")

    monkeypatch.setattr(os, "replace", quebra)
    with pytest.raises(OSError):
        preparar_preferencias(perfil)
    assert _prefs(perfil).read_bytes() == b'{"outra": 1}'
    assert [p.name for p in _prefs(perfil).parent.iterdir()] == ["Preferences"]


def test_preferencias_tmp_velho_nao_atrapalha(tmp_path: Path) -> None:
    perfil = tmp_path / "perfil"
    perfil.mkdir()
    (perfil / "Default").mkdir()
    sobra = perfil / "Default" / "Preferences.tmp"
    sobra.write_text("lixo")
    preparar_preferencias(perfil)
    assert _lido(perfil) == TRES
    assert not sobra.exists()


def test_apagar_perfil(tmp_path: Path) -> None:
    dados = tmp_path / "dados"
    perfil = dados / PASTA_NAVEGADOR
    _com(perfil, b"{}")
    (dados / "jobot.db").write_text("banco", encoding="utf-8")
    apagar_perfil(dados)
    assert not perfil.exists()
    assert (dados / "jobot.db").read_text() == "banco"
    apagar_perfil(dados)  # sem perfil: não erra


def test_apagar_perfil_symlink_nao_apaga_o_alvo(tmp_path: Path) -> None:
    fora = tmp_path / "fora"
    fora.mkdir()
    (fora / "dado.txt").write_text("vivo")
    dados = tmp_path / "dados"
    dados.mkdir()
    (dados / PASTA_NAVEGADOR).symlink_to(fora)
    with pytest.raises(OSError):
        apagar_perfil(dados)
    assert (fora / "dado.txt").read_text() == "vivo"


def test_apagar_perfil_nao_segue_symlink_de_dentro(tmp_path: Path) -> None:
    fora = tmp_path / "fora"
    fora.mkdir()
    (fora / "dado.txt").write_text("vivo")
    dados = tmp_path / "dados"
    perfil = dados / PASTA_NAVEGADOR
    perfil.mkdir(parents=True)
    (perfil / "atalho").symlink_to(fora)
    apagar_perfil(dados)
    assert not perfil.exists()
    assert (fora / "dado.txt").read_text() == "vivo"
