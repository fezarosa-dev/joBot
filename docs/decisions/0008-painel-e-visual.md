# 0008. Painel e visual

- **Status:** aceita
- **Data:** 2026-11-13

## Contexto

O painel é onde a pessoa passa o tempo: precisa ser fácil, bonito e mostrar tudo o que importa sem esconder informação.

## Decisão

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

## Consequências

- O estilo Apple é inspiração, não cópia: nenhum texto ou recurso da Apple entra no repositório.
- O desenho das telas é feito na fase 1.

## Ver também

- [0007. Tratamento das vagas: duplicadas, ciclo de vida, salário e rótulos](0007-tratamento-dos-dados.md)
- [0014. Segurança e privacidade](0014-seguranca-e-privacidade.md)
