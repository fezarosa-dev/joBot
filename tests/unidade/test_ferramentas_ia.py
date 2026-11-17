"""`jobot ferramentas baixar|atualizar|remover ia-local` (T409; desenho 7; D195): `JOBOT_DADOS` em
`tmp_path`, os downloads por `httpx.MockTransport` (sem rede), o `--version` por um falso e o
`llama-server` do teste do `+x` pelo servidor falso em thread (`apoio.llama_falso`)."""

import hashlib
import io
import json
import os
import stat
import sys
import tarfile
from collections.abc import Callable, Iterator
from contextlib import closing
from pathlib import Path
from typing import Any

import httpx
import pytest

import jobot.cli
from apoio.llama_falso import LancadorFalso, RelogioSincrono, ServidorLlamaFalso
from jobot.banco.cadastros import gravar_config, ler_config
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.cli import ferramentas
from jobot.sistema.llama import FalhaLlama, Llama
from jobot.sistema.memoria import GIB
from jobot.sistema.pastas import preparar_pasta

PROGRAMA = b"#!/bin/sh\necho 'version: b1'\n"
GGUF_2B = b"GGUF-2b" * 100
GGUF_4B = b"GGUF-4b" * 150


def _tar(membros: dict[str, bytes]) -> bytes:
    """`.tar.gz` com os membros sem `+x` (modo 0644): quem dá o `+x` é o joBot."""
    saida = io.BytesIO()
    with tarfile.open(fileobj=saida, mode="w:gz") as tf:
        for nome, corpo in membros.items():
            info = tarfile.TarInfo(nome)
            info.size, info.mode = len(corpo), 0o644
            tf.addfile(info, io.BytesIO(corpo))
    return saida.getvalue()


def _item(url: str, corpo: bytes, arquivo: str) -> dict[str, Any]:
    return {
        "arquivo": arquivo,
        "url": url,
        "tamanho": len(corpo),
        "sha256": hashlib.sha256(corpo).hexdigest(),
        "licenca": "MIT",
        "origem": "teste",
    }


