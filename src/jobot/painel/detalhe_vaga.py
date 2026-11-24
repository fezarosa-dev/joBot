"""O que o corpo do detalhe da vaga precisa, igual na página `/vagas/{id}` e ao lado da lista.

Mora fora de `rotas/` porque as duas rotas usam (T255): `rotas/detalhe.py` já importa de
`rotas/vagas.py`, e a volta faria um ciclo.
"""

import json
import sqlite3
from collections.abc import MutableMapping
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Literal

from fastapi import Request

from jobot.banco import perfil
from jobot.banco.ia import Preparo, gravar_preparo, pedes, preparo, tarefa_ia
from jobot.banco.leitura import Detalhe, abertura_da_candidatura, datas_dos_passos
from jobot.banco.perfil import habilidades
from jobot.nucleo.candidatura import email_de_candidatura
from jobot.nucleo.encaixe import casar
from jobot.nucleo.ia import manual
from jobot.nucleo.ia.contrato import Motivo, Pedido, Resposta
from jobot.nucleo.ia.pedidos import dados_para, pedido_candidatura, texto_encaixe
from jobot.nucleo.ia.tarefas import citados, conferir_candidatura
from jobot.nucleo.texto import normalizar
from jobot.painel.consultas import utc_do_banco
from jobot.painel.moeda import exibicao_do_painel
from jobot.painel.rotas.perfil import frase_de_privacidade

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


def _habilidades(con: sqlite3.Connection, vaga: Detalhe) -> dict[str, Any] | None:
    """O que a vaga pede segundo a IA, inteiro, separado pelo perfil (desenho 5.5); sem, `None`.

    O corte é o do texto de hoje da vaga, o mesmo `texto_encaixe` que o laço manda (T412).
    """
    achado = pedes(con, vaga.id).get(vaga.id)
    if achado is None or not achado.pede:
        return None
    tem, faltam = casar(achado.pede, habilidades(con))
    return {
        "tem": ", ".join(tem),
        "faltam": ", ".join(faltam),
        "backend": achado.backend,
        "modelo": achado.modelo,
        "cortado": texto_encaixe(vaga.titulo, vaga.descricao_texto).cortados > 0,
    }


# --- preparar candidatura (desenho 9; T438, D234) ---------------------------------------------

IDIOMAS_DA_CARTA = ("pt", "en", "es")  # os do esquema da `candidatura` (D228.1)


@dataclass(frozen=True)
class Preparando:
    """O preparo de uma vaga em `app.state.ia_preparos` (desenho 5): a IA trabalhando, ou a falha,
    que a primeira leitura mostra e tira (padrões «Serve»). O acerto só fica no banco."""

    estado: Literal["preparando", "falhou"]
    backend: str
    motivo: Motivo | None = None


Preparos = MutableMapping[int, Preparando]


def preparos_de(request: Request) -> Preparos:
    """`app.state.ia_preparos`, criado na primeira vez (o app de teste não passa pelo `serve`)."""
    estado = request.app.state
    if getattr(estado, "ia_preparos", None) is None:
        estado.ia_preparos = {}
    preparos: Preparos = estado.ia_preparos
    return preparos


@dataclass(frozen=True)
class PedidoDaVaga:
    """O pedido montado e o que a conferência precisa dele (`conferir_candidatura`)."""

    pedido: Pedido
    enviados: dict[str, object]  # o bloco PERFIL: o que a lista permitida deixou
    pede: list[str] | None  # o que a vaga pede, do `encaixe`; sem resultado, `None`
    feitas: list[str]  # as perguntas do perfil que já existem
    idioma: str  # o pedido, que é o gravado (D228.4)


def fontes_do_perfil(con: sqlite3.Connection) -> dict[str, object]:
    """Tudo o que o perfil sabe, como `dados_para` recebe (D227.7); a lista permitida escolhe."""
    return asdict(perfil.dados(con)) | {
        "habilidades": perfil.habilidades(con),
        "experiencias": perfil.experiencias(con),
        "cursos": perfil.cursos(con),
        "respostas": [p for p in perfil.perguntas(con) if p.resposta],  # só as respondidas
    }


def pedido_da_vaga(
    con: sqlite3.Connection, vaga_id: int, backend: str, modelo: str, idioma_painel: str
) -> PedidoDaVaga | None:
    """O pedido da `candidatura` da vaga, ou `None` sem perfil: nada que a lista permitida deixe ir
    (nome, e-mail, telefone e cidade nunca vão). O texto sai no idioma da vaga; sem ele (ou
    `outro`), no do painel."""
    fontes = fontes_do_perfil(con)
    enviados = dados_para("candidatura", fontes)
    linha = con.execute(
        "SELECT titulo, descricao_texto, idioma FROM vaga WHERE id = ?", (vaga_id,)
    ).fetchone()
    if not enviados or linha is None:
        return None
    titulo, descricao, da_vaga = linha
    idioma = da_vaga if da_vaga in IDIOMAS_DA_CARTA else idioma_painel
    texto = texto_encaixe(titulo or "", descricao or "")
    achado = pedes(con, vaga_id).get(vaga_id)
    return PedidoDaVaga(
        pedido=pedido_candidatura(texto, fontes, idioma, backend, modelo),
        enviados=enviados,
        pede=None if achado is None else achado.pede,
        feitas=[p.pergunta for p in perfil.perguntas(con)],
        idioma=idioma,
    )


