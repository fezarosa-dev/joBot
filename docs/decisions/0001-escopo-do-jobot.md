# 0001. Escopo: o que o joBot é e o que não é

- **Status:** aceita
- **Data:** 2026-11-13

## Contexto

Procurar vaga hoje exige abrir muitos sites, repetir filtros e perder prazos. O joBot junta tudo num painel pessoal que roda no computador da própria pessoa. O projeto está em desenvolvimento e ainda não tem código: tudo aqui descreve o que está planejado.

## Decisão

- O joBot busca, filtra, ranqueia e organiza vagas de muitas fontes num painel local.
- Botão "preparar candidatura": carta de apresentação, resumo do currículo ajustado à vaga e lista das habilidades que a pessoa tem e das que faltam, sempre no idioma da vaga.
- Não faz candidatura em massa e não envia candidatura sozinho: quem envia é sempre a pessoa.
- Cobre todos os tipos de vaga e todas as áreas: CLT, PJ, estágio, trainee, temporário, aprendiz, pesquisa e bolsa, programas e escolas de verão, concursos e editais.
- Toda funcionalidade pode ser ligada ou desligada.
- Uma pessoa por instalação, com várias buscas salvas.
- Público: pessoas comuns, em computadores médios (8 a 16 GB de RAM, sem placa de vídeo dedicada), com Linux, Windows ou macOS.
- Código aberto sob licença MIT, publicado no GitHub mais adiante (fase 8).

## Consequências

- Sem envio automático, cai o risco de spam e de bloqueio de conta.
- Como tudo é desligável, cada função precisa de uma chave nas configurações.

## Ver também

- [0002. Duas versões, um núcleo](0002-duas-versoes-um-nucleo.md)
- [0016. Licença, sala limpa e processo de trabalho](0016-licenca-clean-room-e-processo.md)
- [0017. Fases do projeto](0017-fases.md)
