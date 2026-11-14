from typing import Any

from jobot.nucleo.encaixe import _arredondar, calcular
from jobot.nucleo.modelo import (
    Aviso,
    Busca,
    Local,
    Modalidade,
    Nivel,
    Salario,
    VagaTratada,
)

SP = Local(cidade="São Paulo", uf="SP", pais="BR")
CAMPINAS = Local(cidade="Campinas", uf="SP", pais="BR")
RECIFE = Local(cidade="Recife", uf="PE", pais="BR")


def _tratada(**campos: Any) -> VagaTratada:
    base: dict[str, Any] = {
        "fonte": "remotive",
        "escopo": "",
        "url": "https://exemplo.com/vaga/1",
        "titulo": "Desenvolvedor Backend",
        "empresa": "Acme",
        "descricao_formato": "texto",
        "descricao": "",
        "id_externo": None,
        "url_candidatura": None,
        "modalidade_declarada": None,
        "contrato_declarado": None,
        "salario_texto": None,
        "salario_estruturado": None,
        "publicada_em": None,
        "prazo": None,
        "inicio": None,
        "etiquetas": (),
        "url_canonica": "https://exemplo.com/vaga/1",
        "url_hash": "abc",
        "descricao_texto": "Vaga de backend em Python.",
        "idioma": "pt",
        "locais": (SP,),
        "area": "tecnologia",
        "nivel": Nivel.JUNIOR,
        "modalidade": Modalidade.PRESENCIAL,
        "contrato": "clt",
        "avisos": (),
        "salario": None,
        "requisitos_estagio": None,
        "versao_regras": "1",
    }
    return VagaTratada(**(base | campos))


def _busca(**campos: Any) -> Busca:
    base: dict[str, Any] = {
        "nome": "minha",
        "cargos": ("backend",),
        "cidades": (SP,),
        "modalidades": (Modalidade.PRESENCIAL, Modalidade.REMOTO),
        "niveis": (Nivel.JUNIOR,),
        "salario_min_centavos": 500_000,
        "salario_moeda": "BRL",
        "idiomas": ("pt",),
    }
    return Busca(**(base | campos))


def _salario(plausivel: bool = True) -> Salario:
    return Salario(
        moeda="BRL",
        minimo=800_000,
        maximo=None,
        periodo="mes",
        mensal_minimo=800_000,
        plausivel=plausivel,
        texto="R$ 8.000",
    )


def _nota(v: VagaTratada, b: Busca | None = None, **extra: Any) -> int | None:
    busca = b or _busca()
    args: dict[str, Any] = {
        "sal_mensal_brl": 8000,
        "minimo_busca_brl": 5000 if busca.salario_min_centavos else None,
        "regras_ligadas": False,
    }
    return calcular(v, busca, **(args | extra)).nota


def _vaga_completa(**campos: Any) -> VagaTratada:
    """Casa com `_busca()` em tudo: nota 100."""
    return _tratada(**({"salario": _salario()} | campos))


def test_pesos() -> None:
    assert _nota(_vaga_completa()) == 100
    # cargo: título 40, só na descrição 20, em lugar nenhum 0
    assert _nota(_vaga_completa(titulo="Analista", descricao_texto="trabalho com backend")) == 80
    assert _nota(_vaga_completa(titulo="Analista", descricao_texto="trabalho com java")) == 60
    # local e modalidade: cidade 20, mesma UF 10, remoto aceito 20, nada 0
    assert _nota(_vaga_completa(locais=(CAMPINAS,))) == 90
    assert _nota(_vaga_completa(locais=(RECIFE,), modalidade=Modalidade.REMOTO)) == 100
    assert _nota(_vaga_completa(locais=(RECIFE,))) == 80
    assert _nota(_vaga_completa(modalidade=Modalidade.HIBRIDO)) == 80  # modalidade fora zera
    # nível: dentro 15, não informado 7, fora 0
    assert _nota(_vaga_completa(nivel=Nivel.NAO_INFORMADO)) == 92
    assert _nota(_vaga_completa(nivel=Nivel.SENIOR)) == 85
    # salário: >= mínimo 15; abaixo 0; sem dado, implausível ou sem cotação 7
    assert _nota(_vaga_completa(), sal_mensal_brl=5000) == 100
    assert _nota(_vaga_completa(), sal_mensal_brl=4999) == 85
    assert _nota(_vaga_completa(salario=None), sal_mensal_brl=None) == 92
    assert _nota(_vaga_completa(salario=_salario(plausivel=False))) == 92
    assert _nota(_vaga_completa(), sal_mensal_brl=None) == 92
    # mínimo da busca em moeda sem cotação: critério preenchido, fica neutro (7), não some
    assert _nota(_vaga_completa(), minimo_busca_brl=None) == 92
    # idioma: aceito 10, não detectado ("outro") 5, outro idioma 0
    assert _nota(_vaga_completa(idioma="outro")) == 95
    assert _nota(_vaga_completa(idioma="en")) == 90