class Rede:
    """Os arquivos por URL e os pedidos em ordem, num `MockTransport` (nada sai da máquina)."""

    def __init__(self) -> None:
        self.arquivos: dict[str, bytes] = {}
        self.pedidos: list[str] = []
        self.cliente = httpx.Client(transport=httpx.MockTransport(self._responder))

    def _responder(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(str(pedido.url))
        corpo = self.arquivos.get(str(pedido.url))
        if corpo is None:
            return httpx.Response(404)
        # em fluxo, como a rede: `baixar` lê com `iter_raw`
        return httpx.Response(200, stream=httpx.ByteStream(corpo))

    def manifesto(
        self,
        build: str = "b1",
        servidor: bytes | None = None,
        modelos: dict[str, bytes] | None = None,
    ) -> dict[str, Any]:
        servidor = _tar({f"llama-{build}/llama-server": PROGRAMA}) if servidor is None else servidor
        modelos = {"2b": GGUF_2B, "4b": GGUF_4B} if modelos is None else modelos
        arquivo = f"llama-{build}-bin-ubuntu-x64.tar.gz"
        url = f"https://exemplo.test/releases/download/{build}/{arquivo}"
        self.arquivos[url] = servidor
        itens = {}
        for chave, corpo in modelos.items():
            nome = f"Modelo-{chave}-{hashlib.sha256(corpo).hexdigest()[:6]}.gguf"
            self.arquivos[f"https://exemplo.test/m/{nome}"] = corpo
            itens[chave] = _item(f"https://exemplo.test/m/{nome}", corpo, nome)
        return {
            "llama_server": {
                "build": build,
                "alvos": {"ubuntu-x64": _item(url, servidor, arquivo)},
            },
            "modelos": itens,
        }


@pytest.fixture
def rede() -> Iterator[Rede]:
    r = Rede()
    yield r
    r.cliente.close()


class Versao:
    """O `llama-server --version` falso: grava o programa e os pedidos já feitos à rede."""

    def __init__(self, rede: Rede, *, ok: bool = True) -> None:
        self.rede, self.ok = rede, ok
        self.chamadas: list[tuple[Path, list[str]]] = []

    def __call__(self, programa: Path) -> bool:
        self.chamadas.append((programa, list(self.rede.pedidos)))
        return self.ok


def _linhas(saida: str) -> list[dict[str, Any]]:
    return [json.loads(linha) for linha in saida.splitlines()]


def _baixar(
    dados: Path,
    rede: Rede,
    manifesto: dict[str, Any],
    escolha: str = "2b",
    *,
    versao: Callable[[Path], bool] | None = None,
    memoria: Callable[[], int] = lambda: 16 * GIB,
) -> int:
    return ferramentas.baixar_ia_local(
        dados,
        escolha,
        manifesto=manifesto,
        cliente=rede.cliente,
        versao=versao or Versao(rede),
        memoria=memoria,
        alvo="ubuntu-x64",
    )


def _atualizar(dados: Path, rede: Rede, manifesto: dict[str, Any]) -> int:
    return ferramentas.atualizar_ia_local(
        dados, manifesto=manifesto, cliente=rede.cliente, versao=Versao(rede), alvo="ubuntu-x64"
    )


def _ferramentas(dados: Path) -> Path:
    return dados / "ferramentas"


def _nomes(pasta: Path) -> list[str]:
    """Os nomes na pasta, fora a `.trava` vazia que cada download deixa (D189.1)."""
    if not pasta.is_dir():
        return ["<sem a pasta>"]
    return sorted(p.name for p in pasta.iterdir() if p.suffix != ".trava")


def test_baixa_o_servidor_roda_a_versao_e_so_entao_o_modelo(
    tmp_path: Path, rede: Rede, capsys: pytest.CaptureFixture[str]
) -> None:
    manifesto = rede.manifesto()
    versao = Versao(rede)
    assert _baixar(tmp_path, rede, manifesto, "4b", versao=versao) == 0
    servidor = manifesto["llama_server"]["alvos"]["ubuntu-x64"]
    modelo = manifesto["modelos"]["4b"]
    assert rede.pedidos == [servidor["url"], modelo["url"]]
    programa = _ferramentas(tmp_path) / "llama" / "b1" / "llama-b1" / "llama-server"
    # o `--version` roda no programa já extraído, depois do servidor e antes do modelo
    assert versao.chamadas == [(programa, [servidor["url"]])]
    assert os.access(programa, os.X_OK)
    gguf = _ferramentas(tmp_path) / "modelos" / modelo["arquivo"]
    assert gguf.read_bytes() == GGUF_4B
    assert not (_ferramentas(tmp_path) / "llama" / servidor["arquivo"]).exists()  # o pacote some
    linhas = _linhas(capsys.readouterr().out)
    assert linhas[-1] == {"fim": "pronto"}
    etapas = [(linha["feito"], linha["total"]) for linha in linhas if "etapa" in linha]
    assert etapas[0] == (0, servidor["tamanho"])
    assert (servidor["tamanho"], servidor["tamanho"]) in etapas
    assert etapas[-1] == (modelo["tamanho"], modelo["tamanho"])
    assert all(linha.get("etapa") == "ia_local" for linha in linhas[:-1])


def test_anota_o_que_baixou(tmp_path: Path, rede: Rede) -> None:
    manifesto = rede.manifesto()
    assert _baixar(tmp_path, rede, manifesto, "2b") == 0
    assert ferramentas.ler_anotacao(tmp_path) == {
        "build": "b1",
        "alvo": "ubuntu-x64",
        "programa": "llama/b1/llama-b1/llama-server",
        "servidor_sha256": manifesto["llama_server"]["alvos"]["ubuntu-x64"]["sha256"],
        "modelo": "2b",
        "arquivo": manifesto["modelos"]["2b"]["arquivo"],
        "modelo_sha256": manifesto["modelos"]["2b"]["sha256"],
    }
    if sys.platform != "win32":
        anotacao = _ferramentas(tmp_path) / "ia_local.json"
        assert stat.S_IMODE(anotacao.stat().st_mode) == 0o600


def test_versao_que_falha_para_antes_do_modelo(
    tmp_path: Path, rede: Rede, capsys: pytest.CaptureFixture[str]
) -> None:
    manifesto = rede.manifesto()
    assert _baixar(tmp_path, rede, manifesto, "2b", versao=Versao(rede, ok=False)) == 1
    assert rede.pedidos == [manifesto["llama_server"]["alvos"]["ubuntu-x64"]["url"]]
    assert _linhas(capsys.readouterr().out)[-1] == {"fim": "falhou", "motivo": "programa_ausente"}
    assert not (_ferramentas(tmp_path) / "modelos").exists()
    assert ferramentas.ler_anotacao(tmp_path) == {}


@pytest.mark.parametrize(
    ("gib", "modelo", "lento"),
    [(11.5, "4b", False), (7.7, "2b", False), (6.5, "2b", True)],  # PC de 12 GB, de 8 GB e menos
)
def test_auto_imprime_a_memoria_lida_e_o_modelo(
    tmp_path: Path,
    rede: Rede,
    capsys: pytest.CaptureFixture[str],
    gib: float,
    modelo: str,
    lento: bool,
) -> None:
    manifesto = rede.manifesto()
    total = int(gib * GIB)
    assert _baixar(tmp_path, rede, manifesto, "auto", memoria=lambda: total) == 0
    primeira = _linhas(capsys.readouterr().out)[:1]
    assert primeira == [{"memoria": total, "modelo": modelo, "lento": lento}]
    assert rede.pedidos[-1:] == [manifesto["modelos"][modelo]["url"]]


def test_modelo_escolhido_nao_le_a_memoria(tmp_path: Path, rede: Rede) -> None:
    """(guarda) controle: `test_auto_imprime_a_memoria_lida_e_o_modelo` lê a memória."""

    def memoria() -> int:
        raise AssertionError("leu a memória")

    assert _baixar(tmp_path, rede, rede.manifesto(), "4b", memoria=memoria) == 0


def test_sem_alvo_para_este_computador_falha_sem_pedido(
    tmp_path: Path, rede: Rede, capsys: pytest.CaptureFixture[str]
) -> None:
    feito = ferramentas.baixar_ia_local(
        tmp_path, "2b", manifesto=rede.manifesto(), cliente=rede.cliente, alvo=None
    )
    assert feito == 1
    assert rede.pedidos == []
    assert _linhas(capsys.readouterr().out) == [{"fim": "falhou", "motivo": "programa_ausente"}]


def test_alvo_daqui() -> None:
    assert ferramentas.alvo_daqui("linux", "x86_64") == "ubuntu-x64"
    assert ferramentas.alvo_daqui("win32", "AMD64") == "win-cpu-x64"
    assert ferramentas.alvo_daqui("darwin", "arm64") == "macos-arm64"
    assert ferramentas.alvo_daqui("darwin", "x86_64") == "macos-x64"
    assert ferramentas.alvo_daqui("linux", "aarch64") is None


def test_download_que_nao_confere_falha_com_o_motivo(
    tmp_path: Path, rede: Rede, capsys: pytest.CaptureFixture[str]
) -> None:
    manifesto = rede.manifesto()
    rede.arquivos[manifesto["modelos"]["2b"]["url"]] = b"x" * len(GGUF_2B)  # outro sha256
    assert _baixar(tmp_path, rede, manifesto, "2b") == 1
    assert _linhas(capsys.readouterr().out)[-1] == {"fim": "falhou", "motivo": "arquivo"}
    anotacao = ferramentas.ler_anotacao(tmp_path)
    assert (anotacao.get("build"), "modelo" in anotacao) == ("b1", False)  # só o servidor anotado


def test_pacote_estragado_nao_deixa_pasta(
    tmp_path: Path, rede: Rede, capsys: pytest.CaptureFixture[str]
) -> None:
    manifesto = rede.manifesto(servidor=b"isto nao e um tar.gz")
    assert _baixar(tmp_path, rede, manifesto, "2b") == 1
    assert _linhas(capsys.readouterr().out)[-1] == {"fim": "falhou", "motivo": "arquivo"}
    assert _nomes(_ferramentas(tmp_path) / "llama") == []


def test_pacote_sem_o_llama_server_e_programa_ausente(
    tmp_path: Path, rede: Rede, capsys: pytest.CaptureFixture[str]
) -> None:
    manifesto = rede.manifesto(servidor=_tar({"llama-b1/llama-cli": PROGRAMA}))
    assert _baixar(tmp_path, rede, manifesto, "2b") == 1
    assert _linhas(capsys.readouterr().out)[-1] == {"fim": "falhou", "motivo": "programa_ausente"}
    assert _nomes(_ferramentas(tmp_path) / "llama") == []
    assert len(rede.pedidos) == 1


def test_atualizar_baixa_so_o_modelo_que_mudou(tmp_path: Path, rede: Rede) -> None:
    velho = rede.manifesto()
    assert _baixar(tmp_path, rede, velho, "2b") == 0
    novo = rede.manifesto(modelos={"2b": GGUF_2B + b"novo", "4b": GGUF_4B})
    rede.pedidos.clear()
    assert _atualizar(tmp_path, rede, novo) == 0
    assert rede.pedidos == [novo["modelos"]["2b"]["url"]]
    modelos = _ferramentas(tmp_path) / "modelos"
    assert _nomes(modelos) == [novo["modelos"]["2b"]["arquivo"]]
    assert ferramentas.ler_anotacao(tmp_path)["modelo_sha256"] == novo["modelos"]["2b"]["sha256"]


def test_atualizar_baixa_so_o_servidor_que_mudou(tmp_path: Path, rede: Rede) -> None:
    assert _baixar(tmp_path, rede, rede.manifesto(), "4b") == 0
    novo = rede.manifesto(build="b2")
    rede.pedidos.clear()
    assert _atualizar(tmp_path, rede, novo) == 0
    assert rede.pedidos == [novo["llama_server"]["alvos"]["ubuntu-x64"]["url"]]
    assert _nomes(_ferramentas(tmp_path) / "llama") == ["b2"]
    anotacao = ferramentas.ler_anotacao(tmp_path)
    assert (anotacao["build"], anotacao["modelo"]) == ("b2", "4b")


def test_atualizar_sem_mudanca_nao_pede_nada(tmp_path: Path, rede: Rede) -> None:
    """(guarda) controle: `test_atualizar_baixa_so_o_modelo_que_mudou` pede o que mudou."""
    manifesto = rede.manifesto()
    assert _baixar(tmp_path, rede, manifesto, "2b") == 0
    rede.pedidos.clear()
    assert _atualizar(tmp_path, rede, manifesto) == 0
    assert rede.pedidos == []


def test_trocar_de_modelo_apaga_o_outro(tmp_path: Path, rede: Rede) -> None:
    manifesto = rede.manifesto()
    assert _baixar(tmp_path, rede, manifesto, "2b") == 0
    assert _baixar(tmp_path, rede, manifesto, "4b") == 0
    modelos = _ferramentas(tmp_path) / "modelos"
    assert _nomes(modelos) == [manifesto["modelos"]["4b"]["arquivo"]]


def test_anotacao_torta_nao_apaga_fora_das_pastas(tmp_path: Path, rede: Rede) -> None:
    """(guarda) o nome velho da anotação só apaga dentro de `modelos/` e `llama/`; controle:
    `test_trocar_de_modelo_apaga_o_outro` e `test_atualizar_baixa_so_o_servidor_que_mudou`."""
    manifesto = rede.manifesto()
    assert _baixar(tmp_path, rede, manifesto, "2b") == 0
    fora = _ferramentas(tmp_path) / "fora.gguf"
    fora.write_bytes(b"da pessoa")
    (tmp_path / "fora").mkdir()
    anotacao = _ferramentas(tmp_path) / "ia_local.json"
    torta = ferramentas.ler_anotacao(tmp_path) | {"arquivo": "../fora.gguf", "build": "../../fora"}
    anotacao.write_text(json.dumps(torta), encoding="utf-8")
    assert _baixar(tmp_path, rede, manifesto, "4b") == 0
    assert fora.is_file() and fora.read_bytes() == b"da pessoa"
    assert (tmp_path / "fora").is_dir()


def test_programa_anotado_fora_de_llama_nao_roda(tmp_path: Path, rede: Rede) -> None:
    """(guarda) o `programa` da anotação só vale dentro de `llama/`; controle:
    `test_atualizar_sem_mudanca_nao_pede_nada` usa o anotado sem baixar de novo."""
    manifesto = rede.manifesto()
    assert _baixar(tmp_path, rede, manifesto, "2b") == 0
    (_ferramentas(tmp_path) / "outro").write_bytes(b"#!/bin/sh\n")
    anotacao = _ferramentas(tmp_path) / "ia_local.json"
    torta = ferramentas.ler_anotacao(tmp_path) | {"programa": "outro"}
    anotacao.write_text(json.dumps(torta), encoding="utf-8")
    versao = Versao(rede)
    assert _baixar(tmp_path, rede, manifesto, "2b", versao=versao) == 0
    llama = _ferramentas(tmp_path) / "llama"
    assert [programa.parent.parent.parent for programa, _ in versao.chamadas] == [llama]


def test_atualizar_sem_nada_baixado_e_modelo_ausente(
    tmp_path: Path, rede: Rede, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _atualizar(tmp_path, rede, rede.manifesto()) == 1
    assert rede.pedidos == []
    assert _linhas(capsys.readouterr().out) == [{"fim": "falhou", "motivo": "modelo_ausente"}]


def _banco(dados: Path, tarefas: dict[str, Any]) -> Path:
    caminho = dados / "jobot.db"
    with closing(abrir(caminho)) as con:
        migrar(con, caminho)
        gravar_config(con, "ia_tarefas", tarefas)
    return caminho


def test_remover_derruba_o_servidor_apaga_as_pastas_e_desliga_as_tarefas_no_local(
    tmp_path: Path, rede: Rede, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _baixar(tmp_path, rede, rede.manifesto(), "2b") == 0
    capsys.readouterr()
    local = {"ligada": True, "backend": "local", "modelo": "Qwen3.5-2B-Q4_K_M"}
    fora = {"ligada": True, "backend": "openai", "modelo": "gpt"}
    caminho = _banco(tmp_path, {"encaixe": local, "curriculo": fora})
    derrubadas: list[bool] = []

    def encerrar_sobra(dados: Path) -> None:
        assert dados == tmp_path
        derrubadas.append((_ferramentas(dados) / "llama").exists())  # antes de apagar

    assert ferramentas.remover_ia_local(tmp_path, encerrar_sobra=encerrar_sobra) == 0
    assert derrubadas == [True]
    assert _nomes(_ferramentas(tmp_path)) == []
    with closing(abrir(caminho)) as con:
        assert ler_config(con, "ia_tarefas") == {
            "encaixe": local | {"ligada": False},
            "curriculo": fora,
        }
    assert _linhas(capsys.readouterr().out) == [{"fim": "pronto"}]


def test_remover_sem_banco_nao_cria_o_banco(tmp_path: Path) -> None:
    """(guarda) controle: `test_remover_derruba_..._no_local` desliga com o banco presente."""
    assert ferramentas.remover_ia_local(tmp_path, encerrar_sobra=lambda dados: None) == 0
    assert not (tmp_path / "jobot.db").exists()


@pytest.mark.skipif(sys.platform == "win32", reason="`+x` e `sh` só no POSIX")
def test_o_mais_x_sobrevive_ao_preparar_pasta_e_o_llama_sobe_de_novo(
    tmp_path: Path, rede: Rede
) -> None:
    # o `--version` de verdade: o programa falso é um `sh` que só escreve a versão
    assert _baixar(tmp_path, rede, rede.manifesto(), "2b", versao=ferramentas.versao_roda) == 0
    preparar_pasta(tmp_path)  # o que o servidor do joBot faz ao subir
    anotacao = ferramentas.ler_anotacao(tmp_path)
    programa = _ferramentas(tmp_path) / anotacao["programa"]
    modelo = _ferramentas(tmp_path) / "modelos" / anotacao["arquivo"]
    servidor = ServidorLlamaFalso()
    lancador = LancadorFalso(servidor)

    def lancar(argv: list[str], env: dict[str, str]) -> Any:
        if not os.access(argv[0], os.X_OK):  # o que o `Popen` faria: PermissionError
            raise PermissionError(argv[0])
        return lancador(argv, env)

    relogio = RelogioSincrono()
    try:
        endereco, _ = Llama(
            tmp_path,
            programa,
            modelo,
            lancar=lancar,
            encerrar=lambda filho: None,
            porta_livre=lambda: servidor.porta,
            agora=relogio.agora,
            dormir=relogio.dormir,
            comando_de=lambda pid: "",
        ).subir()
    except FalhaLlama as falha:  # sem o `+x`: `programa_ausente`
        endereco = falha.motivo
    finally:
        servidor.fechar()
    assert endereco == f"http://127.0.0.1:{servidor.porta}/v1"
    assert lancador.subidas[0][0][:3] == [str(programa), "-m", str(modelo)]


def test_main_chega_no_ia_local(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JOBOT_DADOS", str(tmp_path))
    chamadas: list[tuple[str, Any]] = []

    def gravar(nome: str) -> Callable[..., int]:
        def chamada(dados: Path, *args: str) -> int:
            chamadas.append((nome, args[0] if args else dados))
            return 0

        return chamada

    monkeypatch.setattr(ferramentas, "baixar_ia_local", gravar("b"))
    monkeypatch.setattr(ferramentas, "atualizar_ia_local", gravar("a"))
    monkeypatch.setattr(ferramentas, "remover_ia_local", gravar("r"))
    assert jobot.cli.main(["ferramentas", "baixar", "ia-local", "--modelo", "4b"]) == 0
    assert jobot.cli.main(["ferramentas", "baixar", "ia-local"]) == 0
    assert jobot.cli.main(["ferramentas", "atualizar", "ia-local"]) == 0
    assert jobot.cli.main(["ferramentas", "remover", "ia-local"]) == 0
    assert chamadas == [("b", "4b"), ("b", "auto"), ("a", tmp_path), ("r", tmp_path)]
    assert jobot.cli.main(["ferramentas", "baixar", "ia-local", "--modelo", "9b"]) == 2
    assert jobot.cli.main(["ferramentas", "remover", "navegador"]) == 2


def test_remover_com_banco_estragado_e_falha_sem_traceback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("JOBOT_DADOS", str(tmp_path))
    (tmp_path / "jobot.db").write_bytes(b"isto nao e um banco" * 100)
    assert jobot.cli.main(["ferramentas", "remover", "ia-local"]) == 1
    assert _linhas(capsys.readouterr().out) == [{"fim": "falhou", "motivo": "arquivo"}]


@pytest.mark.skipif(sys.platform == "win32", reason="`sh` só no POSIX")
def test_versao_roda_pelo_codigo_de_saida(tmp_path: Path) -> None:
    for nome, codigo in (("bom", 0), ("ruim", 1)):
        (tmp_path / nome).write_text(f"#!/bin/sh\nexit {codigo}\n", encoding="utf-8")
        (tmp_path / nome).chmod(0o700)
    assert ferramentas.versao_roda(tmp_path / "bom") is True
    assert ferramentas.versao_roda(tmp_path / "ruim") is False
    assert ferramentas.versao_roda(tmp_path / "nao_existe") is False
