# Perguntas do perfil: o mapa

Data: 2026-11-15. Só documento: nenhum código muda com ele. Decisão de origem: pedido do dono, por voz, em 2026-11-15 ("o mapa das perguntas que o joBot vai fazer"). Tudo aqui é **proposta para o dono confirmar** (seção 6).

Fatos sobre o código vêm com `arquivo:linha`, conferidos na `dev` de 2026-11-15. As linhas andam; procure pelo nome quando não baterem. O que não tem fonte é dito como "novo".

## 1. Para que serve

O joBot só acerta o encaixe se souber quem a pessoa é e o que ela quer. Hoje ele sabe pouco: o assistente de primeira execução faz um passo de preferências de busca e um de segundo plano (`painel/rotas/primeira_execucao.py:53`, `PASSOS = {"1": 1, "2": 2}`). Não existe perfil da pessoa: não há tabela nem módulo para isso (`src/jobot/navegador/perfil.py` é o perfil do navegador, outra coisa).

Este documento lista as perguntas que formam o perfil, em quatro blocos:

1. **Quem é**: formação, experiência, cargo, cidade, idiomas.
2. **O que procura**: cargo, área, nível, modalidade, salário, moeda, regime.
3. **O que aceita**: mudança de cidade, viagem, horário, contrato.
4. **O que recusa**: empresas, setores, palavras, faixas.

Cada pergunta diz o texto, o porquê, onde a resposta entra (campo que já existe ou "novo"), o tipo de resposta, se é obrigatória e se o currículo pode respondê-la.

A ADR 0011 já decide o essencial: o perfil é a fonte única para encaixe, candidatura e extensão (`docs/decisions/0011-perfil-e-primeira-execucao.md`, "Consequências"), e o questionário tem cerca de 25 perguntas base mais perguntas geradas para cobrir lacunas ("Questionário"). Este mapa tem 31 perguntas base. É um pouco acima do número da ADR: a seção 6 pergunta se o dono quer cortar.

## 2. Princípios

- **Pergunta curta.** Uma frase, sem jargão. Exemplo ao lado quando ajuda.
- **Uma por vez.** A tela mostra uma pergunta; a pessoa responde ou pula. Agrupar por bloco só na revisão final.
- **Pular é sempre possível.** Nenhuma pergunta trava a entrada no painel. Pular não grava nada e não conta como "não". O que ficou em branco é neutro no encaixe ("critério vazio é neutro", `docs/superpowers/specs/2026-11-13-fase-1-design.md:1105`, seção 11.1).
- **Dá para voltar e mudar.** Toda resposta se edita depois em Configurações. A primeira busca nasce das respostas do bloco 2 e muda como qualquer busca salva.
- **Nada sai da máquina por conta própria.** As respostas ficam no `jobot.db`, na pasta de dados da pessoa (ADR 0014). Só saem para o serviço de IA que a pessoa ligou, e nesse caso o painel diz qual (ADR 0009, ADR 0014). Sem IA ligada, a entrevista roda em formulário simples.
- **A IA só usa o que a pessoa disse.** Regra de ouro da ADR 0009: nunca inventa experiência, curso ou habilidade; se faltar informação, vira pergunta salva no perfil.
- **Conteúdo de vaga e de currículo é dado, nunca instrução.** O texto do PDF e o texto de uma vaga entram como dado. Pedido escrito dentro deles ("ignore as regras acima") não é seguido.
- **A pessoa revisa antes de salvar.** O que veio do currículo aparece preenchido e marcado; ela confirma ou corrige (ADR 0011, "Currículo").
- **Não se pergunta o que não ajuda a achar vaga.** Idade, estado civil, filhos, religião, saúde, raça e afins ficam de fora. CPF e data de nascimento também: a ADR 0011 os lista no perfil, mas só a candidatura precisa deles (seção 5).
- **Texto novo em `pt` e `en`.** Toda pergunta entra nos dois catálogos do painel (`CLAUDE.md`, "Regras do projeto").

## 3. As perguntas

Legenda de cada pergunta:

