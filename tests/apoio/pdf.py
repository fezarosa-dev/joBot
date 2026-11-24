"""PDFs montados no próprio teste com o `PdfWriter` do `pypdf` (nenhum PDF versionado; T435)."""

import io

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def montar_pdf(
    paginas: list[str | None],
    senha: str | None = None,
    dono: str | None = None,
    enchimento: int = 0,
    algoritmo: str = "RC4-128",
) -> bytes:
    """Uma página por texto, em Helvetica; `None` é página sem texto (só imagem, para o leitor).
    O fluxo vai sem compressão: o texto aparece cru nos bytes do PDF. `senha` é a de abrir;
    `dono` sozinho cifra o PDF com a senha de abrir vazia (abre sem pedir nada). `enchimento`
    pendura na primeira página um fluxo de tantos bytes que ninguém desenha (PDF grande). O AES
    (`algoritmo`) pede o `cryptography` para montar."""
    escritor = PdfWriter()
    for texto in paginas:
        pagina = escritor.add_blank_page(612, 792)
        if texto is None:
            continue
        fonte = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        fontes = DictionaryObject({NameObject("/F1"): escritor._add_object(fonte)})
        pagina[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): fontes})
        fluxo = DecodedStreamObject()
        fluxo.set_data(f"BT /F1 12 Tf 72 720 Td ({texto}) Tj ET".encode("latin-1"))
        pagina[NameObject("/Contents")] = escritor._add_object(fluxo)
    if enchimento:
        lastro = DecodedStreamObject()
        lastro.set_data(b"0" * enchimento)
        escritor.pages[0][NameObject("/Enchimento")] = escritor._add_object(lastro)
    if senha is not None or dono is not None:
        # o RC4 (o padrão) não pede o `cryptography`
        escritor.encrypt(senha or "", dono, algorithm=algoritmo)
    saida = io.BytesIO()
    escritor.write(saida)
    return saida.getvalue()
