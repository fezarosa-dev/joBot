"""Checagem diária de versão nova no GitHub (plano T85; ADR 0014 e 0018; D31).

Nasce desligada: só roda com `aviso_versao_ligada` verdadeira, que a pessoa liga em Privacidade
(a T54 é dona do interruptor; aqui só se lê, com padrão `False`). O pedido passa pelo
`ClienteEducado` e leva só o user agent fixo (que traz a versão do joBot); o GitHub vê o IP, como em
qualquer pedido. A etiqueta da resposta é dado de terceiro que vai para a tela: só vale com até 32
caracteres e no formato `v?N.N.N` em ASCII, conferidos antes de qualquer `int()`.
"""

import logging
import re
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

from jobot import __version__
from jobot.banco.cadastros import gravar_config, ler_config
from jobot.banco.conexao import abrir
from jobot.nucleo.http import (
    Bloqueio,
    ClienteEducado,
    ErroDeRede,
    LimiteAtingido,
    OrcamentoGasto,
    Parou429,
    RespostaGrande,
)
from jobot.nucleo.relogio import Relogio

log = logging.getLogger(__name__)

URL_VERSOES = "https://api.github.com/repos/fezarosa-dev/joBot/releases/latest"
INTERVALO_S = 3600  # o laço acorda a cada hora; a checagem decide se já passou um dia
UM_DIA = timedelta(days=1)
_TAMANHO_MAX = 32  # antes do int(): acima de 4300 dígitos o int() levanta ValueError
# fullmatch: o `$` aceitaria a quebra de linha final; [0-9]: o `\d` aceita dígito fora do ASCII
_ETIQUETA = re.compile(r"v?[0-9]+\.[0-9]+\.[0-9]+")
# o servidor respondeu (ou o cliente recusou a resposta): a hora da checagem conta
_RESPOSTAS_RUINS = (
    Bloqueio,
    LimiteAtingido,
    Parou429,
    RespostaGrande,
    ValueError,  # JSON estragado
)


def versao_da_etiqueta(etiqueta: object) -> tuple[int, ...] | None:
    """`v1.2.3` ou `1.2.3` vira `(1, 2, 3)`; qualquer outra coisa, `None` (nunca levanta)."""
    if not isinstance(etiqueta, str) or len(etiqueta) > _TAMANHO_MAX:
        return None
    if _ETIQUETA.fullmatch(etiqueta) is None:
        return None
    return tuple(int(parte) for parte in etiqueta.removeprefix("v").split("."))


def _versao_atual() -> tuple[int, ...] | None:
    # `0.1.0.dev1` e afins: valem os três primeiros números
    achado = re.match(r"[0-9]{1,9}\.[0-9]{1,9}\.[0-9]{1,9}", __version__)
    return versao_da_etiqueta(achado.group(0)) if achado else None


def aviso_ligado(con: sqlite3.Connection) -> bool:
    """O aviso de versão está ligado; nasce desligado."""
    return ler_config(con, "aviso_versao_ligada", False) is True


def versao_para_avisar(con: sqlite3.Connection) -> str | None:
    """A etiqueta gravada, se o aviso está ligado e ela é maior que a versão instalada."""
    if not aviso_ligado(con):
        return None
    etiqueta = ler_config(con, "versao_nova", None)
    nova = versao_da_etiqueta(etiqueta)
    atual = _versao_atual()
    if nova is None or atual is None or nova <= atual:
        return None
    return str(etiqueta)


def _venceu(con: sqlite3.Connection, agora: datetime) -> bool:
    """Passou um dia da última checagem; sem checagem, data estragada ou no futuro (RF4): sim."""
    texto = ler_config(con, "versao_checada_em", None)
    try:
        checada = datetime.fromisoformat(texto) if isinstance(texto, str) else None
    except ValueError:
        checada = None
    if checada is None or checada.tzinfo is None:
        return True
    passou = agora - checada
    return passou < timedelta(0) or passou >= UM_DIA


async def checar_versao_nova(
    con: sqlite3.Connection, cliente: ClienteEducado, relogio: Relogio
) -> None:
    """Uma vez por dia, com o aviso ligado, pergunta ao GitHub a versão mais nova e a grava.

    Falha de rede ou resposta estranha só deixa a versão gravada como estava. A hora da checagem é
    gravada sempre que o servidor respondeu, mesmo com erro (um 404 sem release não pode virar
    um pedido por hora); só falha de transporte ou orçamento gasto, sem resposta, tenta de novo
    na próxima volta.
    """
    if not aviso_ligado(con):
        return
    agora = relogio.agora()
    if not _venceu(con, agora):
        return
    dados: object = None
    try:
        resposta = await cliente.escopo(condicional=False).pedir("GET", URL_VERSOES)
        dados = resposta.json()
    except ErroDeRede as erro:
        log.info("checagem de versão falhou: %s", erro)
        if erro.status is None:
            return
    except OrcamentoGasto as erro:
        log.info("checagem de versão falhou: %s", erro)
        return
    except _RESPOSTAS_RUINS as erro:
        log.info("checagem de versão falhou: %s", erro)
    etiqueta = dados.get("tag_name") if isinstance(dados, dict) else None
    if isinstance(etiqueta, str) and versao_da_etiqueta(etiqueta) is not None:
        gravar_config(con, "versao_nova", etiqueta)
    else:
        log.info("checagem de versão: sem etiqueta válida")
    gravar_config(con, "versao_checada_em", agora.astimezone(UTC).isoformat())


async def laco_versao(banco: Path, cliente: ClienteEducado, relogio: Relogio) -> None:
    """Acorda a cada hora e chama a checagem, com conexão própria fechada ao sair.

    Duas tarefas asyncio numa só conexão se cruzam nos `await` (o commit de uma fecha a
    transação da outra): por isso o laço abre a sua e nunca a divide.
    """
    with closing(abrir(banco)) as con:
        while True:
            try:
                await checar_versao_nova(con, cliente, relogio)
            except Exception:  # erro de uma volta não mata o laço; CancelledError passa
                log.exception("checagem de versão quebrou")
            await relogio.dormir(INTERVALO_S)
