"""`sistema/llama.py`: subida do `llama-server` com lançador injetado e o falso em thread em
`127.0.0.1` (T408; desenho 7; D194). Sem processo de verdade, sem rede, sem tempo real."""

import contextlib
import json
import os
import socket
import sys
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from apoio.llama_falso import FilhoFalso, LancadorFalso, RelogioSincrono, ServidorLlamaFalso
from jobot.sistema import llama
from jobot.sistema.llama import FalhaLlama, Llama


@pytest.fixture
def servidor() -> Iterator[ServidorLlamaFalso]:
    s = ServidorLlamaFalso()
    yield s
    s.fechar()


class Montagem:
    def __init__(self, dados: Path, servidor: ServidorLlamaFalso, **lancador: int | None) -> None:
        self.dados = dados
        self.programa = dados / "ferramentas" / "llama" / "b12359" / "llama-server"
        self.modelo = dados / "ferramentas" / "modelos" / "Qwen3.5-2B-Q4_K_M.gguf"
        self.servidor = servidor
        self.lancador = LancadorFalso(servidor, **lancador)
        self.relogio = RelogioSincrono()
        self.ordem: list[str] = []
        self.encerrados: list[FilhoFalso] = []
        self.sobras: list[int] = []
        self.comando = ""
        self.erro_ao_lancar: OSError | None = None

    def _lancar(self, argv: list[str], env: dict[str, str]) -> FilhoFalso:
        self.ordem.append("lancar")
        if self.erro_ao_lancar is not None:
            raise self.erro_ao_lancar
        return self.lancador(argv, env)

    def _encerrar(self, filho: llama.Filho) -> None:
        assert isinstance(filho, FilhoFalso)
        self.encerrados.append(filho)

    def _encerrar_pid(self, pid: int) -> None:
        self.ordem.append(f"sobra {pid}")
        self.sobras.append(pid)

    def llama(self) -> Llama:
        return Llama(
            self.dados,
            self.programa,
            self.modelo,
            lancar=self._lancar,
            encerrar=self._encerrar,
            porta_livre=lambda: self.servidor.porta,
            agora=self.relogio.agora,
            dormir=self.relogio.dormir,
            comando_de=lambda pid: self.comando,
            encerrar_pid=self._encerrar_pid,
        )

    @property
    def registro(self) -> Path:
        return self.dados / "ferramentas" / "llama.json"


def test_argv_tem_as_opcoes_do_desenho() -> None:
    assert llama.argv_do_servidor(Path("/f/llama-server"), Path("/m/q.gguf"), 5123) == [
        "/f/llama-server",
        "-m",
        "/m/q.gguf",
        "--host",
        "127.0.0.1",
        "--port",
        "5123",
        "-c",
        "8192",
        "-np",
        "1",
        "-ngl",
        "0",
        "--no-webui",
        "--no-slots",
        "--reasoning",
        "off",
        "--sleep-idle-seconds",
        "600",
    ]


def test_espera_a_saude_e_devolve_endereco_e_chave(
    tmp_path: Path, servidor: ServidorLlamaFalso
) -> None:
    servidor.saude = [503, 503, 200]
    m = Montagem(tmp_path, servidor)
    endereco, chave = m.llama().subir()
    assert endereco == f"http://127.0.0.1:{servidor.porta}/v1"
    assert servidor.caminhos == ["/health"] * 3
    assert m.relogio.t == 2 * llama.SONO_S
    argv, env = m.lancador.subidas[0]
    assert argv == llama.argv_do_servidor(m.programa, m.modelo, servidor.porta)
    assert env["LLAMA_API_KEY"] == chave
    assert len(chave) >= 32


def test_chave_nunca_no_argv(tmp_path: Path, servidor: ServidorLlamaFalso) -> None:
    # guarda (D194.1): `ps` mostra o argv a todos; o ambiente, só ao dono do processo
    m = Montagem(tmp_path, servidor)
    endereco, chave = m.llama().subir()
    assert len(m.lancador.subidas) == 1
    argv = m.lancador.subidas[0][0]
    assert not any(chave in a for a in argv)
    # controle: a chave chega ao falso pelo ambiente e abre a API; sem ela, 401
    auth = {"Authorization": f"Bearer {chave}"}
    with httpx.Client(trust_env=False) as c:
        assert c.get(f"{endereco}/models", headers=auth).status_code == 200
        assert c.get(f"{endereco}/models").status_code == 401