def gravar_resposta(
    con: sqlite3.Connection, vaga_id: int, feito: PedidoDaVaga, resposta: Resposta, agora: datetime
) -> None:
    """Confere a resposta (já validada pelo esquema) e grava o preparo, que substitui o anterior;
    as perguntas que passaram viram perguntas do perfil, com origem `ia`."""
    c = conferir_candidatura(resposta.dados, feito.enviados, feito.pede, feito.feitas)
    novo = Preparo(
        idioma=feito.idioma,
        carta=c.carta,
        resumo=c.resumo,
        tem=c.tem,
        faltam=c.faltam,
        perguntar=c.perguntar,
        usou=c.usou,
        backend=resposta.backend,
        modelo=resposta.modelo,
        versao=resposta.versao,
        feito_em=agora.isoformat(),
    )
    gravar_preparo(con, vaga_id, novo)
    for pergunta in c.perguntar:
        perfil.gravar_pergunta(con, "ia:" + normalizar(pergunta), pergunta, "ia", agora)


def chave_da_falha(motivo: Motivo, backend: str) -> str:
    """O texto do motivo, com o da Anthropic à parte (D192.3), como no teste ao ligar; na IA
    manual, o da resposta colada."""
    if backend == manual.BACKEND:
        return "detalhe.candidatura.falha_manual"
    if motivo == "contexto":  # o pedido leva o perfil: encurtar ajuda também quem está offline
        return "detalhe.candidatura.falha.contexto"
    especial = motivo == "chave_recusada" and backend == "anthropic"
    return "configuracoes.ia.falha." + motivo + (".anthropic" if especial else "")


def _cortada(con: sqlite3.Connection, vaga_id: int) -> bool:
    linha = con.execute(
        "SELECT titulo, descricao_texto FROM vaga WHERE id = ?", (vaga_id,)
    ).fetchone()
    return linha is not None and texto_encaixe(linha[0] or "", linha[1] or "").cortados > 0


def contexto_do_preparo(
    con: sqlite3.Connection, vaga_id: int, preparos: Preparos | None, idioma_painel: str
) -> dict[str, Any]:
    """O que `detalhe/_preparo.html` precisa. A falha guardada sai na primeira leitura."""
    tarefa = tarefa_ia(con, "candidatura")
    em_curso = None if preparos is None else preparos.get(vaga_id)
    falha = None
    if preparos is not None and em_curso is not None and em_curso.estado == "falhou":
        del preparos[vaga_id]
        falha = chave_da_falha(em_curso.motivo or "servico_fora", em_curso.backend)
    no_manual = tarefa.backend == manual.BACKEND
    # só o manual mostra o pedido; nos outros basta saber se há perfil a mandar
    feito = (
        pedido_da_vaga(con, vaga_id, tarefa.backend, tarefa.modelo, idioma_painel)
        if tarefa.ligada and no_manual
        else None
    )
    sem_perfil = tarefa.ligada and (
        feito is None if no_manual else not dados_para("candidatura", fontes_do_perfil(con))
    )
    gravado = preparo(con, vaga_id)
    return {
        "ligada": tarefa.ligada,
        "manual": no_manual,
        "privacidade": frase_de_privacidade(tarefa, "detalhe.candidatura.privacidade."),
        "sem_perfil": sem_perfil,
        # como no bloco das habilidades, o corte é o do texto de hoje da vaga (desenho 5.2)
        "cortado": gravado is not None and _cortada(con, vaga_id),
        "preparando": em_curso is not None and em_curso.estado == "preparando",
        "falha": falha,
        "gravado": gravado,
        "citados": ", ".join(citados(gravado.faltam, f"{gravado.carta}\n{gravado.resumo}"))
        if gravado
        else "",
        "texto_manual": manual.texto_para_copiar(feito.pedido, idioma_painel)
        if no_manual and feito
        else None,
    }


def contexto_do_detalhe(
    con: sqlite3.Connection,
    vaga: Detalhe,
    hoje: date,
    retorno: str,
    preparos: Preparos | None = None,
    idioma: str = "pt",
) -> dict[str, Any]:
    """As variáveis de `detalhe/corpo.html`; `retorno` é para onde Salvar e Ocultar voltam;
    `preparos` e `idioma` (o do painel) são do preparo de candidatura."""
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
        "habilidades": _habilidades(con, vaga),
        "preparo": contexto_do_preparo(con, vaga.id, preparos, idioma),
    }