- **Existe**: o campo ou a regra já está no código, com a fonte.
- **Novo**: não há campo hoje.
- **Obrig.**: nenhuma pergunta é obrigatória para usar o painel. Quando a pergunta tem "precisa de uma do bloco", é porque uma busca sem nenhum critério não é criada (`painel/rotas/primeira_execucao.py:170`, `_montar`, devolve `None` sem critério).
- **Currículo**: sim (o PDF costuma trazer), parcial (dá palpite que a pessoa confirma) ou não.

### Bloco A. Quem é

**A1. Em que país você mora?**
- Por quê: define o país padrão das buscas sem cidade, a moeda dos valores convertidos e a regra "remoto restrito a outro país".
- Entra em: **Existe.** Chave `meu_pais` (`banco/cadastros.py:46`, leitura em `:288`), já perguntada no passo 1 (`painel/rotas/primeira_execucao.py:242` e `:250`).
- Tipo: escolha (lista de países, já marcada pelo idioma do navegador).
- Obrig.: não (sem resposta vale o país do navegador, senão BR). Currículo: parcial (endereço).

**A2. Em que cidade você mora?**
- Por quê: ponto de partida do encaixe por local e base para a pergunta C1.
- Entra em: **Novo** (`perfil.cidade_moradia`). O tipo `Local` já existe (`nucleo/modelo.py:101-105`: cidade, UF, país). Não confundir com `Busca.cidades` (`nucleo/modelo.py:236`), que são as cidades onde ela aceita trabalhar.
- Tipo: texto livre com sugestão de UF (a lista de UFs já está em `painel/rotas/primeira_execucao.py:78`, `_ufs`).
- Obrig.: não. Currículo: sim.

**A3. Qual é o seu cargo hoje? (ou o último que você teve)**
- Por quê: ajuda a sugerir os cargos da pergunta B1 e o nível da B3.
- Entra em: **Novo** (`perfil.cargo_atual`). Sugere valores para `Busca.cargos` (`nucleo/modelo.py:235`).
- Tipo: texto livre.
- Obrig.: não. Currículo: sim.

**A4. Há quantos anos você trabalha na sua área?**
- Por quê: com o cargo, sugere o nível (júnior, pleno, sênior) sem a pessoa se classificar sozinha.
- Entra em: **Novo** (`perfil.anos_de_experiencia`). A escala de níveis existe em `nucleo/modelo.py:40-48` (`Nivel`).
- Tipo: número (anos, 0 a 60).
- Obrig.: não. Currículo: sim (soma das experiências).

**A5. Quais foram seus empregos ou projetos mais importantes?**
- Por quê: a IA e o encaixe por habilidade (fase 4) precisam do que a pessoa já fez. Também alimenta a candidatura.
- Entra em: **Novo** (`perfil.experiencias`, lista de empresa, cargo, período, o que fez). Cada item vem de uma pergunta repetida ("mais um?").
- Tipo: texto livre estruturado, até 10 itens.
- Obrig.: não. Currículo: sim (é o principal uso do PDF, ADR 0011).

**A6. Qual é o seu maior nível de estudo?**
- Por quê: compara com vagas que exigem pós ou doutorado e com requisitos de estágio.
- Entra em: **Novo** (`perfil.formacao_nivel`). O aviso "exige doutorado" já existe como rótulo da vaga (`nucleo/modelo.py:75`, `Aviso.EXIGE_DOUTORADO`).
- Tipo: escolha única (ensino médio, técnico, graduação, pós-graduação, mestrado, doutorado).
- Obrig.: não. Currículo: sim.

**A7. Qual curso você faz ou fez, e em que situação está? (concluído, cursando, previsão de formatura)**
- Por quê: vaga de estágio e de programa pede curso, semestre e previsão de formatura.
- Entra em: **Novo** (`perfil.cursos`). O lado da vaga já existe: `RequisitosEstagio` com `curso`, `semestre_minimo`, `previsao_formatura` (`nucleo/modelo.py:108-115`).
- Tipo: texto livre (curso e instituição) mais escolha (situação).
- Obrig.: não. Pergunta condicional: só aparece se A6 foi respondida. Currículo: sim.

**A8. Quais são suas principais habilidades?**
- Por quê: a ADR 0007 prevê mostrar por vaga as habilidades que a pessoa tem (✓) e as que faltam (`docs/decisions/0007-tratamento-dos-dados.md:41`). Estava marcado para a fase 3 (`docs/superpowers/specs/2026-11-13-fase-1-design.md:67`); com a ordem nova (D138), a IA é a fase 4.
- Entra em: **Novo** (`perfil.habilidades`, lista).
- Tipo: lista de palavras (texto livre, até 50).
- Obrig.: não. Currículo: sim.

