import time

import pytest

from jobot.nucleo.texto import detectar_idioma, para_texto

PT = (
    "Estamos buscando uma pessoa para a nossa equipe de tecnologia. Você vai trabalhar com "
    "desenvolvimento de sistemas, participar das decisões do produto e ajudar a empresa a "
    "crescer. Não é preciso ter experiência com todas as ferramentas, mas queremos alguém que "
    "goste de aprender e que tenha vontade de colaborar com o time."
)
EN = (
    "We are looking for a person to join our engineering team. You will work on the design of "
    "the systems, take part in product decisions and help the company to grow. You do not need "
    "to have experience with all of the tools, but we want someone who likes to learn and who "
    "is willing to work with the team."
)
ES = (
    "Estamos buscando una persona para nuestro equipo de tecnología. Vas a trabajar en el "
    "desarrollo de los sistemas, participar en las decisiones del producto y ayudar a la "
    "empresa a crecer. No es necesario tener experiencia con todas las herramientas, pero "
    "queremos alguien que le guste aprender y que tenga ganas de colaborar con el equipo."
)


def test_script_vira_texto() -> None:
    bruto = "<p>Oi</p><script>alert(1)</script><style>p { color: red }</style><p>Tchau</p>"
    assert para_texto(bruto, "html") == "Oi\nTchau"


def test_script_escapado_tambem_some() -> None:
    assert para_texto("&lt;p&gt;Oi&lt;/p&gt;&lt;script&gt;alert(1)&lt;/script&gt;", "html") == "Oi"


def test_html_escapado_do_greenhouse() -> None:
    assert para_texto("&lt;p&gt;Oi&lt;/p&gt;", "html") == "Oi"


def test_html_decodifica_entidades_e_quebra_blocos() -> None:
    bruto = "<h2>Vaga &amp; cia</h2><ul><li>Python</li><li>SQL&nbsp;e&nbsp;mais</li></ul>a<br>b"
    assert para_texto(bruto, "html") == "Vaga & cia\nPython\nSQL e mais\na\nb"


def test_html_nao_mexe_em_menor_que_solto() -> None:
    assert para_texto("<p>salário &lt; 5 mil e 3 < 4</p>", "html") == "salário < 5 mil e 3 < 4"


def test_html_com_tag_sem_fechar_nao_levanta() -> None:
    assert para_texto("<p>Oi <b>mundo<script>x", "html") == "Oi mundo"


def test_markdown_perde_marcas() -> None:
    bruto = (
        "# Título\n\n**Negrito** e _itálico_ com `código`.\n\n"
        "- item um\n* item dois\n1. item três\n\n"
        "> citação\n\n[link](https://exemplo.com/x) ![img](a.png)\n\n```\nfeito_assim\n```\n\n---\n"
    )
    esperado = (
        "Título\nNegrito e itálico com código.\nitem um\nitem dois\nitem três\n"
        "citação\nlink img\nfeito_assim"
    )
    assert para_texto(bruto, "markdown") == esperado


def test_html_preserva_genericos_de_codigo() -> None:
    bruto = "<p>Experiência com List&lt;String&gt; e Map&lt;K,V&gt;</p>"
    assert para_texto(bruto, "html") == "Experiência com List<String> e Map<K,V>"


def test_html_escapado_duas_vezes_com_generico() -> None:
    assert para_texto("&lt;p&gt;List&amp;lt;String&amp;gt;&lt;/p&gt;", "html") == "List<String>"


def test_html_tag_desconhecida_fica_como_texto() -> None:
    assert para_texto("<p>use Result<T, E> e C#</p>", "html") == "use Result<T, E> e C#"


def test_markdown_preserva_genericos_de_codigo() -> None:
    bruto = "Use `List<String>` e Map<K,V>\n\n```\nList<String> x;\n```"
    assert para_texto(bruto, "markdown") == "Use List<String> e Map<K,V>\nList<String> x;"


def test_html_tags_do_word_e_obsoletas_somem() -> None:
    bruto = "<p>Oi</p><o:p></o:p><p>x</p><strike>y</strike> <big>z</big>"
    assert para_texto(bruto, "html") == "Oi\nx\ny z"


def test_html_escapado_com_tag_obsoleta() -> None:
    assert para_texto("&lt;strike&gt;x&lt;/strike&gt;", "html") == "x"


def test_html_oculta_conteudo_de_elementos_externos() -> None:
    bruto = (
        "<p>a</p><iframe src='http://x'>nao</iframe><svg onload=alert(1)><text>t</text></svg>"
        "<template><p>m</p></template><noscript>n</noscript><object data=x>o</object><p>b</p>"
    )
    assert para_texto(bruto, "html") == "a\nb"


def test_html_script_autofechado_esconde_o_conteudo() -> None:
    assert para_texto("<script/>alert(1)</script>t", "html") == "t"


def test_html_namespace_so_do_word_e_tag() -> None:
    bruto = "<p>std::vector<int> e <std::string></p>"
    assert para_texto(bruto, "html") == "std::vector<int> e <std::string>"


def test_markdown_linha_patologica_nao_trava() -> None:
    inicio = time.perf_counter()
    para_texto("*a " * 20000, "markdown")
    para_texto("[a " * 20000, "markdown")
    para_texto("a" + " " * 60000 + "b", "markdown")
    assert time.perf_counter() - inicio < 2


def test_markdown_com_html_solto_vira_texto() -> None:
    assert para_texto("**Oi** <b>mundo</b><script>x()</script>", "markdown") == "Oi mundo"


def test_markdown_mantem_snake_case() -> None:
    assert para_texto("use nome_da_variavel aqui", "markdown") == "use nome_da_variavel aqui"


def test_texto_so_arruma_espacos() -> None:
    assert para_texto("  a   b \n\n\n c<d> ", "texto") == "a b\nc<d>"


def test_idioma_pt_com_termos_em_ingles_continua_pt() -> None:
    texto = (
        "Estamos buscando uma pessoa para a nossa equipe de produto. Você vai trabalhar com "
        "backend, frontend, deploy e code review, participar do sprint planning e ajudar a "
        "empresa a crescer. Não é preciso ter experiência com todas as ferramentas."
    )
    assert detectar_idioma(texto) == "pt"


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        (PT, "pt"),
        (EN, "en"),
        (ES, "es"),
        ("", "outro"),
        ("Software Engineer", "outro"),
        ("Desenvolvedor de software para a nossa equipe", "outro"),
        (PT[:140] + " " + EN[:140], "outro"),
        ("12345 67890 !!!! ???? 11111 22222 33333 44444 55555 66666 77777 88888", "outro"),
    ],
)
def test_idioma(texto: str, esperado: str) -> None:
    assert detectar_idioma(texto) == esperado
