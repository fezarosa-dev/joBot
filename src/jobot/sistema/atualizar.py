"""Comando `jobot atualizar`: puxa a versão nova e religa o que estava ligado (plano T85; D31).

Três canais de instalação: o clone do repositório (`git pull --ff-only` e `uv sync --locked`) e
o `uv tool install` (`uv tool upgrade jobot`), escolha do redator para confirmar (D31), e a casca
(`<dados>/instalacao.json`: venv novo ao lado, provado antes da troca; `casca.py`, T331, D174.3).
Qualquer outro é recusado com o jeito de atualizar à mão. Comandos sempre em lista, sem shell.
As migrações do banco rodam no próximo início do servidor.
"""

import os
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal

import httpx

import jobot
from jobot.nucleo.quebra import URL_REPOSITORIO
from jobot.sistema import casca
from jobot.sistema.abrir import sair_do_servidor, subir_servidor
from jobot.sistema.instancia import AVISO_CAPTURA, captura_em_andamento, pid_do_servidor
from jobot.sistema.segundo_plano_linux import (
    Recusa,
    Resultado,
    Rodar,
    desligar,
    ligar,
    sem_eco_no_terminal,
    status,
)

Tipo = Literal["casca", "clone_git", "uv_tool", "desconhecida"]

_TEMPO_S = 600  # git fetch e uv sync baixam coisas: 60 s do executor do segundo plano é pouco
_HASH = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
_A_MAO = (
    "Não sei como este joBot foi instalado, então não atualizo sozinho. Atualize à mão: "
    "no clone do repositório, rode `git pull --ff-only` e depois `uv sync --locked`; "
    "instalado com uv tool, rode `uv tool upgrade jobot`."
)


class _Recusa(Exception):
    """Motivo, para a pessoa, de não atualizar; nada foi tocado ainda."""


def tipo_de_instalacao(raiz: Path, dados: Path | None = None) -> Tipo:
    """`casca` (tem `<dados>/instalacao.json`), `clone_git` (tem `.git`, pasta ou arquivo de
    worktree, e `pyproject.toml`), `uv_tool` (tem o `uv-receipt.toml` que o `uv tool install`
    grava no ambiente) ou `desconhecida`."""
    if dados is not None and casca.tem_instalacao(dados):
        return "casca"
    if (raiz / ".git").exists() and (raiz / "pyproject.toml").is_file():
        return "clone_git"
    if (raiz / "uv-receipt.toml").is_file():
        return "uv_tool"
    return "desconhecida"


def raiz_da_instalacao() -> Path:
    """O clone (dois níveis acima de `src/jobot/`) ou, fora dele, o ambiente (`sys.prefix`)."""
    clone = Path(jobot.__file__).resolve().parent.parent.parent
    return clone if tipo_de_instalacao(clone) == "clone_git" else Path(sys.prefix)


