import hashlib
import importlib.util
import json
import time
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import aclosing
from pathlib import Path
from types import ModuleType
from typing import Any, Literal

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores.base import (
    ContextoColeta,
    Item,
    LimiteEscopo,
    ResultadoEscopo,
    juntar_paginas,
)
from jobot.nucleo.http import ClienteEducado, HttpEducado, Validadores
from jobot.nucleo.modelo import VagaColetada

MB = 1024 * 1024
RAIZ = Path(__file__).resolve().parents[2]


def _carregar() -> ModuleType:
    spec = importlib.util.spec_from_file_location("capturar_script", RAIZ / "scripts/capturar.py")
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


capturar = _carregar()


def _reduzir(conteudo: str | bytes, formato: str, fonte: str | None = None) -> bytes:
    bruto = conteudo.encode() if isinstance(conteudo, str) else conteudo
    saida: bytes = capturar.reduzir(bruto, formato, fonte)
    return saida


def test_reduzir_corta_para_5_itens() -> None:
    lista = [{"id": i, "titulo": f"Vaga {i}"} for i in range(12)]
    cortada = json.loads(_reduzir(json.dumps(lista), "json"))
    assert [v["id"] for v in cortada] == [0, 1, 2, 3, 4]


def test_reduzir_dicionario_corta_so_a_lista_principal() -> None:
    dado = {
        "total": 12,
        "jobs": [{"id": i, "tags": ["a", "b"]} for i in range(12)],
        "meta": {"paginas": [1, 2, 3, 4, 5, 6, 7]},
    }
    saida = json.loads(_reduzir(json.dumps(dado), "json"))
    assert len(saida["jobs"]) == 5
    assert saida["total"] == 12 and saida["jobs"][0]["tags"] == ["a", "b"]
    assert saida["meta"]["paginas"] == [1, 2, 3, 4, 5, 6, 7]  # só a maior lista é cortada
    aninhada = json.loads(_reduzir(json.dumps({"data": {"items": list(range(9))}}), "json"))
    assert aninhada["data"]["items"] == [0, 1, 2, 3, 4]
    curta = json.loads(_reduzir(json.dumps([1, 2, 3]), "json"))
    assert curta == [1, 2, 3]


def _vagas_com_lista_maior_dentro() -> dict[str, Any]:
    # a primeira vaga tem mais tags do que o feed tem vagas: a "maior lista" não é a das vagas
    vagas = [{"id": i, "tags": [f"t{n}" for n in range(30 if i == 0 else 2)]} for i in range(12)]
    return {"total": 12, "jobs": vagas}


@pytest.mark.parametrize("fonte", ["remotive", "himalayas"])
def test_reduzir_corta_a_lista_de_vagas_e_nao_a_maior_lista(fonte: str) -> None:
    saida = json.loads(_reduzir(json.dumps(_vagas_com_lista_maior_dentro()), "json", fonte))
    assert [v["id"] for v in saida["jobs"]] == [0, 1, 2, 3, 4]
    assert len(saida["jobs"][0]["tags"]) == 30  # as tags ficam inteiras


def test_fonte_sem_indicacao_corta_a_maior_lista() -> None:
    # caracterização: o comportamento de antes vale para fonte sem indicação (ou fonte nenhuma)
    for fonte in (None, "outra_fonte"):
        saida = json.loads(_reduzir(json.dumps(_vagas_com_lista_maior_dentro()), "json", fonte))
        assert len(saida["jobs"]) == 12 and len(saida["jobs"][0]["tags"]) == 5


def test_indicacao_que_nao_acha_a_lista_cai_na_maior_lista() -> None:
    sem_chave = {"outras": [{"id": i} for i in range(9)]}
    assert len(json.loads(_reduzir(json.dumps(sem_chave), "json", "remotive"))["outras"]) == 5
    nao_lista = {"jobs": "vazio", "outras": [{"id": i} for i in range(9)]}
    assert len(json.loads(_reduzir(json.dumps(nao_lista), "json", "remotive"))["outras"]) == 5


