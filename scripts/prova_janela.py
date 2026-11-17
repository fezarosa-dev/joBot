"""Página da prova da janela (T321): servidor HTTP mínimo em 127.0.0.1 com os cabeçalhos do painel.

Só o CI roda (`.github/workflows/casca.yml`). Os cabeçalhos saem de `src/jobot/painel/app.py` por
leitura do arquivo (`CABECALHOS`), sem importar o pacote: o job não instala o joBot.
Uso: `python3 scripts/prova_janela.py <porta> [--com-ipc]`.
"""

import ast
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "src" / "jobot" / "painel" / "app.py"
CSP = "Content-Security-Policy"
# Origem da IPC do Tauri: ipc://localhost no Linux e no Mac, http://ipc.localhost no Windows.
ORIGEM_IPC = "ipc: http://ipc.localhost"
PAGINA = b"<!doctype html><html lang='pt'><title>joBot</title><p>prova da janela</p></html>"


def cabecalhos(com_ipc: bool) -> dict[str, str]:
    arvore = ast.parse(APP.read_text(encoding="utf-8"))
    no = next(
        n.value
        for n in arvore.body
        if isinstance(n, ast.Assign)
        and any(isinstance(a, ast.Name) and a.id == "CABECALHOS" for a in n.targets)
    )
    valores: dict[str, str] = ast.literal_eval(no)
    if com_ipc:
        antes, depois = "connect-src 'self';", f"connect-src 'self' {ORIGEM_IPC};"
        valores[CSP] = valores[CSP].replace(antes, depois)
    return valores


def main() -> None:
    porta = int(sys.argv[1])
    extras = cabecalhos(com_ipc="--com-ipc" in sys.argv[2:])

    class Pagina(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            for chave, valor in extras.items():
                self.send_header(chave, valor)
            self.end_headers()
            self.wfile.write(PAGINA)

    print(f"prova_janela: {extras[CSP]}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", porta), Pagina).serve_forever()


if __name__ == "__main__":
    main()