**A9. Que idiomas você fala, e com que nível?**
- Por quê: base para sugerir os idiomas de vaga da pergunta C8 e, depois, para comparar com requisitos de idioma.
- Entra em: **Novo** (`perfil.idiomas_falados`, pares idioma e nível). O tipo `Idioma` existe (`nucleo/modelo.py:16`, pt, en, es, outro), mas hoje `Busca.idiomas` (`nucleo/modelo.py:241`) guarda o idioma **da vaga** que a pessoa aceita (`nucleo/encaixe.py:136-144`), não o que ela fala. São coisas diferentes.
- Tipo: escolha por idioma (nenhum, básico, intermediário, avançado, fluente) para pt, en, es e "outro" com nome.
- Obrig.: não. Currículo: sim.

### Bloco B. O que procura

**B1. Que cargos ou palavras você quer ver nas vagas? (ex.: "analista de dados", "designer")**
- Por quê: é o critério de maior peso do encaixe (peso 40 de 100, `nucleo/dados/encaixe.json:2`). A palavra no título vale 40 pontos e na descrição, 20 (`nucleo/encaixe.py:42-63`).
- Entra em: **Existe.** `Busca.cargos` (`nucleo/modelo.py:235`), pergunta já feita em `Entrada.cargos` (`painel/rotas/primeira_execucao.py:90`), com o limite de 20 (`:54`, `_MAX_CARGOS`) e a limpeza de `_cargos` (`:107`).
- Tipo: lista de texto livre, sugerida a partir de A3.
- Obrig.: não, mas a busca só nasce se houver ao menos uma resposta no bloco B (`:170`). Currículo: parcial.

**B2. Em que área você quer trabalhar?**
- Por quê: separa "dados" de "marketing" quando o cargo é vago.
- Entra em: **Novo na busca.** A área já é rótulo da vaga (`nucleo/modelo.py:20-37`, `Area`) e filtro da lista (`banco/leitura.py:38`, `"area": "v.area = :area"`), mas `Busca` não tem campo de área e o encaixe não a usa (`nucleo/encaixe.py` não tem `_area`). Proposta: campo `Busca.areas` e um critério no encaixe. Mudar o encaixe é decisão de desenho (seção 6, P2).
- Tipo: escolha múltipla (as 17 áreas de `Area`).
- Obrig.: não. Currículo: parcial.

**B3. Que nível de cargo você procura?**
- Por quê: nível fora do escolhido esconde a vaga, quando a regra está ligada.
- Entra em: **Existe.** `Busca.niveis` (`nucleo/modelo.py:238`), critério `nucleo/encaixe.py:103-111`, regra de ocultar `nucleo/encaixe.py:165`. Já perguntada (`painel/rotas/primeira_execucao.py:63`, `_NIVEIS`).
- Tipo: escolha múltipla (estágio, trainee, júnior, pleno, sênior, especialista, liderança).
- Obrig.: não. Currículo: parcial (A3 e A4 sugerem).

**B4. Como você quer trabalhar: presencial, híbrido ou remoto?**
- Por quê: modalidade fora das aceitas esconde a vaga; remoto pontua cheio quando aceito.
- Entra em: **Existe.** `Busca.modalidades` (`nucleo/modelo.py:237`), critério `nucleo/encaixe.py:76-100`, regra `:161-163`. Já perguntada (`painel/rotas/primeira_execucao.py:62`, `_MODALIDADES`).
- Tipo: escolha múltipla.
- Obrig.: não. Currículo: não.

**B5. Qual é o menor salário mensal que vale a pena para você?**
- Por quê: vaga com salário abaixo é escondida; vaga sem salário fica neutra (7 de 15 pontos, `nucleo/dados/encaixe.json`, `salario_neutro`).
- Entra em: **Existe.** `Busca.salario_min_centavos` (`nucleo/modelo.py:239`), critério `nucleo/encaixe.py:121-133`, regra `:167-170`. Já perguntada (`painel/rotas/primeira_execucao.py:125`, `_centavos`).
- Tipo: número (valor por mês, em unidades da moeda de B6).
- Obrig.: não. Currículo: não.

