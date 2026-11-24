"""Tela de vagas: abas, filtros, ordem, destaques e ações da vaga (desenho 13.3 a 13.5; plano T45).

Todo parâmetro de URL é lido à mão: link velho ou torto cai no padrão, nunca em 422 (RF2).
Ação que muda dados é um `<form>` de verdade: sem JavaScript volta por 303 (`voltar`); o Ocultar
e o Desfazer, com HTMX, trazem a faixa de desfazer e a lateral por OOB.
"""

import json
import re
import sqlite3
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.datastructures import QueryParams

from jobot.banco import acoes, leitura
from jobot.banco.cadastros import gravar_config, ler_config
from jobot.banco.leitura import Filtros, Item
from jobot.banco.paginas import paginas, ultimas_diferencas
from jobot.nucleo.tratamento.locais import codigos_de_pais, nome_do_pais, nome_em_ingles
from jobot.painel.consultas import (
    MAX_ID,
    IdDoBanco,
    busca_ativa,
    busca_efetiva,
    ids_destaques,
    inteiro_da_url,
    relogio_do_painel,
)
from jobot.painel.detalhe_vaga import contexto_do_detalhe
from jobot.painel.lateral import ler_lateral
from jobot.painel.moeda import (
    INTEGER_MAX,
    Exibicao,
    FiltroSalario,
    exibicao_do_painel,
    filtro_salario,
)
from jobot.painel.seguranca import Con, de_volta, renderizar

router = APIRouter()

ABA_DESTAQUES = "destaques"
CHIPS = ("modalidade", "nivel", "area", "contrato", "uf", "fonte", "encaixe", "pais", "publicada")
_ENCAIXES = ("bom", "medio", "fraco")
# rótulo do valor do chip: grupo -> prefixo da chave de i18n (None: o valor já é o texto)
_ROTULO_CHIP = {
    "modalidade": "modalidade",
    "nivel": "nivel",
    "area": "area",
    "contrato": "contrato",
    "fonte": "fonte",
    "encaixe": "vagas.encaixe",
    "motivo": "vagas.motivo",
    "status": "vagas.status",
    "uf": None,
    "pais": None,  # o nome vem de `_nome_do_pais`, na língua da tela
    "publicada": "vagas.publicada",
}
_TETO_SALARIO = 10**12
_MAX_TEXTO = 100
# o INTEGER do SQLite é de 64 bits com sinal: id maior estoura em OverflowError (500)
VagaId = IdDoBanco
_MAX_PAGINA = 10_000
# o Desfazer recarrega até 20 páginas de uma vez (T311): 10 mil vagas levavam ~4 s e 7,6 MB
_MAX_RECARGA = 20


def _texto(texto: str | None) -> str | None:
    limpo = "".join(c for c in texto or "" if c.isprintable()).strip()[:_MAX_TEXTO]
    return limpo or None


def _sem_criterio(con: sqlite3.Connection, busca_id: int | None) -> bool:
    """Sem busca, ou busca sem cargo, lugar, modalidade, nível, idioma nem salário (11.1)."""
    if busca_id is None:
        return True
    linha = con.execute(
        "SELECT cargos, cidades, modalidades, niveis, idiomas, salario_min FROM busca WHERE id = ?",
        (busca_id,),
    ).fetchone()
    return not (linha[5] or any(json.loads(lista) for lista in linha[:5]))