def test_reduzir_rss_corta_para_5_e_guarda_o_namespace() -> None:
    itens = "".join(
        f"<item><title>Vaga {i}</title><dc:date>2026-11-13</dc:date></item>" for i in range(8)
    )
    rss = (
        "<?xml version='1.0' encoding='UTF-8'?><rss version='2.0' "
        "xmlns:dc='http://purl.org/dc/elements/1.1/'><channel><title>t</title>"
        f"{itens}</channel></rss>"
    )
    saida = _reduzir(rss, "xml")
    assert len(ET.fromstring(saida).findall("./channel/item")) == 5
    assert b"dc:date" in saida and b"<title>t</title>" in saida


def test_reduzir_sitemap_com_namespace_padrao() -> None:
    urls = "".join(f"<url><loc>https://exemplo.test/v/{i}</loc></url>" for i in range(9))
    mapa = f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
    saida = _reduzir(mapa, "xml")
    assert len(ET.fromstring(saida)) == 5
    assert b'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"' in saida


def test_reduzir_html_corta_a_lista_e_o_json_embutido() -> None:
    itens = "".join(f"<li class='vaga'>Vaga {i}</li>" for i in range(9))
    jobs = json.dumps({"jobs": [{"id": i} for i in range(9)]})
    pagina = (
        f"<html><head><style>x{{}}</style></head><body><ul>{itens}</ul>"
        f"<script>var x = 1;</script>"
        f'<script type="application/ld+json">{jobs}</script></body></html>'
    )
    saida = _reduzir(pagina, "html").decode()
    assert saida.count("<li") == 5 and "Vaga 4" in saida and "Vaga 5" not in saida
    assert "<style" not in saida and "var x" not in saida
    embutido = saida.split('ld+json">')[1].split("</script>")[0]
    assert len(json.loads(embutido)["jobs"]) == 5


def test_reduzir_respeita_50_kb() -> None:
    limite: int = capturar.MAX_BYTES
    grande = [{"id": i, "titulo": f"Vaga {i}", "descricao": "texto " * 8000} for i in range(9)]
    saida = _reduzir(json.dumps(grande), "json")
    itens = json.loads(saida)
    assert len(saida) <= limite
    assert [v["id"] for v in itens] == [0, 1, 2, 3, 4]
    assert itens[0]["titulo"] == "Vaga 0"  # o encolhimento só mexe em texto longo
    itens_xml = "".join(f"<item><t>{i}</t><d>{'texto ' * 8000}</d></item>" for i in range(9))
    xml = _reduzir(f"<?xml version='1.0'?><rss><channel>{itens_xml}</channel></rss>", "xml")
    assert len(xml) <= limite and len(ET.fromstring(xml).findall("./channel/item")) == 5


def test_reduzir_recusa_o_que_nao_cabe_em_50_kb() -> None:
    sem_lista = {f"chave{i}": "valor" for i in range(8000)}
    with pytest.raises(ValueError, match="50 KB"):
        _reduzir(json.dumps(sem_lista), "json")
    with pytest.raises(ValueError, match="50 KB"):
        _reduzir("<html><body><p>" + "texto " * 12000 + "</p></body></html>", "html")


def test_limpar_troca_email_telefone_e_nome() -> None:
    texto = json.dumps(
        {
            "user": {"login": "maria-silva", "id": 777},
            "by": "joao",
            "recruiter": {"nome": "Ana Souza"},
            "autor": "Pedro",
            "descricao": "Fale com rh@empresa.com.br, +55 11 98765-4321, (11) 98765-4321 "
            "ou 555-123-4567. CPF 123.456.789-09 ou 52998224725.",
            "titulo": "Dev",
        }
    )
    saida: str = capturar.limpar_pessoais(texto)
    for sobra in ("maria", "joao", "Ana", "Pedro", "rh@", "98765", "555-123", "789-09", "5299822"):
        assert sobra not in saida, sobra
    dado = json.loads(saida)
    assert dado["titulo"] == "Dev" and dado["user"]["login"] == "exemplo"
    assert dado["user"]["id"] == 0
    assert "@exemplo.invalid" in saida  # troca por valor de exemplo, não apaga o campo
    assert capturar.limpar_pessoais(saida) == saida
    assert capturar.achar_pessoais(saida) == []
    assert capturar.achar_pessoais(texto)


