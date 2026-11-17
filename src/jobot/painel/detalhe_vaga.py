"""O que o corpo do detalhe da vaga precisa, igual na página `/vagas/{id}` e ao lado da lista.

Mora fora de `rotas/` porque as duas rotas usam (T255): `rotas/detalhe.py` já importa de
`rotas/vagas.py`, e a volta faria um ciclo.
"""

import json
import sqlite3
from datetime import date
from typing import Any

from jobot.banco.leitura import Detalhe, abertura_da_candidatura, datas_dos_passos
from jobot.nucleo.candidatura import email_de_candidatura
from jobot.painel.consultas import utc_do_banco
from jobot.painel.moeda import exibicao_do_painel

_MESES = 12
_URGENTE_DIAS = 7  # prazo urgente: faltam menos de 7 dias (o selo "Fecha logo" vai até 7)


def _dia(texto: str | None) -> date | None:
    try:
        return date.fromisoformat(texto[:10]) if texto else None
    except ValueError:
        return None


def _faixa(vaga: Detalhe, hoje: date) -> dict[str, Any]:
    """Os doze meses a partir do mês de hoje, com as datas da vaga, e o texto equivalente.

    A grade é só desenho (`aria-hidden`): o texto traz o mesmo. Data fora dos doze meses fica só
    no texto.
    """
    publicada = utc_do_banco(vaga.publicada_em) if vaga.publicada_em else None
    talvez = {
        "publicada": None if publicada is None else publicada.astimezone().date(),
        "prazo": _dia(vaga.prazo),
        "inicio": _dia(vaga.inicio),
    }
    datas = {tipo: dia for tipo, dia in talvez.items() if dia is not None}
    textos = [
        {
            "tipo": tipo,
            "dia": dia.isoformat(),
            "faltam": (dia - hoje).days if tipo == "prazo" else None,
            "urgente": tipo == "prazo" and 0 <= (dia - hoje).days < _URGENTE_DIAS,
        }
        for tipo, dia in datas.items()
    ]
    primeiro = hoje.year * 12 + hoje.month - 1  # mês de hoje, contado desde o ano 0
    meses = []
    for i in range(_MESES):
        ano, resto = divmod(primeiro + i, 12)
        mes = resto + 1
        meses.append(
            {
                "mes": mes,
                "atual": (ano, mes) == (hoje.year, hoje.month),
                "marcas": [t for t, d in datas.items() if (d.year, d.month) == (ano, mes)],
            }
        )
    return {"datas": textos, "meses": meses}


def _estagio(vaga: Detalhe) -> dict[str, Any]:
    """Os requisitos do estágio que a vaga trouxe, sem os vazios."""
    bruto = json.loads(vaga.requisitos_estagio) if vaga.requisitos_estagio else {}
    return {chave: valor for chave, valor in bruto.items() if valor not in (None, "")}


def _http(url: str | None) -> bool:
    return url is not None and url.lower().startswith(("http://", "https://"))


def _passos(con: sqlite3.Connection, vaga: Detalhe) -> list[tuple[str, str]]:
    """A Linha do tempo (desenho 5.4): vista, a abertura da candidatura e cada passo com data."""
    passos = [("vista", vaga.primeira_vista_em)]
    abriu = abertura_da_candidatura(con, vaga.id)
    if abriu is not None:
        passos.append(("abriu", abriu))
    return passos + list(datas_dos_passos(con, vaga.id).items())


def contexto_do_detalhe(
    con: sqlite3.Connection, vaga: Detalhe, hoje: date, retorno: str
) -> dict[str, Any]:
    """As variáveis de `detalhe/corpo.html`; `retorno` é para onde Salvar e Ocultar voltam."""
    # uma fonte pode mostrar a vaga em mais de um escopo, com URLs diferentes: todos os links
    unicas: dict[tuple[str, str], Any] = {}
    for f in vaga.fontes:
        unicas.setdefault((f.fonte, f.url), f)
    site = next((f.url for f in vaga.fontes if _http(f.url)), None)
    candidatura = next((f.url_candidatura for f in vaga.fontes if _http(f.url_candidatura)), None)
    # o endereço não é guardado: sai da descrição na hora de mostrar (desenho 5.7)
    email = email_de_candidatura(vaga.descricao_texto)
    principal = "http" if candidatura else "email" if email else "fonte"
    return {
        "vaga": vaga,
        "exibicao": exibicao_do_painel(con, hoje),
        "fontes": list(unicas.values()),
        # sem link próprio de candidatura, o botão abre a vaga na fonte
        "candidatura": candidatura or site,
        "site": site,
        "faixa": _faixa(vaga, hoje),
        "estagio": _estagio(vaga),
        "retorno": retorno,
        "http": _http,
        "passos": _passos(con, vaga),
        "email": email,
        # o botão principal: link próprio de candidatura, senão o e-mail, senão a vaga na fonte
        "principal": principal,
    }