@dataclass(frozen=True)
class Estado:
    """O que a URL pede, já limpo. `*_url`: veio mesmo na URL e por isso volta nos links."""

    aba: str
    busca_id: int | None
    busca_url: bool
    q: str
    excluir: str
    cidade: str
    empresa: str
    sal_de: int | None
    sal_ate: int | None
    sem_salario: bool
    salario: FiltroSalario
    chips: Mapping[str, str]
    ordem: str
    ordem_url: bool
    sem_criterio: bool
    destaques_ligados: bool

    @property
    def e_destaques(self) -> bool:
        return self.aba == ABA_DESTAQUES

    def filtros(self, pagina: int = 1) -> Filtros:
        return Filtros(
            aba=self.aba,
            busca_id=self.busca_id,
            q=self.q,
            excluir=self.excluir,
            cidade=self.cidade,
            empresa=self.empresa,
            sal_de_brl=self.salario.sal_de_brl,
            sal_ate_brl=self.salario.sal_ate_brl,
            sal_moeda=self.salario.sal_moeda,
            sal_de_centavos=self.salario.sal_de_centavos,
            sal_ate_centavos=self.salario.sal_ate_centavos,
            sem_salario=self.sem_salario,
            pais=self.chips.get("pais"),
            publicada=self.chips.get("publicada"),
            area=self.chips.get("area"),
            nivel=self.chips.get("nivel"),
            modalidade=self.chips.get("modalidade"),
            contrato=self.chips.get("contrato"),
            uf=self.chips.get("uf"),
            fonte=self.chips.get("fonte"),
            encaixe=self.chips.get("encaixe"),
            ordem=self.ordem,
            pagina=pagina,
        )

    def url(
        self,
        *,
        aba: str | None = None,
        chips: Mapping[str, str] | None = None,
        extras: Sequence[tuple[str, str]] = (),
        caminho: str = "/vagas",
    ) -> str:
        """O endereço desta vista, com a aba primeiro; `chips` troca os filtros de chip."""
        escolhidos = self.chips if chips is None else chips
        pares = [("aba", aba or self.aba)]
        if self.busca_url and self.busca_id is not None:
            pares.append(("busca", str(self.busca_id)))
        if self.q:
            pares.append(("q", self.q))
        pares += [(k, v) for k in ("excluir", "cidade", "empresa") if (v := getattr(self, k))]
        pares += [(k, str(v)) for k in ("sal_de", "sal_ate") if (v := getattr(self, k)) is not None]
        if self.sem_salario:
            pares.append(("sem_salario", "1"))
        pares += [(g, escolhidos[g]) for g in CHIPS if g in escolhidos]
        if self.ordem_url:
            pares.append(("ordem", self.ordem))
        return f"{caminho}?" + urlencode(pares + list(extras))


def _chip_valido(grupo: str, valor: str) -> bool:
    """`pais` e `publicada` têm conjunto fechado; os outros chips aceitam o que vier."""
    if grupo == "pais":
        return valor in codigos_de_pais()
    if grupo == "publicada":
        return valor in leitura.PUBLICADA
    return True


def ler_estado(params: QueryParams, con: sqlite3.Connection, ex: Exibicao) -> Estado:
    ligados = bool(ler_config(con, "destaques_ligados"))
    validas = {*leitura.ABAS, *([ABA_DESTAQUES] if ligados else [])}
    pedida_aba = params.get("aba") or ""
    aba = pedida_aba if pedida_aba in validas else (ABA_DESTAQUES if ligados else "todas")
    pedida = inteiro_da_url(params.get("busca"), MAX_ID)
    busca_id = busca_efetiva(con, pedida)
    sem = _sem_criterio(con, busca_id)
    pedida_ordem = params.get("ordem") or ""
    ordem_url = pedida_ordem in leitura.ORDENS
    ordem = pedida_ordem if ordem_url else ("recentes" if sem else "encaixe")
    sal_de = inteiro_da_url(params.get("sal_de"), _TETO_SALARIO)
    sal_ate = inteiro_da_url(params.get("sal_ate"), _TETO_SALARIO)
    if sal_de is not None and sal_ate is not None and sal_de > sal_ate:
        sal_de, sal_ate = sal_ate, sal_de  # link torto cai numa faixa útil, não numa lista vazia
    return Estado(
        aba=aba,
        busca_id=busca_id,
        busca_url=pedida is not None and busca_id == pedida,
        q=_texto(params.get("q")) or "",
        excluir=_texto(params.get("excluir")) or "",
        cidade=_texto(params.get("cidade")) or "",
        empresa=_texto(params.get("empresa")) or "",
        sal_de=sal_de,
        sal_ate=sal_ate,
        sem_salario=params.get("sem_salario") == "1",
        salario=filtro_salario(sal_de, sal_ate, ex),
        chips={g: v for g in CHIPS if (v := _texto(params.get(g))) and _chip_valido(g, v)},
        ordem=ordem,
        ordem_url=ordem_url,
        sem_criterio=sem,
        destaques_ligados=ligados,
    )


