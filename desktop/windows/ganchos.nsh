; Ganchos do instalador NSIS da casca (desenho 7.2, T337).
;
; Desinstalar: a casca desliga o segundo plano, para o servidor e apaga a pasta dela (bin/,
; python/, venvs/, manifestos) e o instalacao.json; nunca a pasta de dados nem o Chromium.
; Quem faz é o Rust (`--desinstalar`, desktop/src/fechar.rs); aqui só a chamada.
; Na troca de versão (o NSIS novo roda o desinstalador velho com /UPDATE), nada disso roda.

!macro NSIS_HOOK_PREUNINSTALL
  ${If} $UpdateMode <> 1
    ExecWait '"$INSTDIR\${MAINBINARYNAME}.exe" --desinstalar'
  ${EndIf}
!macroend
