"""Tipos do núcleo (desenho 7.1, 7.2 e 10.3). Só biblioteca padrão.

Dinheiro: `Salario` em centavos da moeda original; `SalarioBruto` e `Busca.salario_min_centavos`
dizem a unidade no nome. Valores em reais inteiros só existem no banco (colunas `_brl`).
"""

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal, Self
from urllib.parse import urlsplit

Periodo = Literal["hora", "dia", "semana", "mes", "ano"]
Idioma = Literal["pt", "en", "es", "outro"]
FormatoDescricao = Literal["html", "markdown", "texto"]


class Area(StrEnum):
    TECNOLOGIA = "tecnologia"
    DADOS = "dados"
    DESIGN = "design"
    PRODUTO = "produto"
    MARKETING = "marketing"
    VENDAS = "vendas"
    FINANCAS = "financas"
    RH = "rh"
    JURIDICO = "juridico"
    OPERACOES = "operacoes"
    ENGENHARIA = "engenharia"
    SAUDE = "saude"
    EDUCACAO = "educacao"
    ADMINISTRATIVO = "administrativo"
    ATENDIMENTO = "atendimento"
    PESQUISA = "pesquisa"
    OUTRA = "outra"


class Nivel(StrEnum):
    ESTAGIO = "estagio"
    TRAINEE = "trainee"
    JUNIOR = "junior"
    PLENO = "pleno"
    SENIOR = "senior"
    ESPECIALISTA = "especialista"
    LIDERANCA = "lideranca"
    NAO_INFORMADO = "nao_informado"


class Modalidade(StrEnum):
    PRESENCIAL = "presencial"
    HIBRIDO = "hibrido"
    REMOTO = "remoto"
    NAO_INFORMADO = "nao_informado"


class Contrato(StrEnum):
    CLT = "clt"
    PJ = "pj"
    ESTAGIO = "estagio"
    TRAINEE = "trainee"
    TEMPORARIO = "temporario"
    APRENDIZ = "aprendiz"
    BOLSA_PESQUISA = "bolsa_pesquisa"
    PROGRAMA = "programa"
    CONCURSO = "concurso"
    FREELANCE = "freelance"
    NAO_INFORMADO = "nao_informado"


class Aviso(StrEnum):
    EXIGE_VISTO = "exige_visto"
    EXIGE_DOUTORADO = "exige_doutorado"
    RESTRITO_A_PAIS = "restrito_a_pais"


@dataclass(frozen=True, kw_only=True)
class SalarioBruto:
    """Salário como a fonte separa: unidades inteiras ou decimais da moeda, não centavos."""

    moeda: str | None = None
    minimo_unidades: float | None = None
    maximo_unidades: float | None = None
    periodo: Periodo | None = None


@dataclass(frozen=True, kw_only=True)
class Salario:
    moeda: str  # ISO 4217
    minimo: int | None  # centavos da moeda original
    maximo: int | None  # centavos da moeda original
    periodo: Periodo
    mensal_minimo: int | None  # centavos da moeda original
    plausivel: bool
    texto: str  # como veio
    beneficios: tuple[str, ...] = ()
    periodo_deduzido: bool = False  # período não veio no texto: deduzido pela ordem de grandeza


@dataclass(frozen=True, kw_only=True)
class Local:
    cidade: str | None = None
    uf: str | None = None
    pais: str | None = None  # ISO 3166-1 alfa-2


@dataclass(frozen=True, kw_only=True)
class RequisitosEstagio:
    curso: str | None = None
    semestre_minimo: int | None = None
    ano_minimo: int | None = None
    previsao_formatura: str | None = None  # como veio no texto
    carga_horaria: str | None = None  # como veio no texto
    bolsa: str | None = None  # como veio no texto


def _confere_http(url: str, campo: str) -> None:
    partes = urlsplit(url)
    if partes.scheme.lower() not in ("http", "https") or not partes.netloc:
        raise ValueError(f"{campo} precisa ser http ou https: {url!r}")


def _confere_vaga(url: str, url_candidatura: str | None, publicada_em: datetime | None) -> None:
    _confere_http(url, "url")
    if url_candidatura is not None:  # vira href no painel: recusa, mas nunca reescreve
        _confere_http(url_candidatura, "url_candidatura")
    if publicada_em is not None and publicada_em.utcoffset() is None:
        raise ValueError("publicada_em precisa ter fuso")