**B6. Em que moeda é esse valor?**
- Por quê: o mínimo é comparado em reais; o joBot converte com a cotação do dia.
- Entra em: **Existe.** `Busca.salario_moeda` (`nucleo/modelo.py:240`), as 11 moedas de `nucleo/cambio.py:25-26` (`MOEDAS` e `MOEDAS_EXIBICAO`); o formulário de buscas usa `painel/rotas/buscas.py:36`.
- Tipo: escolha (BRL mais as 10 do Banco Central). Padrão: a moeda do país de A1.
- Obrig.: só se B5 foi respondida. Currículo: não.

**B7. Em que moeda você quer ver os valores das vagas de fora?**
- Por quê: o salário convertido aparece embaixo, menor, nessa moeda.
- Entra em: **Existe.** Chave `moeda_exibicao` (`banco/cadastros.py:47`, padrão vazio = a do país).
- Tipo: escolha (a do meu país, ou uma das 11).
- Obrig.: não. Currículo: não. Só se pergunta se A1 não for BR (para quem mora no Brasil o padrão serve).

**B8. Que tipo de contrato você procura? (CLT, PJ, estágio, temporário, freelance...)**
- Por quê: o regime muda o valor do salário e o tipo de vaga.
- Entra em: **Novo na busca.** O tipo existe como rótulo da vaga (`nucleo/modelo.py:58-69`, `Contrato`) e como filtro da lista (`banco/leitura.py:41`, `"contrato": "v.contrato = :contrato"`). `Busca` não tem campo de contrato e o encaixe não o usa. Proposta: `Busca.contratos` e, se o dono quiser, uma regra de ocultar "contrato" (seção 6, P2 e P3).
- Tipo: escolha múltipla (os valores de `Contrato`, sem "não informado").
- Obrig.: não. Currículo: não.

### Bloco C. O que aceita

**C1. Você aceitaria mudar de cidade por uma boa vaga?**
- Por quê: decide se o joBot mostra vagas de outras cidades ou só da cidade da pessoa.
- Entra em: **Novo** (`perfil.mudanca`). O resultado vira `Busca.cidades` (`nucleo/modelo.py:236`) e o encaixe por local: cidade igual vale 20, mesma UF 10, fora 0 (`nucleo/encaixe.py:96-100`).
- Tipo: escolha única (não; só no meu estado; em qualquer lugar do meu país; em outro país).
- Obrig.: não. Currículo: não.

**C2. Para quais cidades ou países você se mudaria?**
- Por quê: lista exata das cidades da busca quando C1 não é "não".
- Entra em: **Existe.** `Busca.cidades` (`nucleo/modelo.py:236`), entrada `Entrada.cidades` (`painel/rotas/primeira_execucao.py:90`) com limite de 10 (`:55`, `_MAX_CIDADES`) e leitura em `:116` (`_local`). País de fora entra pelo país da cidade: `paises_das_buscas` (`banco/buscas.py:217-224`) e `nucleo/encaixe.py:147-148`.
- Tipo: lista de texto livre (cidade e UF ou país).
- Obrig.: não. Condicional a C1. Currículo: não.

**C3. Você aceita viajar a trabalho?**
- Por quê: vaga que pede viagem frequente pode não servir.
- Entra em: **Novo** (`perfil.viagem`). Não há rótulo de viagem na vaga (`nucleo/modelo.py:72-75`: `Aviso` só tem visto, doutorado e restrito a país). Hoje a resposta só serve de contexto e de palavra a procurar na descrição; não muda o encaixe. Ver P4.
- Tipo: escolha única (nunca; às vezes; sem problema).
- Obrig.: não. Currículo: não.

**C4. Que horários e escalas você aceita?**
- Por quê: turno noturno, fim de semana e escala 12x36 mudam a vida.
- Entra em: **Novo** (`perfil.horarios`). Sem rótulo na vaga (mesma situação de C3).
- Tipo: escolha múltipla (horário comercial; noturno; fins de semana; escala 12x36; turnos).
- Obrig.: não. Currículo: não.