def rodar_atualizacao(comando: Sequence[str]) -> Resultado:
    """Executor real: lista de argumentos, sem shell, sem terminal e sem git pedir senha."""
    try:
        feito = subprocess.run(
            list(comando),
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=_TEMPO_S,
            check=False,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except subprocess.TimeoutExpired:
        return Resultado(124)
    except OSError:  # programa que não existe ou não abre
        return Resultado(127)
    return Resultado(feito.returncode, feito.stdout, feito.stderr)


def _git(raiz: Path, *args: str) -> list[str]:
    return ["git", "-C", str(raiz), *args]


def _texto(feito: Resultado) -> str:
    return (feito.erro or feito.saida).strip()


def _motivo(recusa: Recusa) -> str:
    return str(recusa.motivo.params.get("saida") or recusa.motivo.chave)


def _commits_atras(rodar: Rodar, raiz: Path) -> int:
    """Quantos commits o clone está atrás do remoto; recusa mudança local e branch divergente."""
    mudancas = rodar(_git(raiz, "status", "--porcelain", "--untracked-files=no"))
    if mudancas.codigo != 0:
        raise _Recusa(f"Não consegui ler o estado do clone: {_texto(mudancas)}")
    if mudancas.saida.strip():
        raise _Recusa(
            "Há mudanças locais no clone do joBot. Guarde-as (git stash) ou desfaça-as "
            "antes de atualizar; nada foi mexido."
        )
    buscado = rodar(_git(raiz, "fetch", "--quiet"))
    if buscado.codigo != 0:
        raise _Recusa(f"Não consegui buscar a versão nova: {_texto(buscado)}")
    contagem = rodar(_git(raiz, "rev-list", "--left-right", "--count", "HEAD...@{upstream}"))
    partes = contagem.saida.split()
    if (
        contagem.codigo != 0
        or len(partes) != 2
        or not all(p.isascii() and p.isdigit() for p in partes)
    ):
        raise _Recusa("Não achei a branch remota deste clone; atualize à mão com git pull.")
    frente, atras = int(partes[0]), int(partes[1])
    if frente:
        raise _Recusa(
            "A branch local divergiu do remoto (tem commits que o remoto não tem). "
            "Resolva à mão antes de atualizar; nada foi mexido."
        )
    return atras


def _comandos(tipo: Tipo, raiz: Path) -> list[list[str]]:
    if tipo == "clone_git":
        return [
            _git(raiz, "pull", "--ff-only", "--quiet"),
            ["uv", "--directory", str(raiz), "sync", "--locked"],
        ]
    return [["uv", "tool", "upgrade", "jobot"]]


def _parar_e_atualizar(
    rodar: Rodar, dados: Path, comandos: list[list[str]], plano: bool, parar: Callable[[Path], int]
) -> bool:
    try:
        if plano:
            with sem_eco_no_terminal():
                desligar(rodar)  # o disable --now também para o servidor que o systemd subiu
        if pid_do_servidor(dados) is not None and parar(dados) != 0:
            print("O servidor não encerrou; nada foi atualizado.", file=sys.stderr)
            return False
    except Recusa as recusa:
        print(f"Não consegui parar o segundo plano: {_motivo(recusa)}", file=sys.stderr)
        return False
    except OSError as erro:
        print(f"Não consegui parar o joBot: {erro}", file=sys.stderr)
        return False
    for comando in comandos:
        feito = rodar(comando)
        if feito.codigo != 0:
            print(f"Falhou: {' '.join(comando)}: {_texto(feito)}", file=sys.stderr)
            return False
    return True


def _religar(
    rodar: Rodar,
    dados: Path,
    plano: bool,
    servidor: bool,
    subir: Callable[[], None],
    ligar_plano: Callable[[], None] | None = None,
) -> bool:
    try:
        if plano:
            with sem_eco_no_terminal():
                (ligar_plano or (lambda: ligar(rodar)))()  # o enable --now sobe o servidor
        elif servidor and pid_do_servidor(dados) is None:  # o que não caiu não sobe de novo
            subir()
    except Recusa as recusa:
        print(f"Não consegui religar o segundo plano: {_motivo(recusa)}", file=sys.stderr)
        return False
    except OSError as erro:
        print(f"Não consegui religar o joBot: {erro}", file=sys.stderr)
        return False
    return True


def _novidades(rodar: Rodar, raiz: Path, tipo: Tipo, antigo: str | None) -> None:
    """No clone, as linhas que o `git diff` acrescentou ao CHANGELOG; no uv tool, o link."""
    if tipo == "uv_tool":
        print(f"joBot atualizado. Veja as novidades em {URL_REPOSITORIO}/releases")
        return
    if antigo is None:  # sem o commit antigo não há como achar as linhas novas
        print("joBot atualizado.")
        return
    diferenca = rodar(
        _git(raiz, "diff", "--no-color", "--unified=0", antigo, "HEAD", "--", "CHANGELOG.md")
    )
    linhas = [
        linha[1:]
        for linha in diferenca.saida.splitlines()
        if linha.startswith("+") and not linha.startswith("+++")
    ]
    print("joBot atualizado.")
    if diferenca.codigo == 0 and any(linha.strip() for linha in linhas):
        print("Novidades no CHANGELOG:")
        for linha in linhas:
            print(linha)


def _ligar_pelo_novo(rodar: Rodar, jobot_novo: Path) -> None:
    """O serviço aponta para o executável do venv: quem o grava é o joBot novo (D174.9)."""
    feito = rodar([str(jobot_novo), "segundo-plano", "ligar"])
    if feito.codigo != 0:
        raise OSError(_texto(feito) or f"código {feito.codigo}")


def _atualizar_casca(
    rodar: Rodar,
    dados: Path,
    cliente: httpx.Client,
    parar: Callable[[Path], int],
    subir: Callable[[], None],
    subir_em: Callable[[Path], None],
) -> int:
    """Canal `casca` (desenho 6.3): monta e prova o venv novo antes de parar qualquer coisa."""
    try:
        instalacao = casca.ler_instalacao(dados)
        nova = casca.preparar(rodar, instalacao, cliente)
    except casca.Falha as falha:
        print(falha, file=sys.stderr)
        return 1
    if nova is None:
        print("O joBot já está na versão mais nova.")
        return 0
    plano = status(rodar).habilitado
    servidor = pid_do_servidor(dados) is not None
    trocada: dict[str, object] | None = None
    if _parar_e_atualizar(rodar, dados, [], plano, parar):
        try:
            trocada = casca.trocar(dados, instalacao, nova)
        except OSError as erro:
            print(f"Não consegui trocar a versão: {erro}. Nada mudou.", file=sys.stderr)
    if trocada is None:  # religa a versão de antes, que continua a do instalacao.json
        casca.descartar(nova)
        _religar(rodar, dados, plano, servidor, subir)
        return 1
    religado = _religar(
        rodar,
        dados,
        plano,
        servidor,
        lambda: subir_em(nova.python),
        lambda: _ligar_pelo_novo(rodar, nova.jobot),
    )
    casca.limpar(trocada)
    print(f"joBot atualizado para a versão {nova.versao}. Novidades em {URL_REPOSITORIO}/releases")
    if nova.navegador_desatualizado:
        print("O navegador não atualizou; baixe-o de novo em Configurações › Ferramentas.")
    return 0 if religado else 1


def _subir_em(python: Path) -> None:
    subir_servidor(str(python))


def atualizar(
    rodar: Rodar,
    dados: Path,
    *,
    parar: Callable[[Path], int] = sair_do_servidor,
    subir: Callable[[], None] = subir_servidor,
    subir_em: Callable[[Path], None] = _subir_em,
    cliente: httpx.Client | None = None,
    raiz: Path | None = None,
) -> int:
    """Atualiza o joBot; 0 se deu certo, 1 se recusou ou falhou (religando o que parou)."""
    if captura_em_andamento(dados):
        print(AVISO_CAPTURA, file=sys.stderr)
        return 1
    if casca.tem_instalacao(dados):
        if cliente is not None:
            return _atualizar_casca(rodar, dados, cliente, parar, subir, subir_em)
        with casca.cliente_de_download() as proprio:
            return _atualizar_casca(rodar, dados, proprio, parar, subir, subir_em)
    raiz = raiz or raiz_da_instalacao()
    tipo = tipo_de_instalacao(raiz)
    if tipo == "desconhecida":
        print(_A_MAO, file=sys.stderr)
        return 1
    antigo: str | None = None
    if tipo == "clone_git":
        try:
            if _commits_atras(rodar, raiz) == 0:
                print("O joBot já está na versão mais nova.")
                return 0
        except _Recusa as recusa:
            print(recusa, file=sys.stderr)
            return 1
        cabeca = rodar(_git(raiz, "rev-parse", "HEAD")).saida.strip()
        antigo = cabeca if _HASH.fullmatch(cabeca) else None  # vai como argumento do git diff
    # anota o que estava ligado antes de parar qualquer coisa
    plano = status(rodar).habilitado
    servidor = pid_do_servidor(dados) is not None
    atualizado = _parar_e_atualizar(rodar, dados, _comandos(tipo, raiz), plano, parar)
    religado = _religar(rodar, dados, plano, servidor, subir)
    if not atualizado or not religado:
        return 1
    _novidades(rodar, raiz, tipo, antigo)
    return 0