def test_ambiente_tira_as_variaveis_llama_da_pessoa() -> None:
    base = {"PATH": "/usr/bin", "LLAMA_ARG_HOST": "0.0.0.0", "LLAMA_API_KEY": "velha"}
    base["llama_arg_api_key_file"] = "/tmp/outra"
    assert llama.ambiente("nova", base) == {"PATH": "/usr/bin", "LLAMA_API_KEY": "nova"}


def test_reusa_a_instancia_viva(tmp_path: Path, servidor: ServidorLlamaFalso) -> None:
    m = Montagem(tmp_path, servidor)
    instancia = m.llama()
    primeira = instancia.subir()
    assert instancia.subir() == primeira
    assert len(m.lancador.subidas) == 1
    # controle: o filho morreu, a próxima chamada sobe outro, com chave nova
    m.lancador.filhos[0].returncode = 1
    assert instancia.subir()[1] != primeira[1]
    assert len(m.lancador.subidas) == 2


def test_filho_morto_antes_da_porta_e_programa_ausente_sem_pedido(
    tmp_path: Path, servidor: ServidorLlamaFalso
) -> None:
    m = Montagem(tmp_path, servidor, vivo_por=0)
    with pytest.raises(FalhaLlama) as erro:
        m.llama().subir()
    assert erro.value.motivo == "programa_ausente"
    assert servidor.caminhos == []
    assert m.encerrados == m.lancador.filhos
    assert not m.registro.exists()


def test_porta_tomada_no_meio_e_programa_ausente(
    tmp_path: Path, servidor: ServidorLlamaFalso
) -> None:
    # o filho morre depois do primeiro /health: o 200 veio de outro processo na porta
    m = Montagem(tmp_path, servidor, vivo_por=1)
    with pytest.raises(FalhaLlama) as erro:
        m.llama().subir()
    assert erro.value.motivo == "programa_ausente"
    assert servidor.caminhos == ["/health"]


def test_programa_que_nao_abre_e_programa_ausente(
    tmp_path: Path, servidor: ServidorLlamaFalso
) -> None:
    m = Montagem(tmp_path, servidor)
    m.erro_ao_lancar = FileNotFoundError(str(m.programa))
    with pytest.raises(FalhaLlama) as erro:
        m.llama().subir()
    assert erro.value.motivo == "programa_ausente"
    assert servidor.caminhos == []
    assert not m.registro.exists()


def test_120_s_sem_saude_e_tempo_esgotado_e_encerra_a_arvore(
    tmp_path: Path, servidor: ServidorLlamaFalso
) -> None:
    servidor.saude = [503]
    m = Montagem(tmp_path, servidor)
    with pytest.raises(FalhaLlama) as erro:
        m.llama().subir()
    assert erro.value.motivo == "tempo_esgotado"
    assert m.relogio.t == llama.ESPERA_S == 120.0
    assert m.encerrados == m.lancador.filhos
    assert not m.registro.exists()


def test_grava_pid_porta_e_programa_em_llama_json(
    tmp_path: Path, servidor: ServidorLlamaFalso
) -> None:
    m = Montagem(tmp_path, servidor)
    m.llama().subir()
    assert m.registro.exists()
    assert json.loads(m.registro.read_text(encoding="utf-8")) == {
        "pid": m.lancador.filhos[0].pid,
        "porta": servidor.porta,
        "programa": str(m.programa),
    }
    if sys.platform != "win32":
        assert m.registro.stat().st_mode & 0o777 == 0o600


def test_encerrar_derruba_a_instancia_e_apaga_o_registro(
    tmp_path: Path, servidor: ServidorLlamaFalso
) -> None:
    m = Montagem(tmp_path, servidor)
    instancia = m.llama()
    instancia.subir()
    instancia.encerrar()
    assert m.encerrados == m.lancador.filhos
    assert not m.registro.exists()
    instancia.subir()
    assert len(m.lancador.subidas) == 2


