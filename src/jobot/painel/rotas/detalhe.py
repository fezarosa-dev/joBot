"""Detalhe da vaga e correção (desenho 13.5; plano T46).

A descrição vai ao template como texto: o Jinja escapa, nada de HTML da fonte chega ao navegador.
A correção é um `<form>` de verdade (sem JavaScript volta por 303). A rota guarda a correção e já
refaz a vaga (`reprocessar_vaga`) e o encaixe (`recalcular_encaixe`), sempre com o dia local do
`Relogio` como `hoje` (DP8), para a tela mostrar o valor novo na hora (D11). Valor que a pessoa
digita e não vale (estado, salário, texto) volta ao formulário com a mensagem e 422; valor que a
tela não oferece é 422 seco; vaga que não existe é 404 (D12).
"""

import json
import re
import sqlite3
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.datastructures import FormData

from jobot.banco import acoes, leitura
from jobot.banco.buscas import recalcular_encaixe
from jobot.banco.cadastros import ler_config
from jobot.banco.gravacao import reprocessar_vaga
from jobot.banco.leitura import Detalhe
from jobot.nucleo.modelo import Area, Contrato, Modalidade, Nivel
from jobot.nucleo.tratamento.salario import ler_salario
from jobot.painel.rotas.vagas import (
    MAX_ID,
    VagaId,
    busca_efetiva,
    inteiro_da_url,
    relogio_do_painel,
    utc_do_banco,
)
from jobot.painel.seguranca import Con, renderizar

router = APIRouter()

# valor que a tela oferece, por campo de lista; "fechada" tem só sim e não
_LISTAS: dict[str, tuple[str, ...]] = {
    "area": tuple(Area),
    "nivel": tuple(Nivel),
    "modalidade": tuple(Modalidade),
    "contrato": tuple(Contrato),
    "fechada": ("sim", "nao"),
}
CAMPOS = ("area", "nivel", "modalidade", "contrato", "uf", "salario", "fechada", "outro")
_MAX_TEXTO = 500
_MESES = 12
_URGENTE_DIAS = 7  # prazo urgente: faltam menos de 7 dias (o selo "Fecha logo" vai até 7)
_UF = re.compile(r"[A-Za-z]{2}")


class _Invalido(Exception):
    """Valor digitado que a pessoa pode consertar: chave de i18n da mensagem e parâmetros."""

    def __init__(self, chave: str, **params: object) -> None:
        super().__init__(chave)
        self.chave = chave
        self.params = params


def _um(form: FormData, campo: str) -> str:
    valor = form.get(campo)
    return valor if isinstance(valor, str) else ""


def _limpo(texto: str) -> str:
    """Sem caractere de controle (a quebra de linha fica) e sem espaço nas pontas."""
    return "".join(c for c in texto if c.isprintable() or c == "\n").strip()


def _vaga_ou_404(request: Request, con: Con, vaga_id: int, pedida: int | None = None) -> Detalhe:
    agora = relogio_do_painel(request).agora()
    vaga = leitura.detalhe(con, vaga_id, busca_efetiva(con, pedida), agora)
    if vaga is None:
        raise HTTPException(404, "vaga não existe")
    return vaga


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


def _contexto(request: Request, vaga: Detalhe, busca_url: int | None) -> dict[str, Any]:
    hoje = relogio_do_painel(request).agora().astimezone().date()
    # uma fonte pode mostrar a vaga em mais de um escopo, com URLs diferentes: todos os links
    unicas: dict[tuple[str, str], Any] = {}
    for f in vaga.fontes:
        unicas.setdefault((f.fonte, f.url), f)
    candidatura = next((f.url_candidatura for f in vaga.fontes if _http(f.url_candidatura)), None)
    if candidatura is None:  # sem link próprio de candidatura, o botão abre a vaga na fonte
        candidatura = next((f.url for f in vaga.fontes if _http(f.url)), None)
    return {
        "vaga": vaga,
        "fontes": list(unicas.values()),
        "candidatura": candidatura,
        "faixa": _faixa(vaga, hoje),
        "estagio": _estagio(vaga),
        "retorno": f"/vagas/{vaga.id}" + (f"?busca={busca_url}" if busca_url else ""),
        "http": _http,
    }


@router.get("/vagas/{vaga_id}")
async def detalhe(request: Request, con: Con, vaga_id: VagaId) -> HTMLResponse:
    busca_url = inteiro_da_url(request.query_params.get("busca"), MAX_ID)
    vaga = _vaga_ou_404(request, con, vaga_id, busca_url)
    return renderizar(request, "detalhe/pagina.html", **_contexto(request, vaga, busca_url))