**C5. Quando você poderia começar?**
- Por quê: vaga de estágio e de programa traz data de início.
- Entra em: **Novo** (`perfil.disponibilidade_inicio`). A vaga já guarda `inicio` (`banco/migracoes/0001_inicial.sql:81`; `nucleo/modelo.py:150`).
- Tipo: escolha (já; em até 30 dias; depois do aviso prévio; numa data) mais data.
- Obrig.: não. Currículo: não.

**C6. Em que países você já pode trabalhar sem visto novo?**
- Por quê: vaga que "exige visto" ou é "restrita a um país" só serve se a pessoa já tem autorização.
- Entra em: **Novo** (`perfil.autorizacao_de_trabalho`, lista de países). Os avisos existem na vaga (`nucleo/modelo.py:72-75`) e a regra "remoto restrito a outro país" também (`nucleo/encaixe.py:172-181`), mas ela só compara com os países das cidades da busca ou o Meu país (`nucleo/encaixe.py:147-148`). A resposta ampliaria esse conjunto.
- Tipo: lista de países (escolha múltipla). Padrão: o país de A1.
- Obrig.: não. Currículo: não.

**C7. Você quer ver vagas que não dizem o salário?**
- Por quê: muita vaga não informa. Hoje elas ficam visíveis com nota neutra (`nucleo/encaixe.py:129-130`); há quem prefira escondê-las.
- Entra em: **Existe em parte.** O filtro "sem salário" já existe na lista (`banco/leitura.py:124`, `Filtros.sem_salario`). A regra de ocultar por falta de salário **não** existe: as regras são cinco (`painel/rotas/buscas.py:32`, `REGRAS`). Proposta: uma sexta regra (P3).
- Tipo: escolha única (sim, mostrar; sim, mas depois das que informam; não, esconder).
- Obrig.: não. Padrão: sim, mostrar. Currículo: não.

**C8. Em que idiomas as vagas podem estar escritas?**
- Por quê: vaga em idioma não aceito é escondida, quando a regra está ligada.
- Entra em: **Existe.** `Busca.idiomas` (`nucleo/modelo.py:241`), critério `nucleo/encaixe.py:136-144`, regra `:171`. Já perguntada (`painel/rotas/primeira_execucao.py:64`, `_IDIOMAS`).
- Tipo: escolha múltipla (pt, en, es). Padrão: os idiomas de A9 com nível intermediário ou mais.
- Obrig.: não. Currículo: parcial (via A9).

**C9. Você aceita contrato por prazo determinado ou por projeto?**
- Por quê: separa o que a pessoa quer (B8) do que ela toparia se faltasse vaga.
- Entra em: **Novo** (`perfil.aceita_prazo_determinado`). Usa os mesmos valores de `Contrato` (`nucleo/modelo.py:58-69`: temporário, freelance, programa).
- Tipo: escolha única (sim; só se pagar melhor; não).
- Obrig.: não. Currículo: não. Se a pessoa já marcou esses contratos em B8, a pergunta é pulada.

### Bloco D. O que recusa

**D1. Há empresas que você não quer ver?**
- Por quê: ex-empregador, empresa com má fama, concorrente. Some da lista sem a pessoa ter de ocultar vaga por vaga.
- Entra em: **Novo** (`busca.empresas_recusadas`). Hoje só há o filtro de lista "empresa contém" (`banco/leitura.py:205`, `_CONTEM["empresa"]`; `Filtros.empresa`, `:109`), que mostra, não esconde. `Empresa` em `nucleo/modelo.py:216` é a fonte de coleta, não lista de recusa. A comparação usaria a mesma normalização do filtro (`jobot_normalizar`, `banco/leitura.py:205`; `normalizar`, `nucleo/texto.py:7`).
- Tipo: lista de texto livre (nomes de empresa).
- Obrig.: não. Currículo: não.

**D2. Há setores em que você não quer trabalhar? (ex.: apostas, tabaco, armas)**
- Por quê: valor pessoal, não técnico. A pessoa não deve ver o que recusou.
- Entra em: **Novo** (`busca.setores_recusados`). A vaga **não tem rótulo de setor**: `Area` é a função (`nucleo/modelo.py:20-37`), não o ramo da empresa. Sem rótulo novo, só dá para transformar cada setor numa lista de palavras. Depende de P5.
- Tipo: escolha múltipla (lista curta fixa) mais texto livre.
- Obrig.: não. Currículo: não.

