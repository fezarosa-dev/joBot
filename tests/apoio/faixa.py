"""Ajudantes dos testes de rota para a faixa de desfazer que chega por OOB (T256, T260)."""

import re


def faixa(html: str) -> str:
    """A faixa de desfazer da resposta HTMX: o nó de `base.html`, trocado por dentro."""
    achou = re.search(r'<div\b[^>]*\bid="faixa-desfazer"[^>]*>.*?</div>\s*</div>', html, re.S)
    assert achou, "sem a faixa de desfazer na resposta"
    abertura = re.match(r"<div\b[^>]*>", achou.group(0))
    assert abertura and 'role="status"' in abertura.group(0)
    assert 'hx-swap-oob="innerHTML"' in abertura.group(0)
    return achou.group(0)


def form_da_faixa(faixa_html: str, destino: str) -> str:
    achou = re.search(
        rf'<form\b[^>]*\baction="{re.escape(destino)}"[^>]*>.*?</form>', faixa_html, re.S
    )
    assert achou, f"a faixa não traz o formulário para {destino}"
    return achou.group(0)