def _atual(vaga: Detalhe) -> dict[str, str]:
    """O valor de hoje de cada campo de lista: o formulário abre com ele selecionado."""
    atual = {c: getattr(vaga, c) or "" for c in ("area", "nivel", "modalidade", "contrato")}
    return atual | {"fechada": "sim" if vaga.fechada else "nao"}


def _formulario(
    request: Request, vaga: Detalhe, form: FormData | None = None, erro: _Invalido | None = None
) -> HTMLResponse:
    """O formulário; com `form`, devolve o que a pessoa digitou (campo, valores e comentário)."""
    f: dict[str, Any] = {"campo": "", "comentario": "", "valores": {}}
    if form is not None:
        f = {
            "campo": _um(form, "campo"),
            "comentario": _um(form, "comentario"),
            "valores": {c: _um(form, f"valor_{c}") for c in CAMPOS},
        }
    return renderizar(
        request,
        "detalhe/correcao.html",
        vaga=vaga,
        campos=CAMPOS,
        listas=_LISTAS,
        atual=_atual(vaga),
        f=f,
        erro=erro,
    )


@router.get("/vagas/{vaga_id}/correcao")
async def formulario(request: Request, con: Con, vaga_id: VagaId) -> HTMLResponse:
    return _formulario(request, _vaga_ou_404(request, con, vaga_id))


def _salario_legivel(con: sqlite3.Connection, vaga_id: int, texto: str) -> bool:
    """Lê o salário como o reprocessamento lê (D11): o texto sozinho, com a moeda, com o idioma."""
    moeda, idioma = con.execute(
        "SELECT sal_moeda, idioma FROM vaga WHERE id = ?", (vaga_id,)
    ).fetchone()
    tentativas = [(texto, "outro"), (texto, idioma)]
    if moeda is not None:
        tentativas.insert(1, (f"{moeda} {texto}", "outro"))
    return any(ler_salario(t, None, i) is not None for t, i in tentativas)


def _validar(con: sqlite3.Connection, vaga_id: int, campo: str, valor: str) -> str:
    """O valor a guardar. Fora do que a tela oferece é 422 seco; texto ruim volta ao formulário."""
    if campo in _LISTAS:
        if valor not in _LISTAS[campo]:
            raise HTTPException(422, f"valor fora da lista: {campo}")
        return valor
    if len(valor) > _MAX_TEXTO:
        raise _Invalido("detalhe.correcao.erro.longo", max=_MAX_TEXTO)
    if campo == "uf" and not _UF.fullmatch(valor):
        raise _Invalido("detalhe.correcao.erro.uf")
    if campo == "uf":
        return valor.upper()
    if campo == "salario" and valor and not _salario_legivel(con, vaga_id, valor):
        raise _Invalido("detalhe.correcao.erro.salario")
    if campo == "outro" and not valor:
        raise _Invalido("detalhe.correcao.erro.outro")
    return valor


@router.post("/vagas/{vaga_id}/correcao")
async def corrigir(request: Request, con: Con, vaga_id: VagaId) -> Response:
    vaga = _vaga_ou_404(request, con, vaga_id)
    form = await request.form()
    campo = _um(form, "campo")
    if campo not in CAMPOS:
        raise HTTPException(422, "campo que não se corrige")
    comentario = _limpo(_um(form, "comentario"))
    try:
        valor = _validar(con, vaga_id, campo, _limpo(_um(form, f"valor_{campo}")))
        if len(comentario) > _MAX_TEXTO:
            raise _Invalido("detalhe.correcao.erro.comentario", max=_MAX_TEXTO)
    except _Invalido as erro:
        pagina = _formulario(request, vaga, form, erro)
        pagina.status_code = 422
        return pagina
    agora = relogio_do_painel(request).agora()
    hoje = agora.astimezone().date()
    try:
        try:
            acoes.corrigir(con, vaga_id, campo, valor, comentario or None, agora)
        except ValueError as erro:  # só a gravação: depois dela a correção já está guardada
            raise HTTPException(422, str(erro)) from erro
        reprocessar_vaga(con, vaga_id, hoje=hoje)
        regras = bool(ler_config(con, "regras_ocultar_ligadas"))
        recalcular_encaixe(con, None, regras, hoje=hoje, vaga_id=vaga_id)
    except LookupError as erro:
        raise HTTPException(404, "vaga não existe") from erro
    return RedirectResponse(f"/vagas/{vaga_id}", status_code=303)
