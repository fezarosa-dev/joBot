# 0008. Painel e visual

- **Status:** aceita
- **Data:** 2026-11-13
- **Atualizada:** 2026-11-15 (visual de app do Mac e botões da janela, D140 e D142); antes, em 2026-11-13

## Contexto

O painel é onde a pessoa passa o tempo: precisa ser fácil, bonito e mostrar tudo o que importa sem esconder informação.

## Decisão

As abas e o visual abaixo valem até a nota de 2026-11-15 (barra lateral e visual de app do Mac).

### Abas e navegação

- Abas: Destaques de hoje (as N melhores novas, uma por empresa), Todas, Novas, Fecham logo, Salvas, Candidatei, Programas e Ocultas.
- Filtros em chips com contagem; o filtro atual fica na URL (link permanente); busca com a tecla /; várias ordenações.
- Faixa de calendário de 12 meses em cada vaga.

### Vagas

- Status de cada vaga: nova → salva → candidatei → entrevista → recusada ou oferta.
- Botão "Algo errado nesta vaga?" para corrigir rótulo ou dado.

### Idiomas e visual

- Idiomas: português e inglês.
- Visual no estilo Apple: fonte SF no Mac e Inter (embutida no app) nos outros sistemas; translucidez; animações com efeito de mola; modo claro/escuro seguindo o sistema, com chave manual.

### Segurança do painel

- O painel só escuta em 127.0.0.1 (o próprio computador) e confere o cabeçalho Host de cada pedido.

## Visual de app do Mac e botões da janela (2026-11-15)

- O alvo passa de "estilo Apple" para parecer um app nativo do Mac, pelas Human Interface Guidelines atuais (D140). Vale para o painel, o assistente da primeira execução e o instalador.
- As abas de cima viram uma barra lateral, como a do Mail: as abas da lista acima e, depois delas, Buscas, Empresas e Fontes. Barra de ferramentas com a busca, lista no meio e detalhe à direita. Os endereços das páginas não mudam.
- Material Liquid Glass, com fundo sólido quando a pessoa liga "Reduzir transparência" ou "Aumentar contraste". Fonte SF pela fonte do sistema no Mac e Inter nos outros sistemas; ícones Lucide, com o arquivo de licença deles. SF Pro e SF Symbols nunca entram no repositório.
- A ideia de que o estilo Apple é inspiração, não cópia continua valendo no sentido de nenhum arquivo, texto ou recurso da Apple no repositório (sala limpa, ADR 0016). O que muda é o alvo: parecer nativo.
- Na fase 3 a janela vira a do app de desktop: no Mac, os botões do sistema; no Windows e no Linux, três círculos desenhados por nós em CSS ou SVG (D142). Até lá, vale o modo app do navegador, com a moldura do sistema (D140).

## Panorama na lateral (2026-11-16)

- A barra lateral ganha o item Panorama, a tela que junta o dia: o que fecha logo, as candidaturas e a busca. É o primeiro item, numa seção sem título acima de Vagas, sem contagem; o resto da lateral não muda.

## Consequências

- O estilo Apple é inspiração, não cópia: nenhum texto ou recurso da Apple entra no repositório.
- O desenho das telas é feito na fase 1.

## Ver também

- [0007. Tratamento das vagas: duplicadas, ciclo de vida, salário e rótulos](0007-tratamento-dos-dados.md)
- [0014. Segurança e privacidade](0014-seguranca-e-privacidade.md)
- [duvidas.md: D140 (visual de app do Mac) e D142 (botões da janela)](../../duvidas.md)
