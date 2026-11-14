"""Sistema falso do segundo plano: nenhum teste de tela chama systemctl nem distrobox de verdade.

`FalsoSistema` é o executor de comandos (`Rodar`) injetado no painel. Ele só anota o que foi
pedido e responde como um systemd e um distrobox-host-exec saudáveis, salvo o que o teste muda.
"""

from collections.abc import Sequence

from jobot.sistema.segundo_plano_linux import Resultado


class FalsoSistema:
    def __init__(self, home: str = "") -> None:
        self.home = home  # o $HOME que o host responde (só dentro da distrobox)
        self.tem_enter = True  # `command -v distrobox-enter` acha o programa
        self.systemd_ok = True  # `systemctl --user show-environment` responde
        self.falha_em: dict[str, Resultado] = {}  # primeiro argumento do systemctl -> resposta
        self.chamadas: list[tuple[str, ...]] = []

    def __call__(self, comando: Sequence[str]) -> Resultado:
        self.chamadas.append(tuple(comando))
        resto = list(comando)
        if resto[0] == "distrobox-host-exec":
            resto = resto[1:]
        if resto[:2] == ["sh", "-c"]:
            if "command -v" in resto[2]:
                return (
                    Resultado(0, "/usr/bin/distrobox-enter\n") if self.tem_enter else Resultado(1)
                )
            return Resultado(0, self.home)  # printf %s "$HOME"
        assert resto[:2] == ["systemctl", "--user"], f"comando inesperado: {comando!r}"
        acao = resto[2]
        if acao == "show-environment":
            return Resultado(0 if self.systemd_ok else 1)
        return self.falha_em.get(acao, Resultado(0))

    def systemctl(self) -> list[tuple[str, ...]]:
        """Os argumentos de cada `systemctl --user` pedido, sem o prefixo do host."""
        achados = []
        for comando in self.chamadas:
            resto = comando[1:] if comando[0] == "distrobox-host-exec" else comando
            if resto[:2] == ("systemctl", "--user"):
                achados.append(resto[2:])
        return achados