@dataclass(frozen=True, kw_only=True)
class VagaColetada:
    fonte: str
    escopo: str  # "" quando a fonte é uma lista só
    url: str
    titulo: str
    empresa: str
    descricao_formato: FormatoDescricao
    descricao: str = ""
    id_externo: str | None = None
    url_candidatura: str | None = None  # guardada e usada sem nenhuma mudança
    locais: tuple[str, ...] = ()
    modalidade_declarada: str | None = None
    contrato_declarado: str | None = None
    salario_texto: str | None = None
    salario_estruturado: SalarioBruto | None = None
    publicada_em: datetime | None = None
    prazo: date | None = None
    inicio: date | None = None
    etiquetas: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _confere_vaga(self.url, self.url_candidatura, self.publicada_em)

    def para_json(self) -> str:
        return json.dumps(asdict(self), default=lambda o: o.isoformat(), ensure_ascii=False)

    @classmethod
    def de_json(cls, texto: str) -> Self:
        d: dict[str, Any] = json.loads(texto)
        for chave in ("locais", "etiquetas"):
            d[chave] = tuple(d.get(chave, ()))
        if d.get("salario_estruturado") is not None:
            d["salario_estruturado"] = SalarioBruto(**d["salario_estruturado"])
        if d.get("publicada_em") is not None:
            d["publicada_em"] = datetime.fromisoformat(d["publicada_em"])
        for chave in ("prazo", "inicio"):
            if d.get(chave) is not None:
                d[chave] = date.fromisoformat(d[chave])
        return cls(**d)


@dataclass(frozen=True, kw_only=True)
class VagaTratada:
    """Tudo de `VagaColetada` (com `locais` já lidos) mais o que o núcleo produz."""

    fonte: str
    escopo: str
    url: str
    titulo: str
    empresa: str
    descricao_formato: FormatoDescricao
    descricao: str
    id_externo: str | None
    url_candidatura: str | None
    modalidade_declarada: str | None
    contrato_declarado: str | None
    salario_texto: str | None
    salario_estruturado: SalarioBruto | None
    publicada_em: datetime | None
    prazo: date | None
    inicio: date | None
    etiquetas: tuple[str, ...]
    url_canonica: str
    url_hash: str
    descricao_texto: str
    idioma: Idioma
    locais: tuple[Local, ...]
    area: Area
    nivel: Nivel
    modalidade: Modalidade
    contrato: Contrato
    avisos: tuple[Aviso, ...]
    salario: Salario | None
    requisitos_estagio: RequisitosEstagio | None
    versao_regras: str

    def __post_init__(self) -> None:
        _confere_vaga(self.url, self.url_candidatura, self.publicada_em)


# Empresa, Busca e Motivo guardam Mapping (dict): frozen, mas não hasheáveis.
# Não usar em set nem como chave de dict.
@dataclass(frozen=True, kw_only=True)
class Empresa:
    nome: str
    fonte: str  # o ATS
    identificador: str
    id: int | None = None
    area: str | None = None
    pais: str | None = None
    parametros: Mapping[str, str] = field(default_factory=dict)
    ativa: bool = True
    removida_em: datetime | None = None
    origem: Literal["lista_inicial", "pessoa", "descoberta"] = "lista_inicial"
    conferida_em: date | None = None


@dataclass(frozen=True, kw_only=True)
class Busca:
    nome: str
    id: int | None = None
    ativa: bool = True
    cargos: tuple[str, ...] = ()  # palavras-chave
    cidades: tuple[Local, ...] = ()
    modalidades: tuple[Modalidade, ...] = ()
    niveis: tuple[Nivel, ...] = ()
    salario_min_centavos: int | None = None  # mensal, em centavos de `salario_moeda`
    salario_moeda: str | None = None
    idiomas: tuple[Idioma, ...] = ()
    regras_ocultar: Mapping[str, bool] = field(default_factory=dict)
    criada_em: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class Motivo:
    chave: str  # chave de i18n
    params: Mapping[str, str | int | float] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class Encaixe:
    nota: int | None  # 0 a 100; None quando a busca não tem nenhum critério
    nivel: Literal["bom", "medio", "fraco"] | None
    motivos: tuple[Motivo, ...] = ()
    oculta_motivo: str | None = None  # regra que escondeu; None se visível