def test_limpar_e_achar_em_texto_longo_sao_rapidos() -> None:
    # regex de e-mail sem âncora varre cada início de palavra até o fim: quadrático em "aaaa..."
    texto = "a" * 100_000 + " " + "1" * 100_000 + " " + "<author>" * 2000
    inicio = time.monotonic()
    capturar.limpar_pessoais(texto)
    capturar.achar_pessoais(texto)
    assert time.monotonic() - inicio < 5


def test_limpar_xml_e_texto_solto() -> None:
    xml = (
        "<item><dc:creator><![CDATA[Maria Silva]]></dc:creator><author>joao@x.com (Joao)</author>"
        "<description>Ligue 11 98765-4321 para rh@x.com</description></item>"
    )
    saida: str = capturar.limpar_pessoais(xml)
    for sobra in ("Maria", "Joao", "joao@", "98765", "rh@"):
        assert sobra not in saida, sobra
    assert "<description>" in saida and capturar.achar_pessoais(saida) == []


def test_limpar_nao_estraga_numeros_comuns() -> None:
    texto = (
        "2026-11-13T12:00:00Z 1700000000 1700000000000 4012345678 R$ 10.000,00 - 20.000,00 "
        "Estágio 2021 - 6 horas 12345678901 versão 1.2.3 vaga 123-456"
    )
    assert capturar.limpar_pessoais(texto) == texto
    assert capturar.achar_pessoais(texto) == []


@pytest.mark.parametrize(
    "texto",
    [
        "<pubDate>Fri, 13 Nov 2026 12:00:00 +0000</pubDate>",
        "Fri, 13 Nov 2026 12:00:00 +0000",
        "2026-11-13T12:00:00.000+0000",
        "+15000 vagas abertas",
        "Wed Oct 10 20:19:24 +0000 2018",
        "2018-10-10T20:19:24 +0000 2018",
    ],
)
def test_limpar_nao_confunde_fuso_ou_quantidade_com_telefone(texto: str) -> None:
    assert capturar.limpar_pessoais(texto) == texto
    assert capturar.achar_pessoais(texto) == []


@pytest.mark.parametrize(
    ("texto", "trecho"),
    [
        ("ligue +5511987654321 agora", "98765"),
        ('<a href="tel:+5511987654321">', "98765"),
        ("+1 415 555 2671", "2671"),
        ("+44 20 7946 0958", "0958"),
        ("+49 89 123456", "123456"),
    ],
)
def test_limpar_troca_telefone_internacional_inteiro(texto: str, trecho: str) -> None:
    # troca pela metade deixa um dígito ("+55 11 90000-00001"), o detector recusa a captura
    saida: str = capturar.limpar_pessoais(texto)
    assert trecho not in saida
    assert capturar.achar_pessoais(saida) == []


def test_limpar_e_achar_mais_seguido_de_muitos_digitos_sao_rapidos() -> None:
    # sem o grupo atômico, cada "+" tenta toda divisão dos 30 dígitos: ~6 s em 500 KB
    texto = ("+" + "1" * 30 + " ") * 16_500
    inicio = time.monotonic()
    capturar.limpar_pessoais(texto)
    capturar.achar_pessoais(texto)
    assert time.monotonic() - inicio < 2


def test_limpar_troca_telefone_logo_depois_de_um_horario() -> None:
    texto = "Atendimento 08:00 +55 11 98765-4321 ou 08:00:30 +55 11 98765-4321"
    assert "98765" not in capturar.limpar_pessoais(texto)
    assert capturar.achar_pessoais(texto)


