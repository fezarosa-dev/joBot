import unicodedata

import pytest

from jobot.nucleo.modelo import RequisitosEstagio
from jobot.nucleo.tratamento.estagio import ler_requisitos


def _ler(texto: str) -> RequisitosEstagio:
    r = ler_requisitos(texto)
    assert r is not None
    return r


@pytest.mark.parametrize(
    ("texto", "curso"),
    [
        ("Estamos buscando estudante de Engenharia de Software.", "Engenharia de Software"),
        ("Cursando Ciência da Computação ou áreas afins", "Ciência da Computação"),
        ("Cursando o curso de Administração, Economia", "Administração"),
        ("cursando sistemas de informacao, a partir do 5o semestre", "sistemas de informacao"),
        ("Currently pursuing a Bachelor's degree in Computer Science.", "Computer Science"),
        ("You are enrolled in Electrical Engineering or similar", "Electrical Engineering"),
    ],
)
def test_campos_curso(texto: str, curso: str) -> None:
    assert _ler(texto).curso == curso


@pytest.mark.parametrize(
    ("texto", "curso"),
    [
        ("cursando Letras e Pedagogia", "Letras e Pedagogia"),
        ("Cursando Letras e Pedagogia, com disponibilidade", "Letras e Pedagogia"),
        (
            "Estudante de Engenharia Civil e Arquitetura e a partir do 5º semestre",
            "Engenharia Civil e Arquitetura",
        ),
    ],
)
def test_curso_composto_traz_os_dois(texto: str, curso: str) -> None:
    assert _ler(texto).curso == curso


def test_falso_positivo_conhecido_do_curso_composto() -> None:
    # caracterização: "e" + maiúscula continua o curso; a T78 decide com o gabarito se limita
    assert _ler("cursando Direito e Estágio remunerado").curso == "Direito e Estágio remunerado"


@pytest.mark.parametrize(
    ("texto", "curso"),
    [
        ("cursando Letras e com disponibilidade", "Letras"),
        ("cursando Letras e a partir do 5º semestre", "Letras"),
        ("cursando letras e pedagogia", "letras"),
        ("studying Law and Economics", "Law"),
    ],
)
def test_e_antes_de_palavra_minuscula_ainda_encerra_o_curso(texto: str, curso: str) -> None:
    assert _ler(texto).curso == curso


@pytest.mark.parametrize(
    ("texto", "semestre"),
    [
        ("Cursando a partir do 5º semestre", 5),
        ("Estudante entre o 3º e o 6º semestre", 3),
        ("At least 4th semester of your degree", 4),
    ],
)
def test_campos_semestre(texto: str, semestre: int) -> None:
    assert _ler(texto).semestre_minimo == semestre


@pytest.mark.parametrize(
    ("texto", "ano"),
    [
        ("Estar a partir do 3º ano da graduação", 3),
        ("Cursando 2o ano ou superior", 2),
        ("3rd year student or above", 3),
    ],
)
def test_campos_ano(texto: str, ano: int) -> None:
    assert _ler(texto).ano_minimo == ano


def test_ano_de_experiencia_nao_e_ano_do_curso() -> None:
    assert ler_requisitos("Pelo menos 2 anos de experiência com Python") is None


@pytest.mark.parametrize(
    ("texto", "formatura"),
    [
        ("Previsão de formatura em dezembro de 2027.", "dezembro de 2027"),
        ("Formatura prevista até 12/2027", "12/2027"),
        ("Expected graduation: May 2027", "May 2027"),
        ("Graduating in 2027 or later", "2027"),
    ],
)
def test_campos_formatura(texto: str, formatura: str) -> None:
    assert _ler(texto).previsao_formatura == formatura


@pytest.mark.parametrize(
    ("texto", "carga"),
    [
        ("Carga horária de 6 horas diárias", "6 horas diárias"),
        ("Jornada: 30 horas semanais", "30 horas semanais"),
        ("Estágio de 6h/dia, presencial", "6h/dia"),
        ("Part-time, 20 hours per week", "20 hours per week"),
    ],
)
def test_campos_carga_horaria(texto: str, carga: str) -> None:
    assert _ler(texto).carga_horaria == carga


@pytest.mark.parametrize(
    ("texto", "bolsa"),
    [
        ("Bolsa de R$ 1.800,00 por mês.", "R$ 1.800,00 por mês"),
        ("Bolsa-auxílio: R$ 1.500", "R$ 1.500"),
        ("Bolsa de 1.200 reais", "1.200 reais"),
        ("Monthly stipend of $2,000 per month", "$2,000 per month"),
    ],
)
def test_campos_bolsa(texto: str, bolsa: str) -> None:
    assert _ler(texto).bolsa == bolsa


def test_varios_campos_juntos() -> None:
    r = _ler(
        "Cursando Engenharia de Computação a partir do 4º semestre. "
        "Formatura prevista em 2028. 6 horas por dia. Bolsa de R$ 2.000."
    )
    assert r == RequisitosEstagio(
        curso="Engenharia de Computação",
        semestre_minimo=4,
        previsao_formatura="2028",
        carga_horaria="6 horas por dia",
        bolsa="R$ 2.000",
    )


@pytest.mark.parametrize(
    "texto", ["", "Vaga para desenvolvedor Python sênior, CLT.", "Bolsa de valores"]
)
def test_texto_sem_nenhum_campo_devolve_none(texto: str) -> None:
    assert ler_requisitos(texto) is None


@pytest.mark.parametrize(
    "texto",
    [
        "Cursando a partir do 5º semestre",
        "Cursando 2o ano ou superior",
        "Estudante entre o 3º e o 6º semestre",
    ],
)
def test_semestre_ou_ano_sem_nome_nao_vira_curso(texto: str) -> None:
    assert _ler(texto).curso is None


@pytest.mark.parametrize(
    ("texto", "carga"),
    [
        ("Bolsa R$ 1.200,00 - 20 horas semanais", "20 horas semanais"),
        ("Estágio 2021 - 6 horas por dia", "6 horas por dia"),
    ],
)
def test_carga_horaria_nao_comeca_no_meio_de_outro_numero(texto: str, carga: str) -> None:
    assert _ler(texto).carga_horaria == carga


def test_texto_ja_decomposto_nfd_e_lido() -> None:
    texto = unicodedata.normalize("NFD", "Conclusão prevista em dezembro de 2027.")
    assert _ler(texto).previsao_formatura == "dezembro de 2027"