def _id_html(valor: str) -> str:
    """Id de HTML que não se repete: todo caractere fora de `[A-Za-z0-9-]` (o `_` também) vira
    `_<hex>_`; como o hex não tem `_`, dois valores diferentes nunca dão o mesmo id."""
    return re.sub(r"[^A-Za-z0-9-]", lambda m: f"_{ord(m.group()):x}_", valor)


def _ordem_chip(grupo: str, valor: str) -> int:
    if grupo == "publicada":
        return list(leitura.PUBLICADA).index(valor) if valor in leitura.PUBLICADA else 0
    return _ENCAIXES.index(valor) if grupo == "encaixe" and valor in _ENCAIXES else 0


def _nome_do_pais(codigo: str, idioma: str) -> str:
    nome = nome_em_ingles if idioma == "en" else nome_do_pais
    return nome(codigo) or codigo


def grupos_dos_chips(
    con: sqlite3.Connection,
    estado: Estado,
    agora: datetime,
    idioma: str,
    grupos: Collection[str] | None = None,
) -> list[dict[str, Any]]:
    """Os chips com contagem. Motivo (Ocultas) e situação (Candidatei) só contam: sem filtro.

    `grupos`: só esses (`None`, todos), como em `leitura.contar_chips`."""
    contagens = leitura.contar_chips(con, estado.filtros(), agora, grupos)
    saida: list[dict[str, Any]] = []
    for nome in (*CHIPS, "motivo", "status"):
        if grupos is not None and nome not in grupos:
            continue  # nem o chip escolhido de um grupo não pedido
        interativo = nome in CHIPS
        valores = dict(contagens.get(nome, {}))
        escolhido = estado.chips.get(nome)
        if interativo and escolhido and escolhido not in valores:
            valores[escolhido] = 0  # filtro sem nenhuma vaga continua visível, para desligar
        if not valores:
            continue
        # encaixe vai de bom a fraco e publicada de 24 h a 30 dias; os outros, do mais contado
        # para o menos
        ordenados = sorted(
            valores.items(), key=lambda kv: (_ordem_chip(nome, kv[0]), -kv[1], kv[0])
        )
        prefixo = _ROTULO_CHIP[nome]
        chips = []
        for valor, n in ordenados:
            ligado = escolhido == valor
            trocados = {k: v for k, v in estado.chips.items() if k != nome}
            chips.append(
                {
                    "id": _id_html(valor),
                    "valor": valor,
                    "chave": f"{prefixo}.{valor}" if prefixo else "",
                    "texto": _nome_do_pais(valor, idioma) if nome == "pais" else None,
                    "n": n,
                    "pressionado": ligado,
                    "url": estado.url(chips=trocados if ligado else {**trocados, nome: valor}),
                }
            )
        saida.append({"nome": nome, "interativo": interativo, "chips": chips})
    return saida


def seletor_de_buscas(con: sqlite3.Connection, estado: Estado) -> list[dict[str, Any]]:
    """As buscas ativas (e a da URL, mesmo desligada), para o menu pop-up da barra da lista."""
    linhas = con.execute(
        "SELECT id, nome FROM busca WHERE ativa = 1 OR id = ? ORDER BY id", (estado.busca_id,)
    ).fetchall()
    if len(linhas) < 2:
        return []
    return [{"id": id_, "nome": nome, "atual": id_ == estado.busca_id} for id_, nome in linhas]


def _paginas_programas(con: sqlite3.Connection) -> list[dict[str, Any]]:
    """As páginas ativas (a que mudou há menos tempo primeiro), com a última diferença."""
    ultima = ultimas_diferencas(con)
    achadas = [p for p in paginas(con) if p.ativa]
    achadas.sort(key=lambda p: p.mudou_em or datetime.min.replace(tzinfo=UTC), reverse=True)
    return [{"p": p, "diferenca": ultima.get(p.id) if p.mudou_em else None} for p in achadas]