def test_limpar_troca_telefone_que_parece_fuso_e_ano_depois_de_horario() -> None:
    # "2034" é prefixo de fixo em SP: o grupo de dígitos depois do "ano" mostra que é telefone
    texto = "às 10:00 +5511 2034-5678"
    saida: str = capturar.limpar_pessoais(texto)
    assert "5678" not in saida
    assert capturar.achar_pessoais(saida) == []
    assert capturar.achar_pessoais(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "ligue 11 9 8765-4321 já",
        "(11) 9 8765-4321",
        "(11) 9.8765-4321",
        "WhatsApp: (21) 9 8765-4321",
        "+55 11 9 8765-4321",
        "+55 (11) 9.8765-4321",
        "11.9.8765.4321",
    ],
)
def test_limpar_e_achar_telefone_com_o_9_separado(texto: str) -> None:
    # o detector usa a mesma regex: conferir só achar_pessoais(saida) não prova a limpeza
    saida: str = capturar.limpar_pessoais(texto)
    assert "8765" not in saida
    assert capturar.achar_pessoais(saida) == []
    assert capturar.achar_pessoais(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "9 vagas em 2026, CEP 01310-100, das 09:00 às 18:00",
        "CNPJ 12.345.678/0001-90",
        "R$ 9.000,00 a R$ 12.000,00 por mês, 40 horas",
        "Prazo 13/11/2026, 9 dias, vaga 123-456 e id 98765",
        "turma 12 9 1234 e lote 2026 9 2027",
        "+9 vagas, nota 9.5, 2026-11-13 9:00",
    ],
)
def test_limpar_nao_confunde_9_solto_com_telefone(texto: str) -> None:
    assert capturar.limpar_pessoais(texto) == texto
    assert capturar.achar_pessoais(texto) == []


@pytest.mark.parametrize("texto", ["ligue: 11 987654321", "11 987654321", "011 987654321"])
def test_limpar_e_achar_celular_com_ddd_e_numero_colado(texto: str) -> None:
    saida: str = capturar.limpar_pessoais(texto)
    assert "8765" not in saida
    assert capturar.achar_pessoais(saida) == []
    assert capturar.achar_pessoais(texto)


@pytest.mark.parametrize(
    "texto",
    [
        '<a href="https://wa.me/5511987654321">fale</a>',
        "https://api.whatsapp.com/send?phone=5511987654321",
        '<a href="tel:011987654321">',
        '{"x": "wa.me/5511987654321"}',
        "Tel:11987654321",
    ],
)
def test_limpar_e_achar_telefone_colado_depois_de_wa_me_tel_ou_phone(texto: str) -> None:
    saida: str = capturar.limpar_pessoais(texto)
    assert "8765" not in saida
    assert capturar.achar_pessoais(saida) == []
    assert capturar.achar_pessoais(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "vaga id=5511987654321 e lote 12 812345678",
        "hotel:1234567890 e phone=12345",
        "https://wa.me/message/ABC123 e tel:0800",
        "+" + "1" * 30,  # passa dos 15 dígitos do E.164: não é telefone e nada sai pela metade
    ],
)
def test_limpar_nao_confunde_numero_colado_sem_marcador_com_telefone(texto: str) -> None:
    assert capturar.limpar_pessoais(texto) == texto
    assert capturar.achar_pessoais(texto) == []


def test_limpar_e_achar_json_embutido_em_html() -> None:
    dado = {"props": {"recruiter": {"name": "Ana Souza"}, "titulo": "Dev"}}
    pagina = (
        "<html><body><script id='__NEXT_DATA__' type='application/json'>"
        f"{json.dumps(dado)}</script></body></html>"
    )
    assert capturar.achar_pessoais(pagina)  # o detector olha o JSON embutido
    saida: str = capturar.limpar_pessoais(pagina)
    assert "Ana" not in saida and "Souza" not in saida
    assert "Dev" in saida and capturar.achar_pessoais(saida) == []
    assert capturar.limpar_pessoais(saida) == saida


def test_reduzir_html_anonimiza_o_json_embutido() -> None:
    dado = {"jobs": [{"id": 1}], "contact": {"name": "Ana Souza"}}
    embutido = json.dumps(dado)
    pagina = f'<html><body><script type="application/ld+json">{embutido}</script></body></html>'
    assert "Ana" not in _reduzir(pagina, "html").decode()


def test_limpar_json_com_numero_que_parece_cpf_continua_json() -> None:
    texto = json.dumps({"id": 52998224725, "descricao": "CPF 52998224725"})
    saida: str = capturar.limpar_pessoais(texto)
    dado = json.loads(saida)  # trocar o número no texto geraria 00000000000, que não é JSON
    assert dado["id"] == 52998224725 and "5299822" not in dado["descricao"]
    assert capturar.achar_pessoais(saida) == []
    assert json.loads(_reduzir(saida, "json"))["id"] == 52998224725