**D3. Há palavras que, se aparecerem na vaga, você não quer ver? (ex.: "comissão", "plantão")**
- Por quê: o jeito mais direto de cortar o que não interessa.
- Entra em: **Existe em parte.** O filtro "não pode ter estas palavras" já existe na lista (`banco/leitura.py:107`, `Filtros.excluir`; desenho `docs/superpowers/specs/2026-11-15-0-2-0-filtros-moeda-design.md`, "Parte A"). `Busca` não o guarda, e ele não esconde por regra. Proposta: `Busca.palavras_recusadas` e uma regra de ocultar (P3).
- Tipo: lista de texto livre, até 20 palavras de até 100 caracteres (o limite do filtro atual).
- Obrig.: não. Currículo: não.

**D4. Há exigências que fazem uma vaga não servir para você? (exige visto, exige doutorado)**
- Por quê: são os avisos que o joBot já põe nas vagas. A pessoa escolhe quais escondem.
- Entra em: **Existe em parte.** Os avisos existem (`nucleo/modelo.py:72-75`, `Aviso`). Nenhuma regra de ocultar usa "exige visto" nem "exige doutorado"; só `restrito_a_pais` entra na regra `pais` (`nucleo/encaixe.py:172-180`). Proposta: `Busca.avisos_que_escondem` (P3).
- Tipo: escolha múltipla (exige visto; exige doutorado).
- Obrig.: não. Currículo: parcial (A6 sugere "exige doutorado" para quem não tem).

**D5. Quando uma vaga não combina com o que você marcou, quer que o joBot a esconda ou só avise?**
- Por quê: é a chave de todas as regras de ocultar. Quem prefere ver tudo desliga.
- Entra em: **Existe.** `Busca.regras_ocultar` (`nucleo/modelo.py:242`), as cinco regras (`painel/rotas/buscas.py:32`: modalidade, nível, salário, idioma, país) e a chave geral `regras_ocultar_ligadas` (`banco/cadastros.py:43`). Na tela de buscas já se liga e desliga cada regra (`painel/rotas/buscas.py:159` e `:174`).
- Tipo: escolha por regra (esconder; só avisar), com um atalho "esconder tudo" e "só avisar em tudo". Padrão: esconder (hoje todas nascem ligadas, `painel/rotas/buscas.py:57`).
- Obrig.: não. Currículo: não.

## 4. O que já existe e o que é novo

| Pergunta | Situação | Onde |
|---|---|---|
| A1 país | existe | `banco/cadastros.py:46`, `:288` |
| A2 cidade onde mora | novo | `perfil.cidade_moradia` |
| A3 cargo atual | novo | `perfil.cargo_atual` |
| A4 anos de experiência | novo | `perfil.anos_de_experiencia` |
| A5 experiências | novo | `perfil.experiencias` |
| A6 nível de estudo | novo | `perfil.formacao_nivel` |
| A7 curso e situação | novo | `perfil.cursos` |
| A8 habilidades | novo | `perfil.habilidades` |
| A9 idiomas que fala | novo | `perfil.idiomas_falados` |
| B1 cargos | existe | `nucleo/modelo.py:235` |
| B2 área | novo na busca | `Busca.areas` (o rótulo existe, `nucleo/modelo.py:20`) |
| B3 nível | existe | `nucleo/modelo.py:238` |
| B4 modalidade | existe | `nucleo/modelo.py:237` |
| B5 salário mínimo | existe | `nucleo/modelo.py:239` |
| B6 moeda do mínimo | existe | `nucleo/modelo.py:240` |
| B7 moeda de exibição | existe | `banco/cadastros.py:47` |
| B8 contrato procurado | novo na busca | `Busca.contratos` (o rótulo existe, `nucleo/modelo.py:58`) |
| C1 mudar de cidade | novo | `perfil.mudanca` |
| C2 cidades e países | existe | `nucleo/modelo.py:236` |
| C3 viagem | novo | `perfil.viagem` |
| C4 horários | novo | `perfil.horarios` |
| C5 início | novo | `perfil.disponibilidade_inicio` |
| C6 autorização de trabalho | novo | `perfil.autorizacao_de_trabalho` |
| C7 vaga sem salário | existe em parte | filtro `banco/leitura.py:124`; regra nova |
| C8 idioma da vaga | existe | `nucleo/modelo.py:241` |
| C9 prazo determinado | novo | `perfil.aceita_prazo_determinado` |
| D1 empresas | novo | `busca.empresas_recusadas` |
| D2 setores | novo | `busca.setores_recusados` |
| D3 palavras | existe em parte | filtro `banco/leitura.py:107`; campo e regra novos |
| D4 avisos | existe em parte | `nucleo/modelo.py:72`; regra nova |
| D5 esconder ou avisar | existe | `nucleo/modelo.py:242`, `painel/rotas/buscas.py:32` |

