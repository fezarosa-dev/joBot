# 0012. Extensão do navegador

- **Status:** aceita
- **Data:** 2026-11-13

## Contexto

Formulários de candidatura repetem as mesmas perguntas em cada site. Uma extensão do navegador pode preencher o que já é conhecido. O projeto ainda não tem código; isto é o plano.

## Decisão

- A extensão é escrita em TypeScript, compilado com `tsc`. A lógica é feita com TDD (escrever o teste primeiro).
- Precisa do joBot rodando no computador.
- Reconhece os campos do formulário pelo rótulo. A pessoa clica OK para preencher.
- Usa respostas salvas e um botão "gerar com IA". Informação que falta vira pergunta pendente no app. Quando a pessoa preenche algo à mão, a extensão pergunta "salvar no perfil?".
- Nunca toca em campos de senha ou de cartão.
- Funciona em todos os sites. Para incluir um site, a pessoa usa "adicionar site" pelo ícone na barra do navegador.
- Instalação descompactada (modo desenvolvedor) por enquanto; Chrome Web Store depois.
- Segurança:
  - token de pareamento com o app;
  - CORS (regra do navegador sobre quem pode falar com o app) liberado só para a origem da extensão;
  - checagem do cabeçalho Host;
  - shadow DOM fechado;
  - permissões de site opcionais.

## Consequências

- A pessoa continua no controle: nada é preenchido ou enviado sem o OK dela.

## Ver também

- [0009. Inteligência artificial: opções, modelos e pacote offline](0009-ia-backends-e-modelos.md)
- [0011. Perfil, currículo, primeira execução e áudio](0011-perfil-e-primeira-execucao.md)
- [0014. Segurança e privacidade](0014-seguranca-e-privacidade.md)
