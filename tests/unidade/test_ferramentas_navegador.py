"""`jobot ferramentas baixar navegador` (T330; D174.2): três caminhos, sem rede e sem processo."""

import argparse
import hashlib
import io
import json
import os
import stat
import sys
import tarfile
from collections.abc import Mapping, Sequence
from pathlib import Path

import httpx
import pytest

import jobot
import jobot.cli
from apoio.janela_falsa import JanelaFalsa
from jobot.cli import ferramentas
from jobot.navegador.chromium import pasta_do_playwright
from jobot.navegador.instalador import comando_de_baixar
from jobot.navegador.janela_comum import Janela
from jobot.sistema.instalacao import manifesto_da_casca

NOME = "chromium-linux-x86_64.tar.gz"
URL = f"https://github.com/fezarosa-dev/joBot/releases/download/v{jobot.__version__}/{NOME}"


def _tar(pasta: Path, *, ruim: str | None = None) -> bytes:
    """Um `chromium-1/` com executável e symlink relativo; `ruim` acrescenta uma entrada por
    último: `fora` (caminho para fora) ou `link_fora` (symlink absoluto)."""
    raiz = pasta / "origem"
    exe = raiz / "chromium-1" / "chrome-linux" / "chrome"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"#!/bin/sh\n")
    exe.chmod(0o755)
    (exe.parent / "atalho").symlink_to("chrome")
    (raiz / "chromium-1" / "INSTALLATION_COMPLETE").write_text("")
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        tar.add(raiz / "chromium-1", arcname="chromium-1")
        if ruim == "fora":
            info = tarfile.TarInfo("../fora.txt")
            info.size = 3
            tar.addfile(info, io.BytesIO(b"oi\n"))
        elif ruim == "link_fora":
            info = tarfile.TarInfo("chromium-1/etc")
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc"
            tar.addfile(info)
    return buffer.getvalue()