Contagem: 31 perguntas. 10 já têm campo e regra hoje (A1, B1, B3, B4, B5, B6, B7, C2, C8, D5). 3 existem em parte, com filtro ou rótulo mas sem campo na busca ou sem regra de ocultar (C7, D3, D4). 2 têm o rótulo na vaga, mas a busca não tem o campo (B2, B8). 16 são campos novos, a maioria do perfil e não da busca (A2 a A9, C1, C3, C4, C5, C6, C9, D1, D2).

### Onde as respostas moram

- **Perfil** (A, C, parte de B): não existe hoje. A ADR 0011 diz que o perfil é a fonte única. Proposta: uma tabela `perfil` de uma linha só, mais tabelas de lista (`experiencia`, `curso`), numa migração `.sql` própria (decisão de esquema, P1).
- **Busca** (B, D): já existe, com várias buscas salvas (ADR 0001; `banco/migracoes/0001_inicial.sql:125`). A primeira busca nasce das respostas do bloco B e do D. Mudar um campo da busca não muda o perfil.
- **Config** (`meu_pais`, `moeda_exibicao`, `regras_ocultar_ligadas`): já existe em `banco/cadastros.py:36-47`.

### Campos novos (resumo)

`perfil.cidade_moradia`, `perfil.cargo_atual`, `perfil.anos_de_experiencia`, `perfil.experiencias`, `perfil.formacao_nivel`, `perfil.cursos`, `perfil.habilidades`, `perfil.idiomas_falados`, `perfil.mudanca`, `perfil.viagem`, `perfil.horarios`, `perfil.disponibilidade_inicio`, `perfil.autorizacao_de_trabalho`, `perfil.aceita_prazo_determinado`, `Busca.areas`, `Busca.contratos`, `busca.empresas_recusadas`, `busca.setores_recusados`, `busca.palavras_recusadas`, `busca.avisos_que_escondem`, `busca.aceita_sem_salario`.

## 5. Fora deste documento

- **A entrevista por IA.** Vem na fase de IA (fase 4 na ADR 0017, desde a D138), e o dono pediu que fique para depois do instalador. Ela usa este mapa como lista de perguntas base e gera as perguntas de lacuna (ADR 0011). Como será a conversa, o prompt, o modelo e o fallback sem IA ficam para o desenho da fase 4. A IA do joBot pode ser local (Qwen, ADR 0009); só entra se a pessoa ligar.
- **As telas.** Layout, ordem na tela, texto exato em `pt` e `en`, microfone e botão "gravar geral" (ADR 0011, "Áudio", fase 6) ficam para o desenho de tela.
- **A leitura do currículo.** Este mapa só diz quais perguntas o PDF pode responder. Extração, revisão e biblioteca (pypdf) são da ADR 0011.
- **Dados que a ADR 0011 põe no perfil e que não são perguntas aqui:** nome, e-mail, telefone, CPF, data de nascimento, links, projetos, cursos avulsos e "perguntas e respostas próprias". Servem à candidatura, não à busca. Entram quando a candidatura for desenhada. CPF e data de nascimento continuam sob a regra da ADR 0014 (só no `jobot.db`, fora da exportação por padrão).
- **Mudar o encaixe e as regras de ocultar.** Os campos novos de busca (área, contrato, empresas, setores, palavras, avisos) só valem se o encaixe e as regras passarem a usá-los. Isso é mudança de `nucleo/encaixe.py` e dos pesos (`nucleo/dados/encaixe.json`), com teste novo, e fica para um desenho próprio.
- **Coletar por perfil.** Usar o perfil para escolher que fontes e cidades buscar (a descoberta ainda segue o critério do Brasil, `docs/superpowers/specs/2026-11-15-0-2-0-filtros-moeda-design.md`, seção 2) não é tratado aqui.