def test_motivo_de_cargo_traz_a_palavra_como_a_pessoa_escreveu() -> None:
    r = calcular(
        _tratada(titulo="Estágio em dados"),
        _busca(cargos=("Estágio",)),
        sal_mensal_brl=None,
        minimo_busca_brl=None,
        regras_ligadas=False,
    )
    assert r.motivos[0].params == {"palavra": "Estágio"}


def test_cargo_ignora_acento_caixa_e_acha_palavra_inteira() -> None:
    def nota(titulo: str, cargos: tuple[str, ...]) -> int | None:
        v = _tratada(titulo=titulo, descricao_texto="")
        return _nota(v, Busca(nome="x", cargos=cargos))

    assert nota("Dev C++ Sênior", ("c++",)) == 100
    assert nota("Estágio em TI", ("ESTAGIO",)) == 100
    assert nota("Engenheiro de Dados Sênior", ("engenheiro de dados",)) == 100
    assert nota("Javascript Dev", ("java",)) == 0  # palavra inteira, não pedaço
    assert nota("Dev", ("", "  ")) is None  # palavra em branco não conta como critério


def test_nota_usa_so_criterios_preenchidos() -> None:
    v = _vaga_completa(nivel=Nivel.JUNIOR, idioma="pt")
    so_nivel_e_idioma = Busca(nome="x", niveis=(Nivel.JUNIOR,), idiomas=("pt",))
    assert _nota(v, so_nivel_e_idioma) == 100  # 25 de 25
    v2 = _vaga_completa(nivel=Nivel.NAO_INFORMADO, idioma="pt")
    assert _nota(v2, so_nivel_e_idioma) == 68  # (7 + 10) de 25
    so_cargo = Busca(nome="x", cargos=("backend",))
    assert _nota(_tratada(titulo="Analista", descricao_texto="backend"), so_cargo) == 50  # 20 de 40
    # salário só entra se a busca tem mínimo
    sem_minimo = Busca(nome="x", niveis=(Nivel.JUNIOR,))
    assert _nota(_vaga_completa(), sem_minimo, minimo_busca_brl=None) == 100


def test_arredondamento_para_o_inteiro_mais_proximo() -> None:
    assert _arredondar(1, 8) == 13  # 12,5 sobe (round() do Python daria 12)
    assert _arredondar(3, 8) == 38  # 37,5
    assert _arredondar(47, 55) == 85  # 85,45
    assert _arredondar(1, 3) == 33
    assert _arredondar(2, 3) == 67


def _compor(cargo: int, local: int, nivel: int, salario: int, idioma: int) -> VagaTratada:
    """Vaga que dá exatamente esses pontos na busca completa de `_busca()`."""
    titulo = {40: "Dev Backend", 20: "Analista", 0: "Analista"}[cargo]
    descricao = {40: "", 20: "backend", 0: "java"}[cargo]
    locais, modalidade = {
        20: ((SP,), Modalidade.PRESENCIAL),
        10: ((CAMPINAS,), Modalidade.PRESENCIAL),
        0: ((RECIFE,), Modalidade.PRESENCIAL),
    }[local]
    nivel_vaga = {15: Nivel.JUNIOR, 7: Nivel.NAO_INFORMADO, 0: Nivel.SENIOR}[nivel]
    idioma_vaga = {10: "pt", 5: "outro", 0: "en"}[idioma]
    return _tratada(
        titulo=titulo,
        descricao_texto=descricao,
        locais=locais,
        modalidade=modalidade,
        nivel=nivel_vaga,
        idioma=idioma_vaga,
        salario=_salario() if salario != 7 else None,
    )