def test_limpar_json_pega_campo_sensivel_pelo_nome_mesmo_em_numero() -> None:
    texto = json.dumps(
        {
            "cpf": 52998224725,
            "telefone": 5511987654321,
            "contato": {"phone": "+1 415 555 0100", "whatsapp": 11987654321},
            "email": "rh@empresa.com.br",
            "id": 52998224725,
        }
    )
    assert capturar.achar_pessoais(texto)  # o número no campo cpf não passa batido
    dado = json.loads(capturar.limpar_pessoais(texto))
    assert dado["cpf"] == 0 and dado["telefone"] == 0 and dado["contato"]["whatsapp"] == 0
    assert dado["contato"]["phone"] == "exemplo" and dado["email"] == "exemplo"
    assert dado["id"] == 52998224725  # o id que só por acaso é CPF válido continua intocado
    assert capturar.achar_pessoais(json.dumps(dado)) == []


def test_limpar_e_achar_dado_codificado_no_html() -> None:
    pagina = (
        '<p>11&nbsp;98765-4321 ou 11&#160;98765-4321</p><a href="mailto:rh%40empresa.com.br">rh</a>'
    )
    assert capturar.achar_pessoais(pagina)
    saida: str = capturar.limpar_pessoais(pagina)
    for sobra in ("98765", "rh%40", "empresa"):
        assert sobra not in saida, sobra
    assert capturar.achar_pessoais(saida) == []
    assert capturar.limpar_pessoais(saida) == saida


def test_achar_olha_tambem_o_texto_decodificado() -> None:
    assert capturar.achar_pessoais("<p>&#43;55 11 98765-4321</p>")  # &#43; é "+"
    assert capturar.achar_pessoais('<a href="tel:%2B5511987654321">ligar</a>')
    assert capturar.achar_pessoais("<p>rh&#64;empresa.com.br</p>")
    assert capturar.achar_pessoais("<p>Tom &amp; Jerry, 100% &lt;b&gt;</p>") == []


def test_limpar_html_nao_troca_numero_que_parece_cpf_no_json_embutido() -> None:
    pagina = (
        '<html><body><p>CPF 52998224725</p><script type="application/json">'
        '{"id": 52998224725}</script></body></html>'
    )
    saida: str = capturar.limpar_pessoais(pagina)
    assert "<p>CPF 00000000000</p>" in saida and '{"id": 52998224725}' in saida
    assert capturar.achar_pessoais(saida) == []
    assert "52998224725" in _reduzir(saida, "html").decode()  # o script não é descartado


def test_limpar_script_json_ilegivel_continua_limpo_por_texto() -> None:
    pagina = '<script type="application/json">{"a": rh@empresa.com.br, 98765</script>'
    saida: str = capturar.limpar_pessoais(pagina)
    assert "rh@empresa" not in saida and capturar.achar_pessoais(saida) == []


class _SemValidadores:
    def ler(self, url: str) -> Validadores | None:
        return None


class ColetorFalso:
    chave = "fonte_falsa"
    nome = "Fonte falsa"
    leva: Literal["A", "B"] = "A"
    hosts = ("exemplo.test",)
    credito_obrigatorio = False
    intervalo_min = None
    max_pedidos = None
    espera_s = 1.0
    por_escopo: Mapping[str, LimiteEscopo] = {}

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        return ("todas",)

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        async def paginas() -> AsyncIterator[Sequence[Item]]:
            for pagina in (1, 2):
                await http.pedir(
                    "GET", f"https://exemplo.test/vagas/{escopo}", params={"p": str(pagina)}
                )
                yield ()

        return await juntar_paginas(http, paginas())

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        return None

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        return {}


def _vagas_com_dados_pessoais() -> dict[str, Any]:
    return {
        "vagas": [
            {
                "id": i,
                "titulo": f"Vaga {i}",
                "user": {"login": "maria-silva"},
                "descricao": "Fale com rh@empresa.com.br ou (11) 98765-4321. CPF 123.456.789-09",
            }
            for i in range(8)
        ]
    }