## 6. Perguntas em aberto para o dono

Cada uma vem com a minha recomendação.

**P1. Onde o perfil mora?**
Opções: (a) uma tabela `perfil` nova, e a busca copia o que precisa; (b) tudo na `busca`, sem perfil separado; (c) arquivo JSON fora do banco.
Recomendo (a): a ADR 0011 já diz que o perfil é fonte única, e o banco já tem migração, gatilhos e exportação. (b) mistura "quem sou" com "o que busco hoje" e duplica por busca. (c) foge das regras de gravação do projeto.

**P2. Área e contrato entram no encaixe?**
Hoje o encaixe tem cinco critérios (cargo, local, nível, salário, idioma, `nucleo/dados/encaixe.json:2`). Área e contrato são rótulos da vaga, mas ficam de fora da nota.
Recomendo: sim para os dois, com peso baixo (5 a 10 cada), tirando pontos de cargo e local. Mas mudar a nota muda os rótulos de todas as vagas já gravadas e o teste de rótulos. Se o dono preferir não mexer na nota agora, as respostas ficam só como filtro de lista.

**P3. Que regras de ocultar novas?**
Hoje: modalidade, nível, salário, idioma, país. Candidatas: contrato, empresa recusada, palavra recusada, aviso (visto e doutorado), sem salário.
Recomendo: criar "empresa recusada" e "palavra recusada" (a pessoa pediu explicitamente), "aviso" (já há o rótulo) e deixar "contrato" e "sem salário" como filtro de lista, sem ocultar. Toda regra nova nasce ligada e com o botão "mostrar mesmo assim", como as de hoje.

**P4. Viagem e horário viram rótulo da vaga?**
Hoje a vaga não tem esses rótulos (`nucleo/modelo.py:72-75`). Sem eles, C3 e C4 só guardam a resposta.
Recomendo: deixar para a fase de IA, quando um modelo lê a descrição. Até lá, C3 e C4 são opcionais e aparecem só na revisão do perfil, sem afetar a nota. Alternativa: cortá-las desta primeira versão.

**P5. Setor como rótulo?**
D2 só funciona com um rótulo de setor na vaga, que não existe. Opções: (a) cortar D2 por ora; (b) setor vira lista de palavras por setor (aproximação, erra); (c) rótulo novo, treinado com o gabarito, que fica fora do repositório.
Recomendo (a) até a fase de IA. Se o dono quiser já, (b) com a lista pública e revisável na wiki.

**P6. O que são "faixas" na recusa?**
O pedido diz "empresas, setores, palavras, faixas". Li "faixas" como faixa de salário e nível, que já saem de B3, B5 e D5, e por isso não criei pergunta extra. Se o dono quis dizer outra coisa (faixa de tamanho de empresa, salário máximo, distância), preciso saber. Tamanho de empresa e distância exigem dado que as fontes não trazem hoje.

**P7. Regime e contrato: uma pergunta ou duas?**
Pedi regime em B8 e "aceita prazo determinado" em C9. Pode ser uma só ("escolha os que aceita, marque com estrela o que prefere").
Recomendo manter duas: a pessoa sente a diferença entre "quero" e "toparia", e a lista de B8 fica curta.

**P8. Quantas perguntas?**
A ADR 0011 diz cerca de 25 base. Este mapa tem 31. Com os cortes sugeridos (C3, C4, D2, B7 quando A1 é BR) fica em 27.
Recomendo seguir com 27 e deixar as outras na revisão de perfil, fora do fluxo inicial.

**P9. As respostas valem para todas as buscas ou só para a primeira?**
Recomendo só para a primeira busca (as outras nascem copiadas dela e editam à parte). Mudar o perfil depois não reescreve as buscas já salvas, mas o painel pergunta se a pessoa quer atualizá-las.

**P10. Pedido de salário: bruto ou líquido?**
O joBot compara com o que a vaga diz, que quase sempre é bruto, e a coluna não distingue. Recomendo dizer "bruto" no texto de B5 e não perguntar mais nada.
