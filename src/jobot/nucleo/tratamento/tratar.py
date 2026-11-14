from dataclasses import fields, replace

from jobot.nucleo.modelo import Local, VagaColetada, VagaTratada
from jobot.nucleo.texto import detectar_idioma, para_texto
from jobot.nucleo.tratamento.estagio import ler_requisitos
from jobot.nucleo.tratamento.locais import ler_locais
from jobot.nucleo.tratamento.rotulos import VERSAO_REGRAS, fonte_so_no_brasil, rotular
from jobot.nucleo.tratamento.salario import ler_salario
from jobot.nucleo.url import canonica, hash_url


def _com_pais_da_fonte(fonte: str, locais: tuple[Local, ...]) -> tuple[Local, ...]:
    """Fonte que só publica vaga no Brasil (A77): sem país escrito em nenhum local, o país é BR."""
    # shortcut: fonte em so_brasil cujo local não traz país (Gupy, InHire, Abler, Cia de Talentos)
    # carimba BR em vaga de fora com cidade fora das listas, e a Sólides com país fora da tabela
    # de países também; melhorar quando o coletor trouxer o país e a tabela crescer.
    if not fonte_so_no_brasil(fonte) or any(local.pais for local in locais):
        return locais
    return tuple(dict.fromkeys(replace(local, pais="BR") for local in locais or (Local(),)))


def tratar(v: VagaColetada) -> VagaTratada:
    """Monta a vaga tratada: texto, idioma, locais, rótulos, salário e estágio (desenho 10)."""
    texto = para_texto(v.descricao, v.descricao_formato)
    idioma = detectar_idioma(texto)
    locais = _com_pais_da_fonte(v.fonte, ler_locais(v.locais))
    rotulos = rotular(v, texto, locais)
    url_canonica = canonica(v.url)
    campos = {f.name: getattr(v, f.name) for f in fields(v) if f.name != "locais"}
    return VagaTratada(
        **campos,
        locais=locais,
        url_canonica=url_canonica,
        url_hash=hash_url(url_canonica),
        descricao_texto=texto,
        idioma=idioma,
        area=rotulos.area,
        nivel=rotulos.nivel,
        modalidade=rotulos.modalidade,
        contrato=rotulos.contrato,
        avisos=rotulos.avisos,
        salario=ler_salario(v.salario_texto, v.salario_estruturado, idioma),
        requisitos_estagio=ler_requisitos(texto),
        versao_regras=VERSAO_REGRAS,
    )
