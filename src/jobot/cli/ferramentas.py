"""Comandos `jobot ferramentas`: o navegador (T330; desenho 6.2; D174.2 e D183.24) e o modelo
local (T409; desenho 7; D195).

O joBot não redistribui o navegador (o Playwright baixa o Google Chrome for Testing, D183.24):
em todo canal, a casca inclusive, é o `playwright install --no-shell chromium` de sempre
(`baixar_chromium`), da versão do Playwright do venv. O stdout leva linhas JSON que a casca lê:
`{"etapa":"navegador","feito":0}` no começo (sem `total`: o Playwright não diz o tamanho) e
`{"fim":"pronto"}` ou `{"fim":"falhou"}` no fim.

O `playwright install` vive em sessão própria (`abrir_instalador`): o sinal de quem chama (a casca
cancelando, o `jobot atualizar` no prazo) não chega a ele. No POSIX o SIGTERM cancela o download e
encerra o grupo dele antes de sair; no Windows quem chama mata a árvore (`taskkill /T`).

Modelo local: `baixar ia-local [--modelo auto|2b|4b]` baixa da fonte oficial o `llama-server` do
`nucleo/dados/ia_local.json` para este computador, roda `llama-server --version` e só então baixa
o modelo (falha em 23 MB, não em 2,7 GB). `auto` escolhe pela memória, com os cortes do `ia.json`,
e escreve antes de tudo `{"memoria": <bytes>, "modelo": "2b"|"4b", "lento": <bool>}`. O que baixou
fica anotado em `<dados>/ferramentas/ia_local.json`; `atualizar ia-local` baixa só o que mudou no
manifesto, com o mesmo modelo; os dois derrubam o `llama-server` antes de trocar ou apagar o
anterior (D195.6); `remover ia-local` desliga as tarefas no backend `local`, derruba o
`llama-server` e apaga `llama/`, `modelos/` e a anotação. Linhas JSON como as do navegador:
`{"etapa":"ia_local","feito":N,"total":T}` por arquivo e `{"fim":"pronto"}` ou
`{"fim":"falhou","motivo":...}`, com os motivos de `baixar.Motivo` mais `programa_ausente` e
`modelo_ausente` (os nomes do contrato da IA). SIGTERM no meio mata o processo e o `.parcial` fica
para a retomada.
"""

import argparse
import asyncio
import errno
import json
import logging
import os
import platform
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from contextlib import closing
from functools import partial
from importlib import resources
from pathlib import Path
from typing import Any

import httpx

from jobot.banco import conexao
from jobot.banco.cadastros import gravar_config, ler_config
from jobot.navegador.instalador import Resultado, abrir_instalador, baixar_chromium
from jobot.navegador.janela_comum import AbrirJanela
from jobot.nucleo.ia.contrato import limites
from jobot.sistema import llama, processo
from jobot.sistema.baixar import (
    FalhaBaixar,
    baixar,
    cliente_de_download,
    extrair,
    tornar_executavel,
)
from jobot.sistema.casca import gravar_atomico
from jobot.sistema.memoria import escolher_modelo, memoria_total
from jobot.sistema.pastas import PASTA_FERRAMENTAS, configurar_log, pasta_de_dados, preparar_pasta

_LOG = logging.getLogger(__name__)

# (sys.platform, platform.machine() em minúsculas) -> alvo do manifesto (D193.1)
_ALVOS = {
    ("linux", "x86_64"): "ubuntu-x64",
    ("win32", "amd64"): "win-cpu-x64",
    ("darwin", "arm64"): "macos-arm64",
    ("darwin", "x86_64"): "macos-x64",
}
ANOTACAO = "ia_local.json"
BACKEND_LOCAL = "local"  # o nome do backend em `esquema_para` e em `ia_tarefas`
VERSAO_S = 30.0  # prazo do `llama-server --version`
# pausas entre as tentativas de apagar: no Windows, o `llama-server` recém-derrubado pelo
# `taskkill /F` ainda prende o `.exe` e o GGUF por um instante (D195.6 e D195.8)
FOLGA = (0.5, 1.0, 2.0)


def _escrever(linha: dict[str, object]) -> None:
    print(json.dumps(linha), flush=True)


async def _baixar(abrir: AbrirJanela) -> Resultado:
    tarefa = asyncio.current_task()
    if tarefa is not None and sys.platform != "win32":
        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, tarefa.cancel)
    try:
        return await baixar_chromium(abrir)  # cancelado, encerra o grupo do `playwright install`
    except asyncio.CancelledError:
        return "falhou"


