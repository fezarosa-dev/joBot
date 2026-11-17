"""Leitor do LinkedIn com login (D136.12 a D136.18)."""

import dataclasses
import re
from collections.abc import Sequence
from datetime import datetime, timedelta
from urllib.parse import parse_qs, quote_plus, urlencode, urljoin, urlsplit, urlunsplit

from selectolax.lexbor import LexborHTMLParser, LexborNode

from jobot.nucleo.coletores.base import ContextoColeta
from jobot.nucleo.leitores.base import Captura, EscopoLogado, Leitura
from jobot.nucleo.modelo import Busca, Modalidade, VagaColetada, confere_http
from jobot.nucleo.relogio import Relogio, RelogioReal
from jobot.nucleo.texto import normalizar

_HOST = "www.linkedin.com"
_SEMANA = "r604800"  # f_TPR: última semana
_POR_PAGINA = 25
_CARTAO = '[componentkey^="job-card-component-ref-"]'
_PREFIXO_CARTAO = "job-card-component-ref-"
_ID = re.compile(r"[0-9]{1,30}")
_START = re.compile(r"[0-9]{1,6}")
_VERIFICADA = re.compile(r"\s*\((?:Verified job|Vaga verificada)\)$")
_LOCAL = re.compile(r"(.*?)\s*\(([^()]+)\)")
_SALARIO = re.compile(
    r"(?:R\$|US\$|[$€£]|\b(?:BRL|USD|EUR|GBP)\b).*[0-9]|[0-9].*\b(?:BRL|USD|EUR)\b"
)
_DESCRICAO = '[componentkey^="JobDetails_AboutTheJob_"]'
# shortcut: rótulo pt não visto numa conta em português, conferir na primeira captura em pt
_ROTULOS_CANDIDATURA = ("Apply on company website", "Candidatar-se no site da empresa")
_AVISOS_VAZIA = frozenset(
    {
        "No results found",
        "No matching jobs found",
        "Nenhum resultado encontrado",
        "Nenhuma vaga encontrada",
    }
)
_CONTRATOS = frozenset(
    {
        "Full-time",
        "Part-time",
        "Contract",
        "Temporary",
        "Internship",
        "Volunteer",
        "Tempo integral",
        "Meio período",
        "Contrato",
        "Temporário",
        "Estágio",
        "Voluntário",
    }
)
_UNIDADES = {
    "minute": timedelta(minutes=1),
    "minuto": timedelta(minutes=1),
    "hour": timedelta(hours=1),
    "hora": timedelta(hours=1),
    "day": timedelta(days=1),
    "dia": timedelta(days=1),
    "week": timedelta(days=7),
    "semana": timedelta(days=7),
    "month": timedelta(days=30),
    "mês": timedelta(days=30),
    "mese": timedelta(days=30),  # "meses" sem o "s" do plural
}
_DATA = re.compile(
    r"(?:(?:Posted|Reposted)\s+)?([0-9]{1,4})\s+(minute|hour|day|week|month)s?\s+ago"
    r"|(?:(?:Publicada|Republicada)\s+)?há\s+([0-9]{1,4})\s+(minuto|hora|dia|semana|mês|mese)s?",
    re.IGNORECASE,
)


def _data_relativa(texto: str, agora: datetime) -> datetime | None:
    """Texto como "N days ago" ou "há N dias" vira `agora` menos N; semana = 7, mês = 30 dias."""
    m = _DATA.fullmatch(texto.strip())
    if m is None:
        return None
    numero, unidade = (m[1], m[2]) if m[1] else (m[3], m[4])
    return agora - int(numero) * _UNIDADES[unidade.lower()]


def _sem_copia_de_leitor_de_tela(arvore: LexborHTMLParser) -> None:
    """`<span>Selected, X</span><span aria-hidden>X</span>`: fica só o texto que aparece."""
    for visivel in arvore.css('p > span[aria-hidden="true"]'):
        anterior = visivel.prev
        while anterior is not None and anterior.tag == "-text":
            anterior = anterior.prev
        if anterior is not None and anterior.tag == "span":
            if "aria-hidden" not in anterior.attributes:
                anterior.decompose()