def _sobra(m: Montagem) -> None:
    m.registro.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps({"pid": 777, "porta": 5555, "programa": str(m.programa)})
    m.registro.write_text(texto, encoding="utf-8")


def test_subida_seguinte_encerra_a_sobra(tmp_path: Path, servidor: ServidorLlamaFalso) -> None:
    m = Montagem(tmp_path, servidor)
    _sobra(m)
    m.comando = f"{m.programa} -m /m/q.gguf --host 127.0.0.1 --port 5555 -c 8192\n"
    m.llama().subir()
    assert m.ordem == ["sobra 777", "lancar"]
    assert json.loads(m.registro.read_text(encoding="utf-8"))["pid"] != 777


@pytest.mark.parametrize(
    "comando",
    [
        "",  # o PID não existe mais
        "/usr/bin/bash\n",  # o PID voltou para outro programa
        "/f/outro/llama-server --port 5555\n",  # outro llama-server
        "{programa} --port 55551\n",  # o mesmo programa noutra porta
        "/usr/bin/gdb --args {programa} --port 5555\n",  # o programa não é o comando
    ],
)
def test_sobra_de_outro_processo_nao_e_encerrada(
    tmp_path: Path, servidor: ServidorLlamaFalso, comando: str
) -> None:
    # guarda: o controle é `test_subida_seguinte_encerra_a_sobra`, com a mesma montagem
    m = Montagem(tmp_path, servidor)
    _sobra(m)
    m.comando = comando.format(programa=m.programa)
    m.llama().subir()
    assert m.sobras == []
    assert json.loads(m.registro.read_text(encoding="utf-8"))["pid"] != 777


def test_registro_estragado_e_ignorado(tmp_path: Path, servidor: ServidorLlamaFalso) -> None:
    m = Montagem(tmp_path, servidor)
    m.registro.parent.mkdir(parents=True)
    m.registro.write_text("{pid", encoding="utf-8")
    m.llama().subir()
    assert m.sobras == []
    assert m.registro.read_text(encoding="utf-8") != "{pid"
    assert json.loads(m.registro.read_text(encoding="utf-8"))["porta"] == servidor.porta


def test_e_o_nosso_no_windows_pelo_nome_da_imagem() -> None:
    programa = Path("C:/d/ferramentas/llama/b12359/llama-server.exe")
    linha = '"llama-server.exe","777","Console","1","812.300 K"\r\n'
    assert llama.e_o_nosso(linha, programa, 5555, "win32")
    assert not llama.e_o_nosso("INFO: No tasks are running.\r\n", programa, 5555, "win32")
    assert not llama.e_o_nosso('"cmd.exe","777","Console","1","1 K"', programa, 5555, "win32")
    outro = '"x-llama-server.exe","777","Console","1","1 K"'
    assert not llama.e_o_nosso(outro, programa, 5555, "win32")


def test_porta_livre_e_de_127_0_0_1() -> None:
    p = llama.porta_livre()
    assert 1024 <= p <= 65535
    with socket.socket() as s:
        s.bind(("127.0.0.1", p))  # estava livre de verdade


@pytest.mark.skipif(sys.platform == "win32", reason="ps só no POSIX")
def test_comando_de_le_o_argv_do_processo() -> None:
    assert "pytest" in llama.comando_de(os.getpid())


def test_saude_nao_passa_pelo_proxy_do_ambiente(
    tmp_path: Path, servidor: ServidorLlamaFalso, monkeypatch: pytest.MonkeyPatch
) -> None:
    # guarda: com `trust_env`, o `/health` iria ao proxy fechado e daria `tempo_esgotado`
    for nome in ("HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.setenv(nome, "http://127.0.0.1:9")
    for nome in ("NO_PROXY", "no_proxy"):
        monkeypatch.delenv(nome, raising=False)
    m = Montagem(tmp_path, servidor)
    subiu = None
    with contextlib.suppress(FalhaLlama):
        subiu = m.llama().subir()
    assert subiu is not None and subiu[0] == f"http://127.0.0.1:{servidor.porta}/v1"
    assert servidor.caminhos == ["/health"]
