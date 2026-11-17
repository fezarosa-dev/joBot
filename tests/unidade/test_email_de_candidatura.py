import pytest

from jobot.nucleo.candidatura import GATILHOS, email_de_candidatura


def test_acha_email_com_gatilho_pt() -> None:
    assert email_de_candidatura("Envie seu currículo para rh@example.com.") == "rh@example.com"


def test_acha_email_com_gatilho_en() -> None:
    assert email_de_candidatura("Send your resume to jobs@Example.ORG") == "jobs@example.org"


def test_acha_email_com_gatilho_es() -> None:
    assert email_de_candidatura("Postulaciones: talento@example.com") == "talento@example.com"


def test_gatilho_com_e_sem_acento() -> None:
    assert email_de_candidatura("Curriculo: rh@example.com") == "rh@example.com"
    assert email_de_candidatura("Currículo: rh@example.com") == "rh@example.com"
    assert email_de_candidatura("Mande a hoja de vida a rh@example.com") == "rh@example.com"


def test_gatilhos_nos_tres_idiomas() -> None:
    assert {"currículo", "send", "postula"} <= set(GATILHOS)
    for palavra in GATILHOS:
        texto = f"{palavra} rh@example.com"
        assert email_de_candidatura(texto) == "rh@example.com", palavra


def test_gatilho_na_linha_de_cima_nao_vale() -> None:
    texto = "Envie o currículo.\nOutro assunto: rh@example.com"
    assert email_de_candidatura(texto) is None
    assert email_de_candidatura("Envie o currículo\npara rh@example.com") == "rh@example.com"


def test_gatilho_so_dentro_do_proprio_endereco_nao_vale() -> None:
    assert email_de_candidatura("Fale com apply@example.com") is None
    assert email_de_candidatura("Fale com apply@example.com para apply") == "apply@example.com"


def test_ignora_email_sem_gatilho() -> None:
    assert email_de_candidatura("Fale com a equipe em rh@example.com.") is None
    assert email_de_candidatura("Envie o currículo para rh@example.com.") == "rh@example.com"


def test_ignora_noreply() -> None:
    for local in ("noreply", "no-reply", "NoReply", "no_reply"):
        assert email_de_candidatura(f"Send your resume to {local}@example.com") is None
    assert email_de_candidatura("Send your resume to reply@example.com") == "reply@example.com"


def _endereco(local: int, domino: int) -> str:
    rotulos = ["b" * 63, "c" * 63, "d" * (domino - 128)]
    return f"{'a' * local}@{'.'.join(rotulos)}"


def test_recusa_endereco_longo() -> None:
    ok = _endereco(64, 189)
    assert len(ok) == 254
    assert email_de_candidatura(f"Send your resume to {ok}") == ok
    assert email_de_candidatura(f"Send your resume to {'a' * 65}@example.com") is None
    longo = _endereco(64, 190)
    assert len(longo) == 255
    assert email_de_candidatura(f"Send your resume to {longo}") is None
    assert email_de_candidatura(f"Send your resume to rh@{'b' * 64}.com") is None


@pytest.mark.parametrize("lixo", ["?cc=x", "&bcc=x", "=", "%0A", "#", "/"])
def test_recusa_caracteres_de_query_no_local(lixo: str) -> None:
    assert email_de_candidatura("Send your resume to rh@example.com") == "rh@example.com"
    assert email_de_candidatura(f"Send your resume to {lixo}rh@example.com") is None
    assert email_de_candidatura(f"Send your resume to r{lixo}h@example.com") is None


@pytest.mark.parametrize("lixo", ["?cc=outro@example.org", "&bcc=x", "=", "%0A", "#", "/x"])
def test_recusa_caracteres_de_query_no_dominio(lixo: str) -> None:
    assert email_de_candidatura("Send your resume to rh@example.com ok") == "rh@example.com"
    assert email_de_candidatura(f"Send your resume to rh@example.com{lixo}") is None
    assert email_de_candidatura(f"Send your resume to rh@exam{lixo}ple.com") is None


def test_recusa_aspas_e_arroba_duplo() -> None:
    assert email_de_candidatura("Send your resume to rh@example.com") == "rh@example.com"
    assert email_de_candidatura('Send your resume to "rh@example.com"') is None
    assert email_de_candidatura("Send your resume to rh@@example.com") is None
    assert email_de_candidatura("Send your resume to a@b@example.com") is None


def test_recusa_fora_de_ascii() -> None:
    assert email_de_candidatura("Send your resume to rh@example.com") == "rh@example.com"
    assert email_de_candidatura("Send your resume to rhé@example.com") is None
    assert email_de_candidatura("Send your resume to rh@exámple.com") is None
    # espaço Unicode (NBSP) encostado no endereço recusa o endereço
    assert email_de_candidatura("Send your resume to rh@example.com\u00a0x") is None
    assert email_de_candidatura("Send your resume to rh@example.comé") is None


def test_recusa_rotulo_com_hifen_na_ponta() -> None:
    assert email_de_candidatura("Send your resume to rh@e-x.com") == "rh@e-x.com"
    assert email_de_candidatura("Send your resume to rh@-example.com") is None
    assert email_de_candidatura("Send your resume to rh@example-.com") is None
    assert email_de_candidatura("Send your resume to rh@example.com-") is None


def test_recusa_dominio_sem_ponto() -> None:
    assert email_de_candidatura("Send your resume to rh@example.com") == "rh@example.com"
    assert email_de_candidatura("Send your resume to rh@localhost") is None
    assert email_de_candidatura("Send your resume to rh@example..com") is None


def test_separadores_validos_em_volta() -> None:
    for texto in (
        "Send your resume (rh@example.com)",
        "Send your resume <rh@example.com>",
        "Send your resume: rh@example.com, thanks",
        "Send your resume;rh@example.com;",
        "Send your resume\nrh@example.com\n",
    ):
        assert email_de_candidatura(texto) == "rh@example.com", texto


def test_tira_pontuacao_do_fim() -> None:
    assert email_de_candidatura("Envie para rh@example.com.") == "rh@example.com"
    assert email_de_candidatura("Envie para rh@example.com..") is None


def test_segue_para_o_proximo() -> None:
    texto = "Envie o currículo para rh@example.com?cc=x ou para vagas@example.org."
    assert email_de_candidatura(texto) == "vagas@example.org"
    texto = "Envie o currículo para noreply@example.com ou para vagas@example.org"
    assert email_de_candidatura(texto) == "vagas@example.org"


def test_devolve_o_primeiro_que_passa() -> None:
    texto = "Envie para a@example.com ou para b@example.org"
    assert email_de_candidatura(texto) == "a@example.com"


def test_texto_vazio_devolve_none() -> None:
    assert email_de_candidatura("") is None
    assert email_de_candidatura("   \n ") is None


def test_texto_longo_hostil_nao_trava() -> None:
    sem_gatilho = "x@example.com. " * 20_000
    assert email_de_candidatura(sem_gatilho) is None
    assert email_de_candidatura(sem_gatilho + "\nEnvie o currículo para rh@example.org.") == (
        "rh@example.org"
    )
    assert email_de_candidatura("a" * 200_000 + "@" + "b" * 200_000) is None
    assert email_de_candidatura("a-" * 100_000 + "@" + "b." * 100_000) is None
    assert email_de_candidatura("é" * 50_000 + " apply " + "@" * 50_000) is None