def _linhas(cartao: LexborNode) -> list[str]:
    """Uma linha por `<p>`, sem " (Verified job)"; linhas seguidas iguais contam uma vez."""
    linhas: list[str] = []
    for p in cartao.css("p"):
        linha = _VERIFICADA.sub("", p.text(strip=True))
        if not (linhas and linha and linhas[-1] == linha):
            linhas.append(linha)
    return linhas


def _textos_das_buscas(buscas: Sequence[Busca]) -> list[str]:
    """Texto por cargo e cidade, mais o remoto; repetido (ignora caixa) fica a 1ª grafia."""
    vistos: dict[str, str] = {}
    for busca in buscas:
        for cargo in (c.strip() for c in busca.cargos):
            if not cargo:
                continue
            achados = [
                f"{cargo} em {', '.join(p for p in (cidade, (local.uf or '').strip()) if p)}"
                for local in busca.cidades
                if (cidade := (local.cidade or "").strip())
            ]
            if Modalidade.REMOTO in busca.modalidades:
                achados.append(f"{cargo} remoto")
            for texto in achados or [cargo]:
                vistos.setdefault(normalizar(texto), texto)
    return list(vistos.values())


class LinkedIn:
    chave = "linkedin_logado"
    nome = "LinkedIn"
    hosts: tuple[str, ...] = (_HOST,)
    url_login = "https://www.linkedin.com/login"
    url_entrada = "https://www.linkedin.com/jobs/"
    # `host + caminho`, como o navegador casa (`casa_login`)
    prefixos_login: tuple[str, ...] = tuple(
        _HOST + caminho
        for caminho in ("/login", "/checkpoint/", "/authwall", "/uas/login", "/signup")
    )
    respostas: tuple[str, ...] = ()
    campos_conta: tuple[str, ...] = ()
    rolar = True
    lista_tem_descricao = False
    lista_exaustiva = False  # busca por relevância da última semana: vaga aberta sai da lista

    def __init__(self, relogio: Relogio | None = None) -> None:
        self._relogio = relogio or RelogioReal()

    def escopos(self, ctx: ContextoColeta) -> Sequence[EscopoLogado]:
        textos = _textos_das_buscas(ctx.buscas) if ctx.buscas else list(dict.fromkeys(ctx.termos))
        return [
            EscopoLogado(
                texto,
                f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(texto)}&f_TPR={_SEMANA}",
            )
            for texto in textos
        ]

    def _no_login(self, url: str) -> bool:
        partes = urlsplit(url)
        return ((partes.hostname or "") + partes.path).startswith(self.prefixos_login)

    def e_login(self, captura: Captura) -> bool:
        return self._no_login(captura.url)

    def pagina_logada(self, html: str, url: str) -> bool:
        """Marca de sessão que não depende de vaga: o link das notificações na barra global."""
        if self._no_login(url):
            return False
        arvore = LexborHTMLParser(html)
        for terceiro in arvore.css(_DESCRICAO):  # link na descrição da vaga não é sessão
            terceiro.decompose()
        if arvore.css_first('a[data-view-name="navigation-notifications"]') is not None:
            return True
        for link in arvore.css("a[href]"):
            try:
                alvo = urlsplit(urljoin(url, link.attributes["href"] or ""))
            except ValueError:
                continue
            if alvo.hostname == _HOST and alvo.path == "/notifications/":
                return True
        return False

    def pagina_bloqueada(self, html: str, url: str) -> bool:
        return False  # o desafio é achado pelo `achar_widget` do navegador (D136.17)

    def proxima(self, captura: Captura) -> str | None:
        """Página seguinte só com `keywords`, o filtro da semana e `start` + 25 (D136.13)."""
        arvore = LexborHTMLParser(captura.html)
        ids = {no.attributes.get("componentkey") for no in arvore.css(_CARTAO)}
        if len(ids) < _POR_PAGINA:
            return None
        partes = urlsplit(captura.url)
        query = parse_qs(partes.query)
        start = query.get("start", ["0"])[0]
        if not _START.fullmatch(start):
            return None
        nova = urlencode(
            {
                "keywords": query.get("keywords", [""])[0],
                "f_TPR": _SEMANA,
                "start": str(int(start) + _POR_PAGINA),
            }
        )
        return urlunsplit(("https", _HOST, partes.path, nova, ""))

    def ler(self, captura: Captura, escopo: EscopoLogado) -> Leitura:
        arvore = LexborHTMLParser(captura.html)
        _sem_copia_de_leitor_de_tela(arvore)
        agora = self._relogio.agora()
        vagas: list[VagaColetada] = []
        pulados = 0
        vistos: set[str] = set()
        for cartao in arvore.css(_CARTAO):
            chave = cartao.attributes.get("componentkey") or ""
            if chave in vistos:  # a marca aparece duas vezes por cartão
                continue
            vistos.add(chave)
            vaga = self._vaga(cartao, chave.removeprefix(_PREFIXO_CARTAO), escopo, agora)
            if vaga is None:
                pulados += 1
            else:
                vagas.append(vaga)
        if vagas or pulados:
            return Leitura(tuple(vagas), pulados, not vagas)
        vazia = any(no.text(strip=True) in _AVISOS_VAZIA for no in arvore.css("h1, h2, h3, p"))
        return Leitura((), 0, not vazia)

    def _vaga(
        self, cartao: LexborNode, id_: str, escopo: EscopoLogado, agora: datetime
    ) -> VagaColetada | None:
        linhas = _linhas(cartao)
        if not _ID.fullmatch(id_) or len(linhas) < 2 or not linhas[0] or not linhas[1]:
            return None
        local = linhas[2] if len(linhas) > 2 else ""
        modalidade = None
        if m := _LOCAL.fullmatch(local):
            local, modalidade = m[1], m[2]
        publicada = salario = None
        for linha in linhas[3:]:  # frase pessoal e o resto não casam e não vão a lugar nenhum
            if (data := _data_relativa(linha, agora)) is not None:
                publicada = publicada or data
            elif _SALARIO.search(linha):
                salario = salario or linha
        return VagaColetada(
            fonte=self.chave,
            escopo=escopo.id,
            url=f"https://www.linkedin.com/jobs/view/{id_}/",
            titulo=linhas[0],
            empresa=linhas[1],
            descricao_formato="html",
            id_externo=id_,
            locais=(local,) if local else (),
            modalidade_declarada=modalidade,
            salario_texto=salario,
            publicada_em=publicada,
        )

    def detalhar(self, captura: Captura, vaga: VagaColetada) -> VagaColetada | None:
        """Descrição de "About the job", contrato do topo e o `url` do `safety/go` (D136.16)."""
        arvore = LexborHTMLParser(captura.html)
        secao = arvore.css_first(_DESCRICAO)
        if secao is None:
            return None
        for sobra in secao.css('h2, [data-testid="expandable-text-button"]'):
            sobra.decompose()
        descricao = secao.html or ""
        caminho = urlsplit(vaga.url).path
        contrato = next(
            (
                texto
                for link in arvore.css("a[href]")
                if _caminho(link.attributes["href"] or "") == caminho
                and (texto := link.text(strip=True)) in _CONTRATOS
            ),
            vaga.contrato_declarado,
        )
        return dataclasses.replace(
            vaga,
            descricao=descricao,
            descricao_formato="html",
            contrato_declarado=contrato,
            url_candidatura=_candidatura(arvore),
        )


def _caminho(href: str) -> str | None:
    try:
        return urlsplit(href).path
    except ValueError:  # host com colchete sem par
        return None


def _candidatura(arvore: LexborHTMLParser) -> str | None:
    """Só o `url` do `safety/go`, sem `mt` nem `urlhash`; o que não é http(s) vira `None`."""
    link = arvore.css_first(", ".join(f'a[aria-label="{r}"]' for r in _ROTULOS_CANDIDATURA))
    href = (link.attributes.get("href") or "") if link is not None else ""
    if not href.startswith("https://www.linkedin.com/safety/go/"):
        return None
    try:
        url = parse_qs(urlsplit(href).query)["url"][0]
        confere_http(url, "url_candidatura")
    except KeyError, ValueError:
        return None
    return url