@pytest.mark.anyio
async def test_capturar_grava_exemplo_reduzido_sem_dado_pessoal_e_com_meta(tmp_path: Path) -> None:
    pedidos: list[httpx.Request] = []

    def responder(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        return httpx.Response(
            200,
            json=_vagas_com_dados_pessoais(),
            headers={"ETag": '"abc"', "Set-Cookie": "sessao=1", "X-Interno": "nao"},
        )

    relogio = RelogioFalso()
    cliente = ClienteEducado(httpx.MockTransport(responder), relogio, _SemValidadores(), "9.9.9")
    try:
        caminho: Path = await capturar.capturar(
            ColetorFalso(), None, "normal", tmp_path, cliente, relogio, "9.9.9"
        )
    finally:
        await cliente.fechar()

    pasta = tmp_path / "fonte_falsa"
    assert caminho == pasta / "normal.json"
    texto = caminho.read_text(encoding="utf-8")
    assert len(json.loads(texto)["vagas"]) == 5
    for sobra in ("maria", "@empresa", "98765", "789-09"):
        assert sobra not in texto.lower(), sobra
    meta = json.loads((pasta / "normal.meta.json").read_text(encoding="utf-8"))
    assert meta["url"] == "https://exemplo.test/vagas/todas?p=1"
    assert meta["codigo"] == 200 and meta["versao"] == "9.9.9"
    assert meta["data"].startswith("2026-11-13T12:00:00")
    assert meta["sha256"] == hashlib.sha256(caminho.read_bytes()).hexdigest()
    assert meta["cabecalhos"]["ETag"] == '"abc"'
    assert "Set-Cookie" not in meta["cabecalhos"] and "X-Interno" not in meta["cabecalhos"]
    assert len(pedidos) == 1  # um pedido só: a segunda página não é buscada
    assert capturar.problemas(pasta) == []


class ColetorDeSitemap(ColetorFalso):
    chave = "mapa_falso"

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        async def paginas() -> AsyncIterator[Sequence[Item]]:
            async with aclosing(
                http.ler_em_fluxo("https://exemplo.test/mapa.xml", teto_bytes=MB)
            ) as f:
                async for _ in f:
                    pass
            yield ()

        return await juntar_paginas(http, paginas())


@pytest.mark.anyio
async def test_capturar_fonte_em_fluxo_guarda_o_sitemap_reduzido(tmp_path: Path) -> None:
    urls = "".join(f"<url><loc>https://exemplo.test/v/{i}</loc></url>" for i in range(9))
    mapa = f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'

    def responder(pedido: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=mapa,
            headers={"ETag": '"mapa1"', "Last-Modified": "Fri, 13 Nov 2026 12:00:00 GMT"},
        )

    relogio = RelogioFalso()
    cliente = ClienteEducado(httpx.MockTransport(responder), relogio, _SemValidadores(), "9.9.9")
    try:
        caminho: Path = await capturar.capturar(
            ColetorDeSitemap(), "x", "normal", tmp_path, cliente, relogio, "9.9.9"
        )
    finally:
        await cliente.fechar()
    assert caminho.name == "normal.xml"
    assert len(ET.fromstring(caminho.read_bytes())) == 5
    assert capturar.problemas(tmp_path / "mapa_falso") == []
    meta = json.loads((tmp_path / "mapa_falso" / "normal.meta.json").read_text(encoding="utf-8"))
    assert meta["cabecalhos"]["ETag"] == '"mapa1"'
    assert meta["cabecalhos"]["Last-Modified"] == "Fri, 13 Nov 2026 12:00:00 GMT"


class ColetorComEmailNaUrl(ColetorFalso):
    chave = "url_com_email"

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        async def paginas() -> AsyncIterator[Sequence[Item]]:
            await http.pedir("GET", "https://exemplo.test/v", params={"q": "rh@empresa.com.br"})
            yield ()

        return await juntar_paginas(http, paginas())


@pytest.mark.anyio
async def test_capturar_nao_grava_nada_se_o_meta_tem_dado_pessoal(tmp_path: Path) -> None:
    def responder(pedido: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"vagas": [{"id": 1}]})

    relogio = RelogioFalso()
    cliente = ClienteEducado(httpx.MockTransport(responder), relogio, _SemValidadores(), "9.9.9")
    try:
        with pytest.raises(RuntimeError, match="pessoal"):
            await capturar.capturar(
                ColetorComEmailNaUrl(), None, "normal", tmp_path, cliente, relogio, "9.9.9"
            )
    finally:
        await cliente.fechar()
    assert list(tmp_path.rglob("*")) == []  # nem a pasta da fonte