def _hex(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def _args(arquivo: Path | None = None, sha256: str | None = None) -> argparse.Namespace:
    return argparse.Namespace(
        comando="ferramentas",
        acao="baixar",
        ferramenta="navegador",
        arquivo=None if arquivo is None else str(arquivo),
        sha256=sha256,
    )


def _linhas(saida: str) -> list[dict[str, object]]:
    return [json.loads(linha) for linha in saida.splitlines()]


def _arvore(pasta: Path) -> list[str]:
    if not pasta.exists():
        return []
    return sorted(str(p.relative_to(pasta)) for p in pasta.rglob("*"))


class _Abrir:
    def __init__(self, codigo: int = 0) -> None:
        self.codigo = codigo
        self.abertos: list[list[str]] = []

    async def __call__(self, argumentos: Sequence[str], ambiente: Mapping[str, str]) -> Janela:
        self.abertos.append(list(argumentos))
        return JanelaFalsa(ja_saiu=True, codigo=self.codigo)


def _rodar(
    tmp_path: Path,
    args: argparse.Namespace,
    *,
    transporte: httpx.MockTransport | None = None,
    abrir: _Abrir | None = None,
) -> int:
    def cliente() -> httpx.Client:
        if transporte is None:
            raise AssertionError("este caminho não devia abrir rede")
        return httpx.Client(transport=transporte, follow_redirects=True)

    return ferramentas.baixar_navegador(
        args,
        dados=tmp_path / "dados",
        destino=tmp_path / "ms-playwright",
        abrir_cliente=cliente,
        abrir=abrir or _Abrir(),
    )


# ------------------------------------------------------------------ pasta padrão do Playwright


@pytest.mark.parametrize(
    ("plataforma", "ambiente", "esperada"),
    [
        ("linux", {"HOME": "/casa/ana"}, "/casa/ana/.cache/ms-playwright"),
        ("linux", {"HOME": "/casa/ana", "XDG_CACHE_HOME": "/cache"}, "/cache/ms-playwright"),
        ("darwin", {"HOME": "/Users/ana"}, "/Users/ana/Library/Caches/ms-playwright"),
        (
            "win32",
            {"LOCALAPPDATA": "C:/Users/ana/AppData/Local"},
            "C:/Users/ana/AppData/Local/ms-playwright",
        ),  # noqa: E501
        ("linux", {"HOME": "/casa/ana", "PLAYWRIGHT_BROWSERS_PATH": "/outra"}, "/outra"),
    ],
)
def test_pasta_padrao_do_playwright_por_sistema(
    plataforma: str, ambiente: dict[str, str], esperada: str
) -> None:
    assert pasta_do_playwright(ambiente, plataforma) == Path(esperada)


# ------------------------------------------------------------------ instalacao.json


def test_manifesto_so_no_canal_casca(tmp_path: Path) -> None:
    assert manifesto_da_casca(tmp_path) is None  # sem o arquivo: clone ou uv tool
    arquivo = tmp_path / "instalacao.json"
    arquivo.write_text(json.dumps({"canal": "outro", "manifesto": "/m.json"}))
    assert manifesto_da_casca(tmp_path) is None
    arquivo.write_text(json.dumps({"canal": "casca", "manifesto": "/pasta/manifesto-0.4.0.json"}))
    assert manifesto_da_casca(tmp_path) == Path("/pasta/manifesto-0.4.0.json")


@pytest.mark.parametrize(
    "conteudo", ["{", '{"canal": "casca"}', '{"canal": "casca", "manifesto": 3}']
)
def test_instalacao_quebrada_da_valueerror(tmp_path: Path, conteudo: str) -> None:
    (tmp_path / "instalacao.json").write_text(conteudo)
    with pytest.raises(ValueError, match="instalacao.json"):
        manifesto_da_casca(tmp_path)


# ------------------------------------------------------------------ (a) --arquivo e --sha256


def test_arquivo_certo_extrai_com_x_e_symlink(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dados = _tar(tmp_path)
    arquivo = tmp_path / NOME
    arquivo.write_bytes(dados)
    assert _rodar(tmp_path, _args(arquivo, _hex(dados))) == 0
    linhas = _linhas(capsys.readouterr().out)
    assert linhas[-1:] == [{"fim": "pronto"}]
    progresso = linhas[:-1]
    assert progresso and all(linha["etapa"] == "navegador" for linha in progresso)
    assert progresso[-1]["feito"] == progresso[-1]["total"]
    exe = tmp_path / "ms-playwright" / "chromium-1" / "chrome-linux" / "chrome"
    assert exe.read_bytes() == b"#!/bin/sh\n"
    if sys.platform != "win32":
        assert os.stat(exe).st_mode & stat.S_IXUSR
    atalho = exe.parent / "atalho"
    assert atalho.is_symlink()
    assert os.readlink(atalho) == "chrome"
    assert not [p for p in _arvore(tmp_path / "ms-playwright") if p.startswith(".")]


def test_sha256_diferente_nao_extrai_nada(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dados = _tar(tmp_path)
    arquivo = tmp_path / NOME
    arquivo.write_bytes(dados)
    assert _rodar(tmp_path, _args(arquivo, "0" * 64)) == 1
    assert _linhas(capsys.readouterr().out)[-1:] == [{"fim": "falhou"}]
    assert _arvore(tmp_path / "ms-playwright") == []


@pytest.mark.parametrize("ruim", ["fora", "link_fora"])
def test_entrada_para_fora_recusa_e_nao_deixa_metade(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], ruim: str
) -> None:
    dados = _tar(tmp_path, ruim=ruim)
    arquivo = tmp_path / NOME
    arquivo.write_bytes(dados)
    assert _rodar(tmp_path, _args(arquivo, _hex(dados))) == 1
    assert _linhas(capsys.readouterr().out)[-1:] == [{"fim": "falhou"}]
    assert _arvore(tmp_path / "ms-playwright") == []
    assert not (tmp_path / "fora.txt").exists()


def test_arquivo_sem_sha256_e_recusado(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    arquivo = tmp_path / NOME
    arquivo.write_bytes(_tar(tmp_path))
    assert _rodar(tmp_path, _args(arquivo, None)) == 1
    assert _linhas(capsys.readouterr().out) == [{"fim": "falhou"}]
    assert _arvore(tmp_path / "ms-playwright") == []


# ------------------------------------------------------------------ (b) canal casca


def _casca(tmp_path: Path, arquivos: list[dict[str, object]]) -> None:
    pasta = tmp_path / "dados"
    pasta.mkdir()
    manifesto = tmp_path / "app" / f"manifesto-{jobot.__version__}.json"
    manifesto.parent.mkdir()
    manifesto.write_text(json.dumps({"versao": jobot.__version__, "arquivos": arquivos}))
    (pasta / "instalacao.json").write_text(
        json.dumps({"canal": "casca", "manifesto": str(manifesto)})
    )


def _servidor(corpo: bytes, pedidos: list[str]) -> httpx.MockTransport:
    def responder(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(str(pedido.url))
        return httpx.Response(200, content=corpo)

    return httpx.MockTransport(responder)


def test_casca_baixa_da_release_e_confere_pelo_manifesto(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dados = _tar(tmp_path)
    _casca(
        tmp_path,
        [
            {"nome": "jobot-0.4.0-py3-none-any.whl", "tamanho": 9, "sha256": "a" * 64},
            {"nome": NOME, "tamanho": len(dados), "sha256": _hex(dados)},
        ],
    )
    pedidos: list[str] = []
    assert _rodar(tmp_path, _args(), transporte=_servidor(dados, pedidos)) == 0
    assert pedidos == [URL]
    assert _linhas(capsys.readouterr().out)[-1:] == [{"fim": "pronto"}]
    assert (tmp_path / "ms-playwright" / "chromium-1" / "chrome-linux" / "chrome").exists()
    assert not [p for p in os.listdir(tmp_path / "ms-playwright") if p.startswith(".")]


def test_casca_com_hash_diferente_nao_muda_nada(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dados = _tar(tmp_path)
    _casca(tmp_path, [{"nome": NOME, "tamanho": len(dados), "sha256": "b" * 64}])
    pedidos: list[str] = []
    assert _rodar(tmp_path, _args(), transporte=_servidor(dados, pedidos)) == 1
    assert pedidos == [URL]
    assert _linhas(capsys.readouterr().out)[-1:] == [{"fim": "falhou"}]
    assert _arvore(tmp_path / "ms-playwright") == []


def test_casca_sem_chromium_no_manifesto_nao_baixa(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _casca(tmp_path, [{"nome": "jobot-0.4.0-py3-none-any.whl", "tamanho": 9, "sha256": "a" * 64}])
    pedidos: list[str] = []
    assert _rodar(tmp_path, _args(), transporte=_servidor(b"x", pedidos)) == 1
    assert pedidos == []
    assert _linhas(capsys.readouterr().out) == [{"fim": "falhou"}]
    assert _arvore(tmp_path / "ms-playwright") == []


def test_casca_corta_download_maior_que_o_manifesto(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dados = _tar(tmp_path)
    _casca(tmp_path, [{"nome": NOME, "tamanho": len(dados) - 1, "sha256": _hex(dados)}])
    assert _rodar(tmp_path, _args(), transporte=_servidor(dados, [])) == 1
    assert _linhas(capsys.readouterr().out)[-1:] == [{"fim": "falhou"}]
    assert _arvore(tmp_path / "ms-playwright") == []


def test_casca_com_erro_404_falha(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    dados = _tar(tmp_path)
    _casca(tmp_path, [{"nome": NOME, "tamanho": len(dados), "sha256": _hex(dados)}])
    transporte = httpx.MockTransport(lambda pedido: httpx.Response(404))
    assert _rodar(tmp_path, _args(), transporte=transporte) == 1
    assert _linhas(capsys.readouterr().out)[-1:] == [{"fim": "falhou"}]
    assert _arvore(tmp_path / "ms-playwright") == []


# ------------------------------------------------------------------ (c) sem casca


@pytest.mark.parametrize(("codigo", "fim", "saida"), [(0, "pronto", 0), (1, "falhou", 1)])
def test_sem_casca_chama_o_playwright_install(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], codigo: int, fim: str, saida: int
) -> None:
    abrir = _Abrir(codigo)
    assert _rodar(tmp_path, _args(), abrir=abrir) == saida
    assert abrir.abertos == [comando_de_baixar()]
    assert _linhas(capsys.readouterr().out) == [{"fim": fim}]


def test_main_chega_no_subcomando(monkeypatch: pytest.MonkeyPatch) -> None:
    recebidos: list[argparse.Namespace] = []

    def falso(args: argparse.Namespace, **_: object) -> int:
        recebidos.append(args)
        return 0

    monkeypatch.setattr(ferramentas, "baixar_navegador", falso)
    argv = ["ferramentas", "baixar", "navegador", "--arquivo", "c.tar.gz", "--sha256", "ab"]
    assert jobot.cli.main(argv) == 0
    assert [(a.acao, a.ferramenta, a.arquivo, a.sha256) for a in recebidos] == [
        ("baixar", "navegador", "c.tar.gz", "ab")
    ]