def _nota_composta(cargo: int, local: int, nivel: int, salario: int, idioma: int) -> int | None:
    v = _compor(cargo, local, nivel, salario, idioma)
    sal = {15: 8000, 7: None, 0: 100}[salario]
    return _nota(v, sal_mensal_brl=sal)


def test_faixas() -> None:
    b = _busca()

    def faixa(*pontos: int) -> str | None:
        v = _compor(*pontos)
        sal = {15: 8000, 7: None, 0: 100}[pontos[3]]
        return calcular(v, b, sal_mensal_brl=sal, minimo_busca_brl=5000, regras_ligadas=False).nivel

    assert _nota_composta(40, 20, 0, 0, 10) == 70
    assert faixa(40, 20, 0, 0, 10) == "bom"
    assert _nota_composta(40, 10, 7, 7, 5) == 69
    assert faixa(40, 10, 7, 7, 5) == "medio"
    assert _nota_composta(40, 0, 0, 0, 0) == 40
    assert faixa(40, 0, 0, 0, 0) == "medio"
    assert _nota_composta(20, 0, 7, 7, 5) == 39
    assert faixa(20, 0, 7, 7, 5) == "fraco"
    assert faixa(0, 0, 0, 0, 0) == "fraco"
    assert faixa(40, 20, 15, 15, 10) == "bom"


def test_motivos_um_por_criterio_preenchido() -> None:
    r = calcular(
        _vaga_completa(), _busca(), sal_mensal_brl=8000, minimo_busca_brl=5000, regras_ligadas=True
    )
    assert [m.chave for m in r.motivos] == [
        "encaixe.cargo_titulo",
        "encaixe.local_cidade",
        "encaixe.nivel_ok",
        "encaixe.salario_ok",
        "encaixe.idioma_ok",
    ]
    assert r.motivos[0].params == {"palavra": "backend"}
    r2 = calcular(
        _tratada(titulo="Analista", descricao_texto="java", salario=None),
        _busca(),
        sal_mensal_brl=None,
        minimo_busca_brl=5000,
        regras_ligadas=False,
    )
    chaves = [m.chave for m in r2.motivos]
    assert chaves[0] == "encaixe.cargo_ausente"
    assert "encaixe.salario_nao_informado" in chaves


def test_sem_criterio_nota_vazia() -> None:
    nada = Busca(nome="x")
    v = _tratada(nivel=Nivel.SENIOR, idioma="en", modalidade=Modalidade.REMOTO)
    r = calcular(v, nada, sal_mensal_brl=10, minimo_busca_brl=None, regras_ligadas=True)
    assert r.nota is None
    assert r.nivel is None
    assert r.motivos == ()
    assert r.oculta_motivo is None  # critério vazio não oculta


def _ruim() -> VagaTratada:
    """Quebra as cinco regras de ocultar de uma vez."""
    return _tratada(
        modalidade=Modalidade.REMOTO,
        nivel=Nivel.SENIOR,
        idioma="en",
        locais=(Local(cidade="Lisboa", pais="PT"),),
        avisos=(Aviso.RESTRITO_A_PAIS,),
        salario=_salario(),
    )


def _busca_ruim(**campos: Any) -> Busca:
    return _busca(modalidades=(Modalidade.PRESENCIAL,), **campos)


def _oculta(v: VagaTratada, b: Busca, **extra: Any) -> str | None:
    args: dict[str, Any] = {"sal_mensal_brl": 100, "minimo_busca_brl": 5000, "regras_ligadas": True}
    return calcular(v, b, **(args | extra)).oculta_motivo


def test_ocultar_primeiro_motivo() -> None:
    v = _ruim()
    desligadas: dict[str, bool] = {}
    ordem = ["modalidade", "nivel", "salario", "idioma", "pais"]
    for regra in ordem:
        assert _oculta(v, _busca_ruim(regras_ocultar=dict(desligadas))) == regra
        desligadas[regra] = False
    assert _oculta(v, _busca_ruim(regras_ocultar=desligadas)) is None


