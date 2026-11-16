"""Molde do leitor com login: lista em HTML, escopo por termo, próxima por link, descrição na vaga.

Ponto de partida para um site com login (guia `docs/site-novo.md`). Mora em `tests/apoio` para
não virar fonte: não está em `LEITORES`. Na cópia, cada linha com `# MUDE:` muda.

O leitor só diz o que leu: o estado do escopo sai de `estado_do_escopo`, e o desafio anti-robô
(CAPTCHA, Cloudflare) é achado pelo navegador. Página de login ou de bloqueio = "falhou"; o leitor
nunca tenta outra rota.
"""

import dataclasses
from collections.abc import Sequence
from urllib.parse import SplitResult, quote_plus, urljoin, urlsplit, urlunsplit

from selectolax.lexbor import LexborHTMLParser, LexborNode

from jobot.nucleo.coletores.base import ContextoColeta
from jobot.nucleo.leitores.base import Captura, EscopoLogado, Leitura
from jobot.nucleo.modelo import VagaColetada

CHAVE = "molde_logado"  # MUDE: `<site>_logado` (o sufixo é obrigatório no registro)
NOME = "Molde com login"  # MUDE: o nome que o painel mostra
_HOST = "vagas.exemplo.invalid"  # MUDE: o host do site
URL_LOGIN = f"https://{_HOST}/entrar"  # MUDE: onde a pessoa entra com a própria senha
URL_ENTRADA = f"https://{_HOST}/vagas"  # MUDE: a primeira página aberta depois do login
PREFIXOS_LOGIN: tuple[str, ...] = (f"{_HOST}/entrar",)  # MUDE: host + caminho de cada entrada
_LISTA = "ul.vagas"  # MUDE: a lista de vagas (presente e vazia = busca sem resultado)
_CARTAO = "ul.vagas > li"  # MUDE: cada vaga da lista
_PROXIMA = 'a[rel="next"]'  # MUDE: o link da próxima página
_MARCA_LOGADA = 'a[href="/sair"]'  # MUDE: algo que só aparece logado e não depende de vaga
_MARCA_BLOQUEIO = "#bloqueio"  # MUDE: a página de bloqueio própria do site
_DESCRICAO = "section.descricao"  # MUDE: a descrição na página da vaga


def _no_site(base: str, href: str) -> SplitResult | None:
    """O `href` resolvido contra `base`, só se for `https` em `_HOST` exato; senão `None`."""
    try:
        partes = urlsplit(urljoin(base, href))
    except ValueError:  # host com colchete sem par
        return None
    # netloc exato: recusa porta e `conta@` na frente do host
    return partes if partes.scheme == "https" and partes.netloc == _HOST else None


def _texto(cartao: LexborNode, seletor: str) -> str:
    no = cartao.css_first(seletor)
    return no.text(strip=True) if no is not None else ""


def _vaga(cartao: LexborNode, base: str, escopo: EscopoLogado) -> VagaColetada | None:
    """Uma vaga da lista, ou `None` se faltar título, empresa ou link para o próprio site."""
    link = cartao.css_first("a.titulo")  # MUDE: o link com o título
    partes = _no_site(base, link.attributes.get("href") or "") if link is not None else None
    titulo, empresa = _texto(cartao, "a.titulo"), _texto(cartao, ".empresa")  # MUDE: campos
    if partes is None or not titulo or not empresa:
        return None
    local = _texto(cartao, ".local")  # MUDE: o campo do local, se houver
    return VagaColetada(
        fonte=CHAVE,
        escopo=escopo.id,
        url=urlunsplit(("https", _HOST, partes.path, "", "")),  # canônica: sem query nem âncora
        titulo=titulo,
        empresa=empresa,
        descricao_formato="html",
        locais=(local,) if local else (),
    )


class MoldeLogado:
    chave = CHAVE
    nome = NOME
    hosts: tuple[str, ...] = (_HOST,)
    url_login = URL_LOGIN
    url_entrada = URL_ENTRADA
    prefixos_login = PREFIXOS_LOGIN
    respostas: tuple[str, ...] = ()  # MUDE: hosts de JSON a guardar, se o site usar
    campos_conta: tuple[str, ...] = ("#conta",)  # MUDE: onde o nome da conta aparece
    rolar = False  # MUDE: `True` se a lista só carrega rolando
    lista_tem_descricao = False
    lista_exaustiva = False  # a vaga ausente só fecha depois da janela parcial

    def escopos(self, ctx: ContextoColeta) -> Sequence[EscopoLogado]:
        """Um escopo por termo, sem espaço nas bordas, sem vazio e sem repetido."""
        termos = dict.fromkeys(t for t in (t.strip() for t in ctx.termos) if t)
        # MUDE: o endereço de busca do site
        return [EscopoLogado(t, f"https://{_HOST}/busca?q={quote_plus(t)}") for t in termos]

    def _no_login(self, url: str) -> bool:
        partes = urlsplit(url)
        return f"{partes.hostname or ''}{partes.path}".startswith(self.prefixos_login)

    def e_login(self, captura: Captura) -> bool:
        return self._no_login(captura.url)

    def pagina_logada(self, html: str, url: str) -> bool:
        if self._no_login(url):
            return False
        arvore = LexborHTMLParser(html)
        for terceiro in arvore.css(_DESCRICAO):  # link na descrição da vaga não é sessão
            terceiro.decompose()
        return arvore.css_first(_MARCA_LOGADA) is not None

    def pagina_bloqueada(self, html: str, url: str) -> bool:
        return LexborHTMLParser(html).css_first(_MARCA_BLOQUEIO) is not None

    def proxima(self, captura: Captura) -> str | None:
        link = LexborHTMLParser(captura.html).css_first(_PROXIMA)
        partes = (
            _no_site(captura.url, link.attributes.get("href") or "") if link is not None else None
        )
        if partes is None:
            return None
        proxima = urlunsplit(partes._replace(fragment=""))
        # o laço do executor não guarda URLs vistas: o link para a própria página giraria
        propria = urlunsplit(urlsplit(captura.url)._replace(fragment=""))
        return None if proxima == propria else proxima

    def ler(self, captura: Captura, escopo: EscopoLogado) -> Leitura:
        arvore = LexborHTMLParser(captura.html)
        if arvore.css_first(_LISTA) is None:  # login, erro ou o site mudou
            return Leitura((), 0, True)
        vagas: list[VagaColetada] = []
        pulados = 0
        for cartao in arvore.css(_CARTAO):
            vaga = _vaga(cartao, captura.url, escopo)
            if vaga is None:
                pulados += 1
            else:
                vagas.append(vaga)
        return Leitura(tuple(vagas), pulados, bool(pulados) and not vagas)

    def detalhar(self, captura: Captura, vaga: VagaColetada) -> VagaColetada | None:
        secao = LexborHTMLParser(captura.html).css_first(_DESCRICAO)
        if secao is None:
            return None
        return dataclasses.replace(vaga, descricao=secao.html or "", descricao_formato="html")


LEITOR = MoldeLogado()