def _contexto_pagina(
    con: sqlite3.Connection, estado: Estado, agora: datetime, ex: Exibicao, ate_pagina: int = 1
) -> dict[str, Any]:
    """`ate_pagina`: quantas páginas da lista vêm juntas (o Desfazer recarrega até a que o
    "Carregar mais" já trouxe, T305)."""
    ids_de_destaque = ids_destaques(con, estado.busca_id, agora) if estado.destaques_ligados else []
    itens: Sequence[Item]
    mais_url = None
    fora_sem_salario = fora_sem_valor = 0
    if estado.e_destaques:
        achados = [leitura.detalhe(con, i, estado.busca_id, agora) for i in ids_de_destaque]
        itens = [d for d in achados if d is not None]
        ate_pagina = 1
    else:
        juntos: list[Item] = []
        tem_mais, n = True, 0
        while tem_mais and n < ate_pagina:
            n += 1
            pagina = leitura.listar(con, estado.filtros(n), agora)
            juntos += pagina.itens
            tem_mais = pagina.tem_mais
        itens, ate_pagina = juntos, n
        fora_sem_salario, fora_sem_valor = leitura.contar_fora_do_salario(
            con, estado.filtros(), agora
        )
        if tem_mais:
            mais_url = estado.url(extras=[("pagina", str(ate_pagina + 1))])
    return {
        "paginas_programas": _paginas_programas(con) if estado.aba == "programas" else [],
        "seletor": seletor_de_buscas(con, estado),
        # o menu de busca manda a vista de agora (aba, filtros, ordem) e só troca a `busca`
        "campos_do_seletor": parse_qsl(urlsplit(replace(estado, busca_url=False).url()).query),
        "chips_url": None if estado.e_destaques else estado.url(caminho="/vagas/chips"),
        "itens": itens,
        "mais_url": mais_url,
        "proxima": ate_pagina + 1,
        "ordens": list(leitura.ORDENS),
        "ordem": estado.ordem,
        "q": estado.q,
        "excluir": estado.excluir,
        "cidade": estado.cidade,
        "empresa": estado.empresa,
        "sal_de": estado.sal_de,
        "sal_ate": estado.sal_ate,
        # os chips ativos moram no "Mais filtros" (T301): contam junto com os campos
        "n_mais_filtros": len(estado.chips)
        + sum(
            1
            for v in (estado.excluir, estado.cidade, estado.empresa, estado.sal_de, estado.sal_ate)
            if v not in ("", None)
        ),
        "exibicao": ex,
        "aviso_salario": None if estado.e_destaques else estado.salario.aviso,  # lista sem Filtros
        "fora_sem_salario": fora_sem_salario,
        "fora_sem_valor": fora_sem_valor,
        "mostrar_tambem_url": replace(estado, sem_salario=True).url(),
        "sem_criterio": estado.sem_criterio,
        "e_destaques": estado.e_destaques,
        "tem_busca": True,  # a casca põe o campo q na barra, ligado ao form#busca do miolo
        "aba_da_busca": "todas" if estado.e_destaques else estado.aba,
        "campos_ocultos": [
            *((g, v) for g in CHIPS if (v := estado.chips.get(g))),
            *([("sem_salario", "1")] if estado.sem_salario else []),
        ],
        "busca_id": estado.busca_id,
        "busca_na_url": estado.busca_url,
        "retorno": estado.url(),
        "marcar_foco": False,
        "url_vaga": estado.url(extras=[("vaga", "")]),  # a linha completa com o seu id
    }


def _lateral_oob(
    con: sqlite3.Connection, agora: datetime, busca_id: int | None, caminho: str, aba: str
) -> dict[str, Any]:
    """A seção "Vagas" da lateral para a resposta HTMX trocar no lugar: as contagens de agora e o
    item marcado igual ao da casca (`caminho` e `aba` são os da página que a pessoa vê)."""
    lado = ler_lateral(con, agora, busca_id)
    return {"lado": lado, "caminho": caminho, "aba": aba if aba in lado.abas else lado.abas[0]}


def com_vary(resposta: HTMLResponse) -> HTMLResponse:
    resposta.headers["Vary"] = "HX-Request, HX-History-Restore-Request, HX-Target"
    return resposta


@router.get("/")
async def raiz(con: Con) -> RedirectResponse:
    if not ler_config(con, "primeira_execucao_concluida", False):
        return RedirectResponse("/primeira-execucao/1", status_code=303)
    aba = ABA_DESTAQUES if ler_config(con, "destaques_ligados") else "todas"
    return RedirectResponse(f"/vagas?aba={aba}", status_code=303)