def test_ocultar_so_com_dado_conhecido() -> None:
    b = _busca()
    nada_conhecido = _tratada(
        modalidade=Modalidade.NAO_INFORMADO,
        nivel=Nivel.NAO_INFORMADO,
        idioma="outro",
        avisos=(Aviso.RESTRITO_A_PAIS,),
        locais=(),
        salario=None,
    )
    assert _oculta(nada_conhecido, b, sal_mensal_brl=None) is None


def test_remoto_restrito_a_outro_pais() -> None:
    b = _busca(modalidades=(), niveis=(), idiomas=(), salario_min_centavos=None)
    restrita = _tratada(
        modalidade=Modalidade.REMOTO,
        avisos=(Aviso.RESTRITO_A_PAIS,),
        locais=(Local(pais="US"),),
    )
    kw: dict[str, Any] = {"minimo_busca_brl": None}
    assert _oculta(restrita, b, **kw) == "pais"
    # país da pessoa vem das cidades da busca; sem cidade, Brasil
    assert _oculta(restrita, _busca(cidades=(), modalidades=()), **kw) == "pais"
    br = _tratada(modalidade=Modalidade.REMOTO, avisos=(Aviso.RESTRITO_A_PAIS,), locais=(SP,))
    assert _oculta(br, b, **kw) is None
    eua = _busca(cidades=(Local(cidade="Austin", pais="US"),), modalidades=())
    assert _oculta(restrita, eua, **kw) is None
    # sem aviso, ou sem ser remoto, ou sem país na vaga: não oculta
    sem_aviso = _tratada(modalidade=Modalidade.REMOTO, locais=(Local(pais="US"),))
    assert _oculta(sem_aviso, b, **kw) is None
    presencial = _tratada(
        modalidade=Modalidade.PRESENCIAL,
        avisos=(Aviso.RESTRITO_A_PAIS,),
        locais=(Local(pais="US"),),
    )
    assert _oculta(presencial, b, **kw) is None
    sem_pais = _tratada(modalidade=Modalidade.REMOTO, avisos=(Aviso.RESTRITO_A_PAIS,), locais=())
    assert _oculta(sem_pais, b, **kw) is None


def test_salario_abaixo_do_minimo_oculta() -> None:
    b = Busca(nome="x", salario_min_centavos=500_000, salario_moeda="BRL")
    v = _tratada(salario=_salario())
    assert _oculta(v, b, sal_mensal_brl=4999) == "salario"
    assert _oculta(v, b, sal_mensal_brl=5000) is None


def test_sem_cotacao_nao_oculta() -> None:
    b = Busca(nome="x", salario_min_centavos=500_000, salario_moeda="BRL")
    v = _tratada(salario=_salario())
    assert _oculta(v, b, sal_mensal_brl=None) is None  # vaga em moeda sem cotação
    assert _oculta(v, b, minimo_busca_brl=None) is None  # mínimo da busca sem cotação
    assert _oculta(_tratada(salario=_salario(plausivel=False)), b) is None  # implausível
    assert _oculta(_tratada(salario=None), b) is None  # sem dado
    # controles: o mesmo caso com cotação oculta, e sem cotação a nota fica neutra
    assert _oculta(v, b, sal_mensal_brl=4999, minimo_busca_brl=5000) == "salario"
    sem = calcular(v, b, sal_mensal_brl=None, minimo_busca_brl=None, regras_ligadas=True)
    assert sem.oculta_motivo is None
    assert [m.chave for m in sem.motivos] == ["encaixe.salario_nao_informado"]
    assert sem.nota == 47  # 100 x 7 / 15


def test_regras_desligadas_nao_ocultam() -> None:
    v = _ruim()
    b = _busca_ruim()
    desligada = calcular(v, b, sal_mensal_brl=100, minimo_busca_brl=5000, regras_ligadas=False)
    assert desligada.oculta_motivo is None
    assert desligada.nota is not None  # a nota continua sendo calculada
    ligada = calcular(v, b, sal_mensal_brl=100, minimo_busca_brl=5000, regras_ligadas=True)
    assert ligada.oculta_motivo == "modalidade"
    assert ligada.nota == desligada.nota
