"""A macro do componente de progresso no corpo de uma tela (plano T252; desenho 5.9)."""

import re

from jobot.banco.andamento import FonteAndamento
from jobot.painel import i18n, seguranca
from jobot.painel.progresso import Progresso

USO = (
    '{% from "execucao/_progresso.html" import progresso with context %}'
    '{{ progresso(p) }}{{ progresso(p, corpo=True, base="pronto") }}'
)
PROG = Progresso(
    False,
    42.0,
    "coleta",
    1,
    3,
    ("gupy",),
    None,
    (FonteAndamento("gupy", "lendo", 1, 3, None, None),),
)


def _render() -> str:
    def t(chave: str, **params: object) -> str:
        return i18n.t("pt", chave, **params)

    return seguranca.TEMPLATES.env.from_string(USO).render(p=PROG, t=t)


def test_corpo_tem_ids_proprios_e_botao_com_texto() -> None:
    html = _render()
    ids = re.findall(r'\bid="([^"]+)"', html)
    assert len(ids) == len(set(ids)), ids  # a barra e o corpo na mesma página
    assert {"pronto-preenchimento", "pronto-ver", "pronto-detalhes"} <= set(ids)
    botao = re.search(r'<button[^>]*id="pronto-ver"[^>]*>([^<]*)</button>', html)
    assert botao, html
    assert botao.group(1) == i18n.t("pt", "execucao.etapa.ver_detalhes")
    assert 'class="progresso-ver-texto"' in botao.group(0)
    assert 'popovertarget="pronto-detalhes"' in botao.group(0)
    assert f'data-ocultar="{i18n.t("pt", "execucao.etapa.ocultar_detalhes")}"' in botao.group(0)
    assert re.search(r'class="progresso progresso-corpo"', html)