def _gravar_escolha(con: sqlite3.Connection, pedida: int | None) -> None:
    """Só o id de uma busca ligada vira a escolhida; o resto (texto, id que não existe, busca
    desligada) não grava nada. A desligada continua valendo na página, mas só nela (E16)."""
    if busca_ativa(con, pedida) and ler_config(con, "busca_escolhida", None) != pedida:
        gravar_config(con, "busca_escolhida", pedida)


@router.get("/vagas")
async def vagas(request: Request, con: Con) -> HTMLResponse:
    agora = relogio_do_painel(request).agora()
    ex = exibicao_do_painel(con, agora.astimezone().date())
    estado = ler_estado(request.query_params, con, ex)
    _gravar_escolha(con, inteiro_da_url(request.query_params.get("busca"), MAX_ID))
    cabecalho = request.headers
    restaurando = cabecalho.get("hx-history-restore-request") == "true"
    parcial = cabecalho.get("hx-request") == "true" and not restaurando
    pagina = inteiro_da_url(request.query_params.get("pagina"), _MAX_PAGINA) or 1
    # o Desfazer recarrega o miolo inteiro até a página já carregada (T305); o "carregar mais"
    # mira o #lista-vagas
    miolo_ate = parcial and cabecalho.get("hx-target") == "vagas-miolo"
    if parcial and pagina > 1 and not estado.e_destaques and not miolo_ate:
        # "carregar mais": só as linhas novas e o botão da página seguinte
        lista = leitura.listar(con, estado.filtros(pagina), agora)
        seguinte = estado.url(extras=[("pagina", str(pagina + 1))])
        return com_vary(
            renderizar(
                request,
                "vagas/mais.html",
                exibicao=ex,
                itens=lista.itens,
                mais_url=seguinte if lista.tem_mais else None,
                proxima=pagina + 1,
                marcar_foco=True,
                retorno=estado.url(),
                busca_id=estado.busca_id,
                url_vaga=estado.url(extras=[("vaga", "")]),
            )
        )
    # o detalhe ao lado (T255): id torto ou de vaga que não existe abre só a lista
    vaga_id = inteiro_da_url(request.query_params.get("vaga"), INTEGER_MAX)
    vaga = None if vaga_id is None else leitura.detalhe(con, vaga_id, estado.busca_id, agora)
    detalhe: dict[str, Any] | None = None
    if vaga is not None:
        retorno = estado.url(extras=[("vaga", str(vaga.id))])
        detalhe = contexto_do_detalhe(con, vaga, agora.astimezone().date(), retorno)
    if parcial and cabecalho.get("hx-target") == "detalhe-vaga":
        # o clique na linha troca só o detalhe: sem refazer a lista, os Destaques e a lateral
        return com_vary(renderizar(request, "vagas/detalhe_lado.html", detalhe=detalhe))
    contexto = _contexto_pagina(
        con, estado, agora, ex, min(pagina, _MAX_RECARGA) if miolo_ate else 1
    )
    contexto["detalhe"] = detalhe
    if parcial:
        contexto["lateral_oob"] = _lateral_oob(con, agora, estado.busca_id, "/vagas", estado.aba)
    modelo = "vagas/miolo.html" if parcial else "vagas/pagina.html"
    return com_vary(renderizar(request, modelo, **contexto))


def _aplicar(request: Request, acao: Callable[[datetime], None]) -> None:
    """Roda a ação do `acoes`: vaga que não existe é 404; valor ou estado inválido, 422."""
    try:
        acao(relogio_do_painel(request).agora())
    except LookupError as erro:
        raise HTTPException(404, "vaga não existe") from erro
    except ValueError as erro:
        raise HTTPException(422) from erro  # o texto da tela sai do status (T150)


def _lateral_de_volta(
    con: sqlite3.Connection, agora: datetime, busca_id: int | None, voltar: str
) -> dict[str, Any]:
    """A lateral por OOB com o item marcado da página de onde a pessoa veio (`voltar`)."""
    de = urlsplit(voltar)
    aba = parse_qs(de.query).get("aba", [""])[0]
    return _lateral_oob(con, agora, busca_id, "/vagas" if de.path == "/" else de.path, aba)


