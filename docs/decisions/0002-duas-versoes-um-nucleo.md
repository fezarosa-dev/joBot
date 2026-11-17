# 0002. Duas versões, um núcleo

- **Status:** aceita
- **Data:** 2026-11-13
- **Atualizada:** 2026-11-17 (a IA da fase 4 não dá nota de encaixe, para confirmar, D185 e [0026](0026-ia-da-fase-4.md))

## Contexto

Nem todo mundo quer instalar um programa. Uma versão no navegador, sem instalação, alcança mais gente, mas não pode guardar logins nem segredos.

## Decisão

### Um núcleo, duas caras

- Um único repositório com um núcleo comum (coletores, rótulos, remoção de duplicadas, leitura de salário) e duas versões.
- Versão local (o foco): completa, com sites que exigem login, IA automática, extensão do navegador, Gmail e áudio.
- Versão GitHub Pages (fase 8): o GitHub Actions (serviço do GitHub que roda tarefas automáticas) roda uma vez por dia só com fontes públicas, nunca com logins ou segredos. Os dados ficam num ramo separado chamado `dados`, sobrescrito a cada dia.

### O que a versão Pages tem

- O perfil do visitante fica no localStorage do navegador (um espaço de gravação do próprio navegador).
- A IA é manual (copiar e colar) para: currículo → perfil, nota de encaixe, candidatura e respostas de formulário.
- Status por vaga, exportar/importar o perfil em arquivo (que também pode ser importado na versão local), o mesmo visual e um botão "baixar versão completa".
- Os rótulos vêm só de regras. Usar o Haiku com a chave do próprio visitante fica como opção, desligada por padrão.
- Fora da versão Pages: logins, Gmail, extensão, IA automática e áudio.
- Toda página da versão Pages (fase 8) terá uma faixa fixa no topo dizendo que a versão para baixar é mais completa, com o que ela tem a mais (mais fontes, segundo plano, inteligência artificial, sites com login) e um link para a instalação. O texto final e o visual da faixa são decididos na fase 8.

### Quando e como a versão Pages roda

- Só vai ao ar quando o repositório for público. O GitHub Actions em runners padrão é gratuito para repositório público (conferido na documentação do GitHub em 2026-11-13).
- Para não parar: o GitHub desativa agendamentos de repositório público depois de 60 dias sem atividade. Por isso o workflow se reativa pela API a cada execução.
- O site mostra `atualizado em <data>`.
- O cron (agendador) roda fora do minuto :00, porque horários cheios atrasam ou perdem execuções.

## Nota de encaixe na fase 4 (2026-11-17, para confirmar)

- Na fase 4, a IA não dá nota de encaixe (D185.11, para confirmar): ela só lista o que a vaga pede, e o código compara com o perfil. A "nota de encaixe" pela IA manual da versão Pages muda junto: a fase 8 decide o que a IA manual faz no encaixe.
- Os esquemas das respostas da IA ficam em pydantic, no Python (D185.3, para confirmar). Eles não servem ao JavaScript da versão Pages; a fase 8 decide se viram dados que as duas versões leem.

## Consequências

- As regras de rótulo precisam funcionar igual em Python e em JavaScript (ver 0007).
- Nenhum segredo vai para o GitHub Actions.

## Pontos em aberto

- Confirmar se os pushes no ramo `dados` contam como atividade do repositório (agendamentos só rodam no ramo padrão).

## Ver também

- [0007. Tratamento das vagas: duplicadas, ciclo de vida, salário e rótulos](0007-tratamento-dos-dados.md)
- [0009. Inteligência artificial: opções, modelos e pacote offline](0009-ia-backends-e-modelos.md)
- [0017. Fases do projeto](0017-fases.md)
- [0026. IA da fase 4: tarefas, backends e modelo local](0026-ia-da-fase-4.md)
- [duvidas.md: D185 (fase 4)](../../duvidas.md)