def baixar_navegador(args: argparse.Namespace, *, abrir: AbrirJanela = abrir_instalador) -> int:
    _escrever({"etapa": "navegador", "feito": 0})
    pronto = asyncio.run(_baixar(abrir)) == "pronto"
    _escrever({"fim": "pronto" if pronto else "falhou"})
    return 0 if pronto else 1


class _Falhou(Exception):
    def __init__(self, motivo: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo


def alvo_daqui(plataforma: str = sys.platform, maquina: str | None = None) -> str | None:
    """O alvo do manifesto deste computador; `None` sem binário oficial (Linux ARM, por exemplo)."""
    maquina = platform.machine() if maquina is None else maquina
    return _ALVOS.get((plataforma, maquina.lower()))


ALVO = alvo_daqui()


def manifesto_local() -> dict[str, Any]:
    """`nucleo/dados/ia_local.json` (T407; D193)."""
    arquivo = resources.files("jobot.nucleo").joinpath("dados", "ia_local.json")
    dados: dict[str, Any] = json.loads(arquivo.read_text(encoding="utf-8"))
    return dados


def ler_anotacao(dados: Path) -> dict[str, Any]:
    """O que está baixado (`<dados>/ferramentas/ia_local.json`); sem arquivo ou estragado: `{}`."""
    try:
        anotacao = json.loads((dados / PASTA_FERRAMENTAS / ANOTACAO).read_text(encoding="utf-8"))
    except OSError, ValueError:
        return {}
    return anotacao if isinstance(anotacao, dict) else {}


def versao_roda(programa: Path) -> bool:
    """`llama-server --version` sai com 0: o binário e as bibliotecas dele rodam aqui."""
    try:
        feito = subprocess.run(
            [str(programa), "--version"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=VERSAO_S,
            check=False,
            **processo.SEM_JANELA,  # do `pythonw` (painel, casca), sem console que pisca
        )
    except OSError, subprocess.TimeoutExpired:
        return False
    return feito.returncode == 0


def _linha(linha: str) -> None:
    print(linha, flush=True)


def baixar_ia_local(
    dados: Path,
    escolha: str = "auto",
    *,
    manifesto: Mapping[str, Any] | None = None,
    cliente: httpx.Client | None = None,
    versao: Callable[[Path], bool] = versao_roda,
    memoria: Callable[[], int] = memoria_total,
    alvo: str | None = ALVO,
    encerrar_sobra: Callable[[Path], None] = llama.encerrar_sobra,
    dormir: Callable[[float], None] = time.sleep,
) -> int:
    """`jobot ferramentas baixar ia-local`: 0 pronto, 1 falhou (a linha `fim` diz o motivo)."""
    modelo = escolha
    if escolha == "auto":
        try:
            total = memoria()
        except OSError:  # `GlobalMemoryStatusEx` que falha: a casca ainda lê a linha `fim`
            _LOG.exception("a memória não foi lida")
            _escrever({"fim": "falhou", "motivo": "arquivo"})
            return 1
        cortes = limites()["memoria_gib"]
        modelo, lento = escolher_modelo(
            total, desde_4b_gib=cortes["modelo_4b_desde"], aviso_gib=cortes["aviso_lento_abaixo"]
        )
        _escrever({"memoria": total, "modelo": modelo, "lento": lento})
    return _instalar(dados, modelo, manifesto, cliente, versao, alvo, encerrar_sobra, dormir)


def atualizar_ia_local(
    dados: Path,
    *,
    manifesto: Mapping[str, Any] | None = None,
    cliente: httpx.Client | None = None,
    versao: Callable[[Path], bool] = versao_roda,
    alvo: str | None = ALVO,
    encerrar_sobra: Callable[[Path], None] = llama.encerrar_sobra,
    dormir: Callable[[float], None] = time.sleep,
) -> int:
    """Baixa o que mudou no manifesto, com o modelo anotado; nada baixado: `modelo_ausente`."""
    modelo = ler_anotacao(dados).get("modelo")
    if not isinstance(modelo, str) or not modelo:
        _escrever({"fim": "falhou", "motivo": "modelo_ausente"})
        return 1
    return _instalar(dados, modelo, manifesto, cliente, versao, alvo, encerrar_sobra, dormir)


def _instalar(
    dados: Path,
    modelo: str,
    manifesto: Mapping[str, Any] | None,
    cliente: httpx.Client | None,
    versao: Callable[[Path], bool],
    alvo: str | None,
    encerrar_sobra: Callable[[Path], None],
    dormir: Callable[[float], None],
) -> int:
    manifesto = manifesto_local() if manifesto is None else manifesto
    proprio = cliente is None
    cliente = cliente_de_download() if cliente is None else cliente
    derrubar = partial(encerrar_sobra, dados)
    try:
        _servidor_e_modelo(
            dados / PASTA_FERRAMENTAS, modelo, manifesto, cliente, versao, alvo, derrubar, dormir
        )
    except (_Falhou, FalhaBaixar) as falha:
        _escrever({"fim": "falhou", "motivo": falha.motivo})
        return 1
    except OSError as erro:  # pasta sem permissão, disco cheio na extração ou na anotação
        _LOG.exception("o modelo local não foi baixado")
        motivo = "espaco" if erro.errno == errno.ENOSPC else "arquivo"
        _escrever({"fim": "falhou", "motivo": motivo})
        return 1
    finally:
        if proprio:
            cliente.close()
    _escrever({"fim": "pronto"})
    return 0


def _servidor_e_modelo(
    ferramentas: Path,
    modelo: str,
    manifesto: Mapping[str, Any],
    cliente: httpx.Client,
    versao: Callable[[Path], bool],
    alvo: str | None,
    derrubar: Callable[[], None],
    dormir: Callable[[float], None],
) -> None:
    """`derrubar` (o `llama.encerrar_sobra`) vem antes de cada troca ou apagamento: o
    `llama-server` que o servidor do joBot subiu não fica servindo o velho, e no Windows solta o
    `.exe` e o GGUF (D195.6)."""
    servidor = manifesto["llama_server"]
    item = servidor["alvos"].get(alvo) if alvo else None
    escolhido = manifesto["modelos"].get(modelo)
    if item is None:
        raise _Falhou("programa_ausente")
    if escolhido is None:
        raise _Falhou("modelo_ausente")
    anotado = ler_anotacao(ferramentas.parent)
    build, pasta_llama = servidor["build"], ferramentas / "llama"
    programa = None
    if anotado.get("build") == build and anotado.get("servidor_sha256") == item["sha256"]:
        programa = _dentro(ferramentas, pasta_llama, anotado.get("programa"))
    if programa is None or not programa.is_file():
        if (pasta_llama / build).exists():
            derrubar()  # a pasta do mesmo build vai ser trocada
        programa = _baixar_servidor(pasta_llama, build, item, alvo or "", cliente)
    if not versao(programa):  # antes do modelo: falha em 23 MB, não em 2,7 GB
        raise _Falhou("programa_ausente")
    anotacao = {k: v for k, v in anotado.items() if k in ("modelo", "arquivo", "modelo_sha256")}
    anotacao |= {
        "build": build,
        "alvo": alvo,
        "programa": programa.relative_to(ferramentas).as_posix(),
        "servidor_sha256": item["sha256"],
    }
    _anotar(ferramentas, anotacao)
    if anotado.get("build") != build:
        derrubar()
        _apagar(pasta_llama, anotado.get("build"), dormir)

    destino = ferramentas / "modelos" / escolhido["arquivo"]
    if anotado.get("modelo_sha256") != escolhido["sha256"] or not destino.is_file():
        if destino.exists():
            derrubar()  # o `os.replace` do `baixar` troca o GGUF de mesmo nome
        baixar(
            escolhido["url"],
            destino,
            tamanho=escolhido["tamanho"],
            sha256=escolhido["sha256"],
            cliente=cliente,
            progresso=_linha,
        )
    anotacao |= {
        "modelo": modelo,
        "arquivo": escolhido["arquivo"],
        "modelo_sha256": escolhido["sha256"],
    }
    _anotar(ferramentas, anotacao)
    if anotado.get("arquivo") != escolhido["arquivo"]:
        derrubar()
        _apagar(ferramentas / "modelos", anotado.get("arquivo"), dormir)


def _baixar_servidor(
    pasta_llama: Path, build: str, item: Mapping[str, Any], alvo: str, cliente: httpx.Client
) -> Path:
    """Baixa o pacote, extrai numa pasta nova (apagada na falha, D189.7), dá o `+x` ao
    `llama-server` e troca a pasta do build; o pacote some no fim. Devolve o programa."""
    pacote = pasta_llama / item["arquivo"]
    baixar(
        item["url"],
        pacote,
        tamanho=item["tamanho"],
        sha256=item["sha256"],
        cliente=cliente,
        progresso=_linha,
    )
    nova, pronta = pasta_llama / f"{build}.novo", pasta_llama / build
    nome = "llama-server.exe" if alvo.startswith("win") else "llama-server"
    shutil.rmtree(nova, ignore_errors=True)  # sobra de uma extração interrompida
    try:
        extrair(pacote, nova)
        # o caminho dentro do pacote não é fixado: vale o único arquivo com o nome do programa
        achados = sorted(p for p in nova.rglob(nome) if p.is_file() and not p.is_symlink())
        if not achados:
            raise _Falhou("programa_ausente")
        tornar_executavel(achados[0])
        relativo = achados[0].relative_to(nova)
        shutil.rmtree(pronta, ignore_errors=True)
        nova.rename(pronta)
    except BaseException:
        shutil.rmtree(nova, ignore_errors=True)
        raise
    finally:
        pacote.unlink(missing_ok=True)
    return pronta / relativo


def _dentro(ferramentas: Path, pasta: Path, relativo: object) -> Path | None:
    """O caminho anotado, só se estiver dentro de `pasta`."""
    if not isinstance(relativo, str) or not relativo:
        return None
    caminho = ferramentas / relativo
    return caminho if caminho.resolve().is_relative_to(pasta.resolve()) else None


def _apagar(pasta: Path, nome: object, dormir: Callable[[float], None]) -> None:
    """Apaga o anterior `pasta/nome` (arquivo ou pasta) só se `nome` for um nome só, sem barra
    nem `..`. Se não sair, fica (com o aviso no log): o novo já está anotado."""
    if not isinstance(nome, str) or nome in ("", ".", "..") or Path(nome).name != nome:
        return
    alvo = pasta / nome
    try:
        if alvo.is_dir() and not alvo.is_symlink():
            _com_folga(lambda: shutil.rmtree(alvo), dormir)
        else:
            _com_folga(lambda: alvo.unlink(missing_ok=True), dormir)
    except OSError:
        _LOG.warning("o anterior %s ficou", alvo, exc_info=True)


def _com_folga(apagar: Callable[[], None], dormir: Callable[[float], None]) -> None:
    """`apagar`, de novo depois de cada pausa de `FOLGA` enquanto der `PermissionError`."""
    for pausa in FOLGA:
        try:
            apagar()
        except PermissionError:
            dormir(pausa)
        else:
            return
    apagar()


def _anotar(ferramentas: Path, anotacao: Mapping[str, Any]) -> None:
    gravar_atomico(ferramentas / ANOTACAO, json.dumps(anotacao, indent=2).encode())


def remover_ia_local(
    dados: Path,
    *,
    encerrar_sobra: Callable[[Path], None] = llama.encerrar_sobra,
    dormir: Callable[[float], None] = time.sleep,
) -> int:
    """Desliga as tarefas no `local`, derruba o `llama-server` e apaga `llama/`, `modelos/` e a
    anotação. Banco ausente não é criado."""
    ferramentas = dados / PASTA_FERRAMENTAS
    try:
        _desligar_local(dados / "jobot.db")
        encerrar_sobra(dados)
        for nome in ("llama", "modelos"):
            pasta = ferramentas / nome
            if pasta.exists():
                _com_folga(partial(shutil.rmtree, pasta), dormir)
        (ferramentas / ANOTACAO).unlink(missing_ok=True)
    except OSError, sqlite3.Error:
        _LOG.exception("o modelo local não foi removido")
        _escrever({"fim": "falhou", "motivo": "arquivo"})
        return 1
    _escrever({"fim": "pronto"})
    return 0


def _desligar_local(banco: Path) -> None:
    if not banco.exists():
        return
    with closing(conexao.abrir(banco)) as con:
        tarefas = ler_config(con, "ia_tarefas")
        if not isinstance(tarefas, dict):
            return
        locais = [
            t for t in tarefas.values() if isinstance(t, dict) and t.get("backend") == BACKEND_LOCAL
        ]
        for tarefa in locais:
            tarefa["ligada"] = False
        if locais:
            gravar_config(con, "ia_tarefas", tarefas)


def executar(args: argparse.Namespace) -> int:
    if args.ferramenta == "navegador":
        if args.acao != "baixar":
            print("jobot: o navegador só tem `baixar`.", file=sys.stderr)
            return 2
        configurar_log(pasta_de_dados(os.environ))
        return baixar_navegador(args)
    os.umask(0o077)  # como `preparar_dados` do `serve`: o que nasce aqui é 0600
    dados = pasta_de_dados(os.environ)
    configurar_log(dados)
    preparar_pasta(dados)
    if args.acao == "baixar":
        return baixar_ia_local(dados, args.modelo)
    if args.acao == "atualizar":
        return atualizar_ia_local(dados)
    return remover_ia_local(dados)