@pytest.mark.anyio
async def test_capturar_recusa_nome_de_caso_que_sai_da_pasta(tmp_path: Path) -> None:
    def responder(pedido: httpx.Request) -> httpx.Response:
        raise AssertionError("não devia chegar à rede")

    relogio = RelogioFalso()
    cliente = ClienteEducado(httpx.MockTransport(responder), relogio, _SemValidadores(), "9.9.9")
    try:
        for caso in ("../fora", "a.editado", "", "A b"):
            with pytest.raises(ValueError, match="caso"):
                await capturar.capturar(
                    ColetorFalso(), None, caso, tmp_path, cliente, relogio, "9.9.9"
                )
    finally:
        await cliente.fechar()
    assert list(tmp_path.iterdir()) == []


def test_main_fonte_desconhecida_devolve_1_e_lista_as_fontes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert capturar.main(["nao_existe", "--caso", "normal"]) == 1
    assert "nao_existe" in capsys.readouterr().err


class ColetorHtml(ColetorFalso):
    chave = "html_falso"

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        async def paginas() -> AsyncIterator[Sequence[Item]]:
            await http.pedir("GET", "https://exemplo.test/v")
            yield ()

        return await juntar_paginas(http, paginas())


@pytest.mark.anyio
async def test_capturar_html_limpa_o_que_o_parser_decodifica(tmp_path: Path) -> None:
    pagina = (
        "<html><body><p>rh&#64;empresa.com.br</p><p>11&nbsp;98765-4321</p>"
        '<a href="mailto:rh%40empresa.com.br">rh</a></body></html>'
    )

    def responder(pedido: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=pagina, headers={"Content-Type": "text/html"})

    relogio = RelogioFalso()
    cliente = ClienteEducado(httpx.MockTransport(responder), relogio, _SemValidadores(), "9.9.9")
    try:
        caminho: Path = await capturar.capturar(
            ColetorHtml(), None, "normal", tmp_path, cliente, relogio, "9.9.9"
        )
    finally:
        await cliente.fechar()
    texto = caminho.read_text(encoding="utf-8")
    assert caminho.suffix == ".html" and "<p>" in texto
    for sobra in ("empresa", "98765", "rh%40", "rh@"):
        assert sobra not in texto, sobra
    assert capturar.problemas(tmp_path / "html_falso") == []


@pytest.mark.anyio
async def test_capturar_nao_deixa_nada_na_pasta_se_a_conferencia_falha(tmp_path: Path) -> None:
    pasta = tmp_path / "fonte_falsa"
    pasta.mkdir()
    (pasta / "outro.json").write_text("{}", encoding="utf-8")  # caso sem meta: a pasta reprova

    def responder(pedido: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"vagas": [{"id": 1}]})

    relogio = RelogioFalso()
    cliente = ClienteEducado(httpx.MockTransport(responder), relogio, _SemValidadores(), "9.9.9")
    try:
        with pytest.raises(RuntimeError, match="outro.json"):
            await capturar.capturar(
                ColetorFalso(), None, "normal", tmp_path, cliente, relogio, "9.9.9"
            )
    finally:
        await cliente.fechar()
    assert [p.name for p in pasta.iterdir()] == ["outro.json"]  # nem o caso novo, nem o meta


class ColetorRemotiveFalso(ColetorFalso):
    chave = "remotive"


@pytest.mark.anyio
async def test_capturar_corta_a_lista_indicada_pela_chave_da_fonte(tmp_path: Path) -> None:
    relogio = RelogioFalso()
    cliente = ClienteEducado(
        httpx.MockTransport(lambda _: httpx.Response(200, json=_vagas_com_lista_maior_dentro())),
        relogio,
        _SemValidadores(),
        "9.9.9",
    )
    try:
        caminho: Path = await capturar.capturar(
            ColetorRemotiveFalso(), None, "normal", tmp_path, cliente, relogio, "9.9.9"
        )
    finally:
        await cliente.fechar()
    saida = json.loads(caminho.read_text(encoding="utf-8"))
    assert len(saida["jobs"]) == 5 and len(saida["jobs"][0]["tags"]) == 30