def _resposta_faixa(
    request: Request,
    con: sqlite3.Connection,
    vaga_id: int,
    voltar: str,
    busca: str,
    ocultou: bool,
    antes: str = "",
    com_faixa: bool = True,
) -> Response:
    """Ocultar e Desfazer/Refazer (T256). Sem HTMX, volta para a página como antes. Com HTMX, a
    faixa de desfazer e a lateral por OOB; o HX-Trigger-After-Settle avisa o app.js para tirar a
    linha (e fechar o detalhe dela) ou para recarregar a lista com a linha de volta. O aviso sai
    depois do settle: antes dele, os hx-* da faixa nova ainda não valem e um ⌘Z viraria POST
    nativo. `antes` vai no form do Desfazer: "-1" quando a vaga estava em "mostrar mesmo assim",
    para o Desfazer voltar a ela e não a 0. `com_faixa=False` (Ocultar repetido, vaga já oculta)
    deixa a faixa da tela como está: a nova levaria `antes=""` e o Desfazer zeraria a vaga."""
    if request.headers.get("hx-request") != "true":
        return de_volta(voltar)
    agora = relogio_do_painel(request).agora()
    busca_id = busca_efetiva(con, inteiro_da_url(busca, MAX_ID))
    resposta = renderizar(
        request,
        "vagas/faixa_oob.html",
        texto="ocultada" if ocultou else "mostrada",
        acao="desfazer" if ocultou else "refazer",
        rota="/vagas/{id}/mostrar" if ocultou else "/vagas/{id}/ocultar",
        vaga_id=vaga_id,
        voltar=voltar,
        busca=busca,
        antes=antes,
        com_faixa=com_faixa,
        lateral_oob=_lateral_de_volta(con, agora, busca_id, voltar),
    )
    evento = "vaga-ocultada" if ocultou else "vaga-mostrada"
    resposta.headers["HX-Trigger-After-Settle"] = json.dumps({evento: {"vaga": vaga_id}})
    return resposta


@router.post("/vagas/{vaga_id}/status")
async def mudar_status(
    request: Request,
    con: Con,
    vaga_id: VagaId,
    status: Annotated[str, Form()],
    voltar: Annotated[str, Form()] = "/",
) -> Response:
    """Salvar e os passos seguintes. Quem pede é o menu de contexto e o detalhe, por POST sem
    HTMX: a resposta volta para a página de onde a pessoa veio (o corpo do cartão saiu, T305)."""
    _aplicar(request, lambda agora: acoes.mudar_status(con, vaga_id, status, agora))
    return de_volta(voltar)


@router.post("/vagas/{vaga_id}/ocultar")
async def ocultar(
    request: Request,
    con: Con,
    vaga_id: VagaId,
    voltar: Annotated[str, Form()] = "/",
    busca: Annotated[str, Form()] = "",
) -> Response:
    linha = con.execute("SELECT oculta_manual FROM vaga WHERE id = ?", (vaga_id,)).fetchone()
    _aplicar(request, lambda agora: acoes.ocultar(con, vaga_id, agora))
    antes = "-1" if linha and linha[0] == -1 else ""
    ja_oculta = bool(linha and linha[0] == 1)
    return _resposta_faixa(
        request, con, vaga_id, voltar, busca, ocultou=True, antes=antes, com_faixa=not ja_oculta
    )


@router.post("/vagas/{vaga_id}/mostrar")
async def mostrar(
    request: Request,
    con: Con,
    vaga_id: VagaId,
    voltar: Annotated[str, Form()] = "/",
    busca: Annotated[str, Form()] = "",
    antes: Annotated[str, Form()] = "",
) -> Response:
    """ "Trazer de volta" (ocultada à mão) ou "mostrar mesmo assim" (ocultada por regra). O
    Desfazer da faixa manda `antes=-1` quando o Ocultar saiu de um "mostrar mesmo assim"."""
    linha = con.execute("SELECT oculta_manual FROM vaga WHERE id = ?", (vaga_id,)).fetchone()
    if linha is None:
        raise HTTPException(404, "vaga não existe")
    if linha[0] == 1:
        oculta = -1 if antes == "-1" else 0
        _aplicar(request, lambda agora: acoes.trazer_de_volta(con, vaga_id, agora, oculta))
    else:
        _aplicar(request, lambda agora: acoes.mostrar(con, vaga_id, agora))
    return _resposta_faixa(request, con, vaga_id, voltar, busca, ocultou=False)
