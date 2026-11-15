# Versão 0.2.0: filtros novos, país e moeda (desenho)

Data: 2026-11-15. Decisão de origem: D107 (`duvidas.md`). Vem antes da fase 2 (ADR 0017).
Este documento é a especificação para planejar e construir a 0.2.0 sem voltar ao dono. Todo fato sobre o código vem com `arquivo:linha`, conferido na `dev` de 2026-11-15; as linhas podem andar com as tarefas da 0.1.1 (T150 a T156), então procure pelo nome quando a linha não bater.

## 1. Intenção e porquê

Pedido do dono, por voz, em 2026-11-15:

- "colocar pra pessoa poder filtrar, pesquisar por nome, por faixa de salário, por competência, por local, por todas as coisas que você acha que é interessante fazer o filtro";
- "selecionar o país que ela tá e também selecionar a moeda que ela quer";
- o valor convertido "lá embaixo", "uma letrinha menor", "uma cor um pouco mais apagada";
- e a pergunta de como isso funciona com centenas de milhares de vagas.

Por quê: hoje a tela de vagas só filtra por igualdade de um valor (área, nível, modalidade, contrato, UF, fonte, encaixe) e por palavras em AND. Quem procura emprego quer cortar por salário, lugar, empresa e data, e quer ver o salário de fora na moeda que entende. O joBot é usado fora do Brasil também (projeto público), então o país e a moeda não podem ficar presos ao Brasil e ao real.

O que o dono decidiu (D107):

- seis filtros novos: salário de... até...; país; cidade; empresa; publicada há 24 h, 7 dias ou 30 dias; "precisa ter estas palavras" e "não pode ter estas palavras";
- a moeda do valor convertido escolhida entre 11: BRL, USD, EUR, GBP, CAD, AUD, CHF, JPY, SEK, NOK, DKK (o real e as 10 que o Banco Central já fornece; sem fonte nova);
- "Meu país" em Configurações define o país padrão das buscas sem cidade e a moeda padrão; o idioma do painel continua à parte.

"Por competência" hoje é a área e as palavras. Competências por IA e mudança nas regras de rótulo ficam para a fase 3 (D108).

## 2. Objetivos, não objetivos e anti-objetivos

Objetivos

1. A pessoa filtra a lista de vagas pelos seis filtros novos, combinados entre si e com os chips e a busca que já existem.
2. Todo filtro vai para a URL: o link copiado reabre a mesma vista; o voltar do navegador funciona (HTMX com `hx-push-url`).
3. A pessoa escolhe "Meu país" e a moeda de exibição em Configurações; o valor convertido aparece nessa moeda, embaixo do salário, menor e mais apagado.
4. Com centenas de milhares de vagas a tela continua usável: índices novos, paginação de 50 e FTS mantidos, e um jeito de medir.

Não objetivos (ficam como estão)

- O encaixe continua comparando em reais (`minimo_busca_brl`, `nucleo/encaixe.py:122-131`).
- A ordem "salário" continua pelo valor em reais (`ORDENS["salario"]`, `banco/leitura.py:59,60-66`).
- A descoberta automática de quadros continua pelo critério do Brasil: `_no_brasil_ou_remota` aceita a vaga remota ou com local no Brasil (`nucleo/coletores/descoberta_cc.py:228-230`). Com Meu país diferente de BR ela sugere quadros pelo critério do Brasil. Fica para depois: o construtor registra uma D no `duvidas.md` ("descoberta pelo Meu país"), sem código na 0.2.0.
- O país de reserva dos coletores quando nenhuma busca ativa manda país (o "testar" do painel) continua o deles: `_PADRAO` do Workday, do Oracle e do Eightfold (`nucleo/coletores/workday.py:41`, `oracle_hcm.py:46`, `eightfold.py:64`). Com busca ativa eles já recebem o `ctx.paises`, que passa a vir do Meu país (parte G).
- O formulário de buscas e a primeira execução continuam oferecendo BRL e as 10 do PTAX (`painel/rotas/buscas.py:36`, `painel/rotas/primeira_execucao.py:208`).
- Moeda fora das 11, outra fonte de câmbio, filtro por competência com IA (fase 3, D108).
- Sem chips novos para cidade e empresa (são caixas de texto).

Anti-objetivos (o que a 0.2.0 não pode fazer)

- Nunca 422 por parâmetro torto na URL: cai no padrão (`painel/rotas/vagas.py:3`).
- Nunca esconder vaga em silêncio: todo filtro que corta por falta de dado (sem salário, sem cotação) diz isso na tela.
- Nunca apagar nem reescrever vaga para filtrar: filtro é só leitura.
- Nunca contatar serviço novo: a única fonte de câmbio continua o PTAX do Banco Central (ADR 0014).
- Nunca mostrar número de dinheiro duvidoso: salário implausível (`sal_plausivel = 0`) não entra no filtro nem na conversão (`painel/formatos.py:87-90`).

## 3. Restrições

Do `CLAUDE.md` do projeto e das lições (`registros/padroes.md`):

- Painel só em `127.0.0.1`, sem recurso externo, CSP sem script inline; texto de fora sempre escapado.
- Mudança de esquema por migração `.sql` em `src/jobot/banco/migracoes/`. A 0.1.1 usa a 0004 (T153, ainda não está na `dev`); a 0.2.0 usa a próxima livre, a 0005. A versão do banco nos testes vem de `ULTIMA` (`tests/integracao/test_migracoes.py:13`).
- Gravação: `INSERT ... ON CONFLICT DO UPDATE`, nunca `INSERT OR REPLACE`; nada é apagado (`vaga_sem_delete`, `banco/migracoes/0001_inicial.sql:97`). A 0005 só cria índices: não reconstrói `vaga`, não mexe em gatilho nem no FTS.
- Sem dependência nova. Lista de países, mapa país para moeda e símbolos ficam no código.
- Todo texto novo da tela entra em `i18n/pt` e `i18n/en`, com o mesmo conjunto de chaves; chave com parâmetro é contrato.
- Link torto cai no padrão, nunca dá 422: todo parâmetro novo é lido à mão em `_ler_estado` (`painel/rotas/vagas.py:151-172`).
- Dinheiro em inteiros: `Salario` em centavos da moeda original, reais inteiros só nas colunas `_brl` (`0001_inicial.sql:71-77`); conta exata com `Decimal(int)` e o contexto exato, nunca `Decimal(str(int))`, nunca `float` (lição de dinheiro em `registros/padroes.md`). O contexto exato do projeto (`Context(prec=MAX_PREC)`, `nucleo/cambio.py:22`, `nucleo/tratamento/salario.py:42`) só serve para multiplicar e somar: uma divisão que não termina, nesse contexto, levanta `MemoryError` (conferido: `Context(prec=MAX_PREC).divide(Decimal(500000), Decimal("0.0368"))`). Toda divisão de dinheiro desta versão usa `Fraction` com arredondamento à mão (parte G). Toda coluna derivada cabe no INTEGER de 64 bits.
- Dia de calendário compara com o dia local; instante ("há 24 h") compara com o relógio injetado em UTC.
- O painel não importa `httpx` (`tests/unidade/test_camadas.py:48-49`): o painel nunca busca cotação, só lê a tabela `cotacao`.
- Termo do usuário no MATCH: aspas em volta, aspa dobrada, Cc e Cs viram espaço, também no LIKE (`banco/leitura.py:175-188`).

## 4. Como funciona hoje (fatos conferidos)

Banco

- `vaga` (`0001_inicial.sql:61-91`): `empresa` (`:65`), `sal_moeda`, `sal_min`, `sal_max`, `sal_periodo` (`:71`), `sal_mensal_min` em centavos da moeda original (`:72`), `sal_mensal_min_brl` e `sal_mensal_max_brl` em reais inteiros (`:73-74`; vaga em BRL vale centavos ÷ 100 mesmo com a conversão desligada, `:75-76`), `sal_cotacao_data` (`:77`), `sal_plausivel` (`:78`), `publicada_em` (`:81`, gravada em UTC ISO, `banco/gravacao.py:150`), `primeira_vista_em` (`:82`).
- Índices de `vaga`: `vaga_lista`, `vaga_primeira_vista` (já existe, em `primeira_vista_em`), `vaga_prazo`, `vaga_empresa` (`0001_inicial.sql:92-95`). Não há índice em `publicada_em` nem nas colunas `_brl`.
- `local_vaga(vaga_id, cidade, uf, pais)` (`0001_inicial.sql:103-106`) só tem índice em `uf` (`:107`). Não há índice em `vaga_id`, `pais` nem `cidade`. Correção ao brief: o filtro de UF já existente roda `EXISTS (... l.vaga_id = v.id ...)` (`banco/leitura.py:42`) sem índice em `vaga_id`; com muitas vagas isso é varredura de `local_vaga` por vaga. A 0005 corrige.
- `vaga_fts` (`banco/migrar.py:14-34`): `content='vaga'`, colunas `titulo, empresa, descricao_texto`, `unicode61 remove_diacritics 2`, gatilhos de insert e update; só existe com FTS5 (`banco/migrar.py:69-70`).
- `cotacao(moeda, data, venda, buscada_em)`, chave `(moeda, data)`, `venda` em reais por 1 unidade, decimal em texto (`0001_inicial.sql:176-182`).
- `config(chave, valor JSON)` (`0001_inicial.sql:214`).

Leitura da lista

- `Filtros` é dataclass frozen kw_only com `aba, busca_id, q, area, nivel, modalidade, contrato, uf, fonte, encaixe, ordem, pagina` (`banco/leitura.py:85-98`).
- `_FILTROS` cobre só igualdade de valor único (`banco/leitura.py:37-45`); `_CHIPS` conta cada grupo com os outros filtros ligados, via `_onde(sem=)` (`:48-56`, `:196-215`, `:251-269`).
- `_busca` usa `MATCH` com `"palavra"*` em AND no FTS e, sem FTS, `LIKE` sobre `jobot_normalizar(titulo || empresa || descricao)` (`banco/leitura.py:175-188`). Não há busca negativa.
- `ORDENS`: encaixe, recentes (`julianday(COALESCE(publicada_em, primeira_vista_em))`), prazo, salario (ignora `sal_plausivel = 0`), empresa (`_RECENTES` e `_SALARIO` em `banco/leitura.py:58-59`, `ORDENS` em `:60-66`). `POR_PAGINA = 50` (`:18`).

Rota e tela

- `painel/rotas/vagas.py`: `_texto` limpa e corta em 100 (`:45`, `:73-75`); `CHIPS` (`:31`); `Estado` (`:98-148`) com `filtros()` (`:115-129`) e `url()` (`:131-148`); `_ler_estado` (`:151-172`); `campos_ocultos` (`:351`); `_grupos` monta os chips com contagem e rótulo por `_ROTULO_CHIP` (`:34-44`, `:248-281`). O relógio do painel é `relogio_do_painel` (`:55-57`).
- `templates/vagas/miolo.html`: `form.busca` com `hx-trigger="submit, change from:#ordem"` e `hx-target="#vagas-miolo"` (`:21`), campos ocultos dos chips (`:26-28`), `input#busca-q name=q maxlength=100 data-busca` (`:30`), botão Buscar (`:31`), `select#ordem` (`:33-38`); `div.filtros` com os grupos de chips (`:42-56`), cada chip é um botão `hx-get` para a URL do `Estado`.
- Salário no cartão: `templates/vagas/corpo.html:43-46` (valor em `strong`, `em-reais` e `cotacao` na mesma linha); no detalhe: `templates/detalhe/pagina.html:44-47` (cotação e "≈" juntos num `small`). CSS: `.em-reais` e `.cotacao` já usam `var(--texto-2)` (`static/css/vagas.css:277-281`), mas no mesmo tamanho e ao lado do valor.
- Token de texto secundário já existe: `--texto-2` (`static/css/base.css:31`). Não precisa de cor nova.

Câmbio e moeda

- `nucleo/cambio.py`: `MOEDAS` são as 10 do PTAX (`:15`), `buscar_cotacao` (`:92`), `em_reais` (`:105-113`).
- `banco/cotacoes.py`: `_BRL` (`:14`), validade de 7 dias (`:15`), `moedas_em_aberto` (`:19-24`), `cotacao_mais_recente` (`:59-76`), `aplicar_cotacoes` (`:106` em diante; conversão desligada deixa `NULL` nas `_brl` de toda vaga em moeda estrangeira, `:136-137`).
- `_cotacoes` (`agenda/execucao.py:301-317`) busca só as moedas de `moedas_em_aberto` e só com `conversao_moeda_ligada`.
- `painel/formatos.py`: `_SIMBOLO` só tem USD, BRL, EUR, GBP (`:16`); `salario_texto` devolve `SalarioTexto(original, cotacao, em_reais)` (`:23-26`, `:87-112`); vaga em BRL não ganha linha de conversão (`:96-97`).
- i18n: `vagas.cotacao` tem `R$` fixo (`i18n/pt/vagas.json:78`, `i18n/en/vagas.json:78`); `vagas.em_reais` é `"≈ {valor}"` (`i18n/pt/vagas.json:79`).

País e configuração

- `banco/cadastros.py`: `ler_config` (`:225`), `gravar_config` (`:239`), `PADROES` (`:32-42`).
- Configurações: `rotas/configuracoes.py` com `GRUPOS = ("fontes", "funcoes", "segundo-plano", "aparencia", "privacidade")` (`:34`), `FUNCOES` (`:35`), `_ctx_aparencia` vazio (`:90-91`), `_gravar_funcoes` (`:152`); o idioma fica em Aparência pelas rotas `/preferencias` (`templates/configuracoes/aparencia.html:15-22`).
- `paises_das_buscas` usa `{"BR"}` fixo para busca sem cidade (`banco/buscas.py:216-222`) e vai para o contexto dos coletores (`agenda/execucao.py:150`).
- O encaixe também tem BR fixo: `_pais_da_pessoa` devolve os países das cidades da busca ou, sem cidade, `{"BR"}` (`nucleo/encaixe.py:147-148`). Esse valor alimenta a regra de ocultar `pais`: vaga remota restrita a um país que não é o da pessoa (`nucleo/encaixe.py:167-176`). O encaixe é gravado por `_recalcular` (`banco/buscas.py:289-340`), que chama `calcular` (`:323-329`); todos os caminhos passam por ele: `criar_busca` e `editar_busca` (`:157`, `:177`), `recalcular_encaixe` (`:343-360`) chamado pela execução (`agenda/execucao.py:99`), pela tela de Funções quando muda a conversão ou as regras (`painel/rotas/configuracoes.py:175-179`, que recalcula antes de gravar a chave) e pela correção da vaga (`painel/rotas/detalhe.py:248`).
- Correção ao brief: `nucleo/tratamento/locais.py:232-233` (`if uf and not pais: pais = "BR"`) não é país padrão: é "sigla de UF brasileira implica Brasil". Fica como está; Meu país não mexe nele.
- `locais._PAISES` (`nucleo/tratamento/locais.py:15-77`) tem 106 nomes e 55 códigos ISO (não 62); `nome_do_pais` (`:264-266`) e `nome_em_ingles` (`:273-276`). Não há mapa país para moeda.
- O idioma inicial vem do `Accept-Language` (`painel/i18n.py:36`, `painel/seguranca.py:68-82`).

## 5. O como decidido, por parte

### Parte A. Palavras: "precisa ter" e "não pode ter"

- "Precisa ter estas palavras" é a caixa `q` que já existe (AND, prefixo). Muda só o rótulo e a dica, se o construtor achar que ajuda; o parâmetro continua `q`.
- Campo novo "Não pode ter estas palavras", parâmetro de URL `excluir`, limpo por `_texto` (até 100 caracteres, `painel/rotas/vagas.py:73-75`), `maxlength="100"` no HTML.
- Campo novo `excluir: str = ""` em `Filtros`. Exclui a vaga que tiver qualquer uma das palavras:
  - com FTS: `v.id NOT IN (SELECT rowid FROM vaga_fts WHERE vaga_fts MATCH :fts_excluir)`, com `:fts_excluir` = `"w1"* OR "w2"*`, cada palavra com a mesma limpeza do `_busca` (aspas, aspa dobrada, Cc e Cs viram espaço, palavra sem letra nem número some);
  - sem FTS: `NOT (texto LIKE :e0 ESCAPE '\' OR texto LIKE :e1 ...)`, com o mesmo `texto` e o mesmo `_escapar_like` do `_busca`.
- Reaproveite o preparo das palavras do `_busca` (extraia a lista de palavras limpas para uma função usada pelos dois). Campo vazio ou só pontuação: sem condição.

### Parte B. Salário de... até...

- Parâmetros `sal_de` e `sal_ate`: inteiros, em unidades inteiras da moeda de exibição Y (sem centavos), por mês. Lidos com `inteiro_da_url` (`painel/rotas/vagas.py:65-70`) com teto `10**12`; outra coisa (letra, zero, negativo, enorme) é como não ter vindo. `sal_de > sal_ate`: troque os dois (link torto cai num valor útil, não em lista vazia).
- Campos novos em `Filtros`: `sal_de_brl: int | None`, `sal_ate_brl: int | None` (já em reais inteiros) e, para o caso da conversão desligada, `sal_moeda: str | None` com `sal_de_centavos`/`sal_ate_centavos`. A rota converte; `banco/leitura.py` só compara inteiros.
- Conversão Y para BRL, na rota (ou num helper puro em `nucleo/cambio.py`): `reais = Decimal(valor) * venda_Y`, com `venda_Y` de `cotacao_mais_recente(con, Y, hoje=dia_local)`. "De" arredonda para baixo, "até" para cima (o filtro nunca corta uma vaga por arredondamento). Y = BRL: sem conversão.
- Três grupos de vaga, que não se misturam (uma coluna `_brl` nula não quer dizer "sem salário": ela também fica nula com a conversão desligada, sem cotação de X ou quando o valor em reais não cabe no INTEGER, `banco/cotacoes.py:85-87,132-137`):
  - **sem salário**: `v.sal_moeda IS NULL OR (v.sal_min IS NULL AND v.sal_max IS NULL) OR v.sal_plausivel = 0`. É o mesmo critério da tela, que não mostra salário nesses casos (`painel/formatos.py:90-93`);
  - **com salário e sem valor convertido**: não é "sem salário" e `v.sal_mensal_min_brl IS NULL AND v.sal_mensal_max_brl IS NULL`;
  - **com valor comparável**: o resto.
- Faixa da vaga em reais: baixo = `COALESCE(v.sal_mensal_min_brl, v.sal_mensal_max_brl)` e alto = `COALESCE(v.sal_mensal_max_brl, v.sal_mensal_min_brl)`. Vaga só com máximo ("até 8 mil") ou só com mínimo usa o mesmo número nas duas pontas.
- Condição (conversão ligada, ou Y = BRL), por sobreposição de faixas, com essas expressões escritas exatamente assim (são as dos índices da parte H):
  `v.sal_plausivel IS NOT 0 AND COALESCE(v.sal_mensal_max_brl, v.sal_mensal_min_brl) >= :sal_de_brl AND COALESCE(v.sal_mensal_min_brl, v.sal_mensal_max_brl) <= :sal_ate_brl` (cada lado só quando o valor veio; com um lado só, a vaga sem valor convertido cai fora porque `NULL >= x` não é verdadeiro).
- Conversão desligada e Y diferente de BRL: só compara vagas pagas em Y (`v.sal_moeda = :sal_moeda`), em centavos da moeda original (valor digitado `* 100`):
  - baixo = `COALESCE(v.sal_mensal_min, <máximo mensal>)` e alto = `COALESCE(<máximo mensal>, v.sal_mensal_min)`;
  - `<máximo mensal>` sai de `sal_max` e `sal_periodo`, com os fatores de `PARA_MENSAL` (`nucleo/tratamento/salario.py:43-49`), do mesmo jeito que `mensal` (`:261-262`) e `_calcula` (`banco/cotacoes.py:100-102`, período fora da lista dá nulo):
    `CASE v.sal_periodo WHEN 'hora' THEN v.sal_max * 160 WHEN 'dia' THEN v.sal_max * 21 WHEN 'semana' THEN round(v.sal_max * 4.33) WHEN 'mes' THEN v.sal_max WHEN 'ano' THEN round(v.sal_max / 12.0) END`.
    O `round` do SQLite arredonda o meio para longe do zero e o do Python para o par: diferença de no máximo 1 centavo, sem efeito num filtro digitado em unidades inteiras;
  - esse modo não tem índice (é o modo raro); aceito e medido na parte H;
  - a tela mostra um aviso: "Com a conversão desligada, o filtro de salário só olha vagas pagas em {moeda}."
- Conversão ligada e sem cotação de Y nos últimos 7 dias: o filtro não corta nada e a tela avisa: "Ainda não temos a cotação de {moeda}; o filtro de salário fica desligado até a próxima busca."
- Vaga sem salário: fica fora quando o filtro está ligado (pergunta 1, recomendação sim), com aviso "N vagas sem salário ficaram de fora" e um link "Mostrar também" que liga `sem_salario=1` (parâmetro booleano: só `1` vale; outro valor é como não ter vindo). Com `sem_salario=1`, a condição vira `(<condição acima>) OR (<sem salário>)`, nos dois modos; nunca `OR v.sal_mensal_min_brl IS NULL`, que traria de volta, no modo desligado, toda vaga em moeda estrangeira.
- Vaga com salário e sem valor convertido (conversão desligada com Y = BRL, sem cotação de X, valor que não cabe): fica fora e ganha aviso próprio, "N vagas em outra moeda, sem valor convertido, ficaram de fora", com o que fazer (ligar a conversão ou esperar a próxima busca). Não entra no `sem_salario=1`. No modo desligado com Y ≠ BRL, o aviso desse modo já explica as vagas de outras moedas.
- As duas contagens dos avisos usam os mesmos filtros ligados, sem o de salário, e as definições acima: nenhuma vaga é contada no aviso errado.

### Parte C. Publicada há 24 h, 7 dias ou 30 dias

- Grupo de chips `publicada` com três valores fixos: `24h`, `7d`, `30d`. Valor fora desses três é ignorado.
- Condição: `julianday(COALESCE(v.publicada_em, v.primeira_vista_em)) >= julianday(:agora) - :dias`, com `:dias` = 1, 7 ou 30 e `:agora` do relógio do painel (já entra em `_onde`, `banco/leitura.py:201-205`). É instante, não dia de calendário: "há 24 h" é 24 horas antes de agora.
- Contagem: os três valores se sobrepõem (24 h está dentro de 7 dias), então não servem ao `GROUP BY` do `contar_chips`. Conte com uma consulta só, `SUM(CASE ...)` para os três, com os outros filtros ligados (`_onde(sem="publicada")`).
- Ordem dos chips: 24 h, 7 dias, 30 dias (fixa, como o encaixe em `_ordem_chip`, `painel/rotas/vagas.py:244-245`).

### Parte D. País

- Grupo de chips `pais`, como o de UF: `_FILTROS["pais"] = "EXISTS (SELECT 1 FROM local_vaga l WHERE l.vaga_id = v.id AND l.pais = :pais)"` e `_CHIPS["pais"] = ("l.pais", "JOIN local_vaga l ON l.vaga_id = v.id")`.
- Valor da URL: duas letras ASCII em maiúsculas que existam em `_PAISES` (`nome_do_pais(codigo) is not None`); outro valor é ignorado.
- Rótulo pela língua da tela: `nome_do_pais` em pt, `nome_em_ingles` em en. Código sem nome mostra o próprio código. O rótulo não vem do catálogo de i18n, então `_ROTULO_CHIP["pais"]` é `None` e `_grupos` passa o texto pronto (hoje o template monta o texto por `rotulo(chip.chave, chip.valor)` ou mostra o valor cru, `templates/vagas/miolo.html:47`).
- Ordem: do mais contado para o menos (como os outros).

### Parte E. Cidade e empresa

- Caixas de texto, parâmetros `cidade` e `empresa`, limpos por `_texto` (100 caracteres).
- Casa por "contém" normalizado: `jobot_normalizar(v.empresa) LIKE :empresa ESCAPE '\'` e `EXISTS (SELECT 1 FROM local_vaga l WHERE l.vaga_id = v.id AND jobot_normalizar(COALESCE(l.cidade, '')) LIKE :cidade ESCAPE '\')`, com `%` + `_escapar_like(normalizar(texto))` + `%` e a mesma limpeza de Cc e Cs.
- `local_vaga.cidade` aceita nulo e quase sempre vem nulo (local só de UF ou só de país; a semeadura grava `NULL`, `tests/apoio/semear.py:79`). `jobot_normalizar` é `normalizar` (`banco/leitura.py:163`), que levanta `TypeError` com `None` (`nucleo/texto.py:7-12`); dentro do SQLite isso vira `OperationalError` e a tela daria 500. Por isso o `COALESCE(l.cidade, '')` é obrigatório. `l.cidade IS NOT NULL AND ...` não protege: o SQLite não garante a ordem do `AND`. `v.empresa` é `NOT NULL` (`0001_inicial.sql:65`) e não precisa.
- "Contém" não usa índice (o `vaga_empresa` é sobre o texto cru, `0001_inicial.sql:95`): custo linear, aceito e medido na parte H.

### Parte F. Onde ficam na tela

- Um `<details class="mais-filtros">` com `<summary>` "Mais filtros" dentro do `form.busca`, depois da caixa de busca. Dentro: salário de/até (dois `input type="number" min="1" step="1" inputmode="numeric"` com a moeda Y escrita ao lado), cidade, empresa e "não pode ter estas palavras", com `label` visível em cada um.
- Fechado por padrão; o servidor renderiza `open` quando algum campo dele está preenchido. Um contador no `summary` ("Mais filtros (2)") mostra quantos estão ligados.
- Desvio do que a sessão decidiu (que punha tudo no `<details>`): os grupos de chips `pais` e `publicada` ficam no `div.filtros`, junto dos outros chips. Motivo: o chip mostra a contagem e corta a lista num clique, como os de UF e modalidade (`painel/rotas/vagas.py:248-281`, `templates/vagas/miolo.html:42-56`); escondido, a pessoa não vê quantas vagas há por país nem por data. Os chips são `type=button` com `hx-get` e funcionariam também dentro do `<details>`, então as duas opções custam o mesmo. Quem decide é o dono, na pergunta 3.
- Tudo vai para a URL pelo mesmo caminho dos chips:
  - `_ler_estado` lê `excluir`, `sal_de`, `sal_ate`, `sem_salario`, `cidade`, `empresa`, `pais`, `publicada`;
  - `Estado` ganha os campos de texto e de salário; `pais` e `publicada` entram em `CHIPS` e em `Estado.chips`;
  - `Estado.filtros()` passa tudo para `Filtros`;
  - `Estado.url()` põe os campos novos em toda URL (chips, abas, "mais"), para que clicar num chip não perca o filtro de salário;
  - `campos_ocultos` já cobre os chips (`painel/rotas/vagas.py:351`); os campos do `<details>` são campos do próprio formulário, não ocultos.
- O formulário continua mandando com Enter e com o botão Buscar; o `hx-trigger` não muda.
- Link torto em qualquer parâmetro novo cai no padrão (ignorado), nunca 422.

### Parte G. Moeda de exibição e "Meu país"

Configuração

- Chaves novas em `config`, com padrão em `PADROES` (`banco/cadastros.py:32-42`): `meu_pais` (padrão `"BR"`) e `moeda_exibicao` (padrão `""` = segue o país).
- Mapa país para moeda, puro, em `nucleo/cambio.py` (ex.: `moeda_do_pais(pais) -> str` e `MOEDAS_EXIBICAO = ("BRL", *MOEDAS)`, as 11):
  BR BRL; zona do euro EUR (dos códigos de `_PAISES`: AT, BE, DE, ES, FI, FR, GR, IE, IT, NL, PT); US USD; GB GBP; CA CAD; AU AUD; CH CHF; JP JPY; SE SEK; NO NOK; DK DKK; os demais caem em USD (pergunta 4).
- Moeda efetiva Y = `moeda_exibicao` se estiver entre as 11, senão `moeda_do_pais(meu_pais)`. Valor gravado inválido (código fora de `_PAISES`, moeda fora das 11) cai no padrão, sem erro.
- Tela: em Configurações > Aparência (onde já está o idioma, `templates/configuracoes/aparencia.html`), dois campos: "Meu país" (`select` com os 55 países de `_PAISES`, nome na língua da tela, em ordem alfabética) e "Moeda dos valores convertidos" (`select` com "A do meu país ({moeda})" e as 11). Texto de ajuda: "Usado nas buscas sem cidade e para escolher a moeda. O idioma do painel é escolhido à parte." Gravação no mesmo padrão de `_gravar_*` de `rotas/configuracoes.py`.
- `paises_das_buscas` (`banco/buscas.py:221`) troca o `{"BR"}` fixo por `{meu_pais}`. Sem busca ativa continua devolvendo `()` (`tests/integracao/test_buscas.py:148`); os coletores mantêm o padrão deles.
- Encaixe: `_pais_da_pessoa` (`nucleo/encaixe.py:147-148`, núcleo puro) troca o `{"BR"}` fixo por `{pais_padrao}`, recebido por parâmetro: `calcular` ganha o argumento nomeado `pais_padrao: str` (`nucleo/encaixe.py:188-195`) e o repassa a `_regra_que_bate`. Busca com cidade continua usando os países das cidades; só a busca sem cidade usa o Meu país. O núcleo não lê config.
- Quem chama: `_recalcular` (`banco/buscas.py:289`) lê `meu_pais` uma vez por chamada (com o mesmo tratamento de valor inválido, que cai em BR) e passa a `calcular`. Assim os cinco caminhos que gravam encaixe (criar e editar busca, execução, Funções, correção da vaga) usam o Meu país sem mudança neles. `recalcular_encaixe` ganha `pais_padrao: str | None = None` (`None` = ler a config), para quem precisa recalcular com um valor ainda não gravado.
- Quando recalcula: ao salvar um Meu país diferente do gravado, a rota de Configurações chama `recalcular_encaixe(con, None, regras, hoje=hoje, pais_padrao=novo)` e só depois grava a chave, no mesmo padrão de Funções (`painel/rotas/configuracoes.py:175-181`: se o recálculo falhar, a chave fica como estava e salvar de novo refaz). Trocar só a moeda de exibição não recalcula (o encaixe compara em BRL). Na primeira execução, grave o Meu país antes de criar as buscas (`painel/rotas/primeira_execucao.py:313`), para que `criar_busca` já calcule o encaixe com ele.
- Primeira execução, passo 1: "Meu país" já marcado (pergunta 2). O padrão vem da região do `Accept-Language` (`pt-BR` dá BR, `en-GB` dá GB), só se a região estiver em `_PAISES`; sem região ou desconhecida, BR.

Cotação

- `_cotacoes` (`agenda/execucao.py:301-317`) passa a buscar também Y quando Y não é BRL e não está em `moedas_em_aberto`. Uma consulta a mais por dia ao mesmo serviço do Banco Central, já declarado (ADR 0014); continua só com `conversao_moeda_ligada`.
- O painel não busca cotação. Ao trocar a moeda, até a próxima busca a tela mostra a nota de "sem cotação" (abaixo).

Exibição (cartão e detalhe)

- O "≈ valor" aparece em Y, numa linha própria embaixo do salário, com letra menor e `color: var(--texto-2)` (o token de texto secundário que já existe, `static/css/base.css:31`). No cartão (`templates/vagas/corpo.html:43-46`) e no detalhe (`templates/detalhe/pagina.html:44-47`), o mesmo desenho. A cotação vai junto, na mesma linha pequena.
- Quando aparece:
  - vaga paga em Y: sem linha de conversão (nada a converter);
  - vaga paga em X diferente de Y, conversão ligada, cotação de X e de Y válidas: "≈ {valor em Y}/mês";
  - vaga paga em BRL e Y diferente de BRL: também converte (hoje a vaga em BRL nunca ganha linha, `painel/formatos.py:96-97`);
  - conversão desligada: sem linha de conversão, como hoje;
  - sem cotação de Y: mostra o valor em reais, como hoje, com uma nota curta: "em reais: ainda não temos a cotação de {moeda}".
- Conta, sem `Decimal` na divisão (o contexto exato levanta `MemoryError` em divisão que não termina, seção 3): `unidades = Fraction(reais) / Fraction(venda_Y)` (`Fraction` aceita o `Decimal` da cotação sem perda), arredondada à mão para o inteiro mais próximo com o meio para cima (`q, r = divmod(u.numerator, u.denominator)`; `q + 1` se `2 * r >= u.denominator`), e `centavos_Y = unidades * 100` (unidade inteira de Y: é um "≈", e resolve o JPY, que não tem centavos), passado a `dinheiro(centavos_Y, Y, idioma)`. Conferido: 5.000 reais a 6,25 dá 80.000 centavos (€ 800); a 0,0368 dá 13.587.000 centavos (¥ 135.870). A conversão Y para BRL do filtro (parte B) é multiplicação e pode seguir no contexto exato. `dinheiro` recebe centavos (`painel/formatos.py:37-42`), como já faz o `em_reais` hoje (`reais × 100`, `:107-109`); passar unidades mostraria um valor 100 vezes menor. Os reais vêm de `sal_mensal_min_brl` e `sal_mensal_max_brl`.
- Texto da cotação deixa de ter `R$` fixo (`i18n/*/vagas.json:78`) e mostra a taxa cruzada `venda_X / venda_Y`: "{um} = {taxa} (PTAX de {data})", com `um` e `taxa` já formatados com símbolo. Quando X é BRL, mostre 1 unidade de Y em reais (o PTAX como sai), para não aparecer uma fração minúscula. A data é a mais antiga das duas cotações usadas. A taxa cruzada é só para mostrar: calcule com precisão limitada (`Context(prec=34, rounding=ROUND_HALF_UP).divide(venda_X, venda_Y)`) e depois `quantize` para as casas que vão para a tela (ou `Fraction` com o mesmo arredondamento à mão); nunca divida no contexto exato.
- `_SIMBOLO` (`painel/formatos.py:16`) ganha os símbolos que faltam: CAD `C$`, AUD `A$`, CHF `CHF`, JPY `¥`, SEK `kr`, NOK `kr`, DKK `kr`. Para não confundir as três coroas, o construtor pode preferir o código (`SEK`) ao `kr`; decida e teste.
- `vagas.em_reais` muda de nome ou de texto se deixar de ser "em reais"; chave com parâmetro é contrato: mude o template, pt e en juntos.
- O encaixe continua comparando em BRL.

### Parte H. Desempenho com centenas de milhares de vagas

Migração `0005_filtros.sql` (só índices):

- `CREATE INDEX local_vaga_vaga ON local_vaga(vaga_id);` (o `EXISTS` de UF, país e cidade).
- `CREATE INDEX local_vaga_pais ON local_vaga(pais, vaga_id);` (chip de país).
- `CREATE INDEX vaga_publicada_ou_vista ON vaga(julianday(COALESCE(publicada_em, primeira_vista_em)));` (filtro "publicada há" e ordem "recentes", que usam essa mesma expressão, `banco/leitura.py:58`). Correção ao brief: `primeira_vista_em` já tem índice (`0001_inicial.sql:93`) e um índice só em `publicada_em` não serve à expressão com `COALESCE`.
  Risco que este índice cria: com `julianday()` num índice, todo `INSERT` ou `UPDATE` que gravar em `publicada_em` ou `primeira_vista_em` um texto que dependa do relógio do SQLite (como `'now'`) falha com "non-deterministic use of julianday() in an index" (conferido no sqlite3; `NULL` passa). Hoje os dois só recebem ISO em UTC: `publicada_em` por `_utc` (`banco/gravacao.py:106-109`, `:150`) e `primeira_vista_em` pelo `:agora` do `INSERT` da vaga (`banco/gravacao.py:358-359`, `quando = _utc(agora)` em `:299`). Daqui em diante, todo caminho que grava essas colunas usa ISO vindo do relógio injetado, nunca `'now'` nem `CURRENT_TIMESTAMP`.
- `CREATE INDEX vaga_sal_baixo_brl ON vaga(COALESCE(sal_mensal_min_brl, sal_mensal_max_brl));` e `CREATE INDEX vaga_sal_alto_brl ON vaga(COALESCE(sal_mensal_max_brl, sal_mensal_min_brl));` (as expressões exatas da condição da parte B). Índice na coluna simples não serve: com `COALESCE(a, b) >= ?` o SQLite não usa um índice só em `a` e varre a tabela. Conferido com `EXPLAIN QUERY PLAN` num esquema mínimo: com os índices de expressão, "só de", "só até" e os dois juntos saem como `SEARCH ... USING INDEX`. A ordem "salario" usa outra expressão (`CASE`, `banco/leitura.py:59`) e continua sem índice; fica como está.

Continuam a paginação de 50 (`banco/leitura.py:18`) e o FTS para palavras, inclusive "não pode ter".

Como medir:

- Teste automático (roda no CI, sem tempo): base em memória com o esquema real (`migrar(con, Path(":memory:"))`), algumas centenas de vagas semeadas, e `EXPLAIN QUERY PLAN` da consulta de `listar` com cada filtro novo; afirma que aparece `USING INDEX` com o índice esperado (país, publicada; salário com "só de", "só até" e os dois juntos, aceitando qualquer um dos dois índices de salário no caso dos dois juntos) e, em cada `EXISTS` de `local_vaga`, o índice próprio dele: país com `local_vaga_pais (pais=? AND vaga_id=?)`, que cobre a consulta e é o que o SQLite prefere; UF e cidade com `local_vaga_vaga (vaga_id=?)` (conferido com `EXPLAIN QUERY PLAN` num esquema mínimo com os índices da 0005). Não mede tempo (instável no CI).
- Medição à mão (script em `scripts/`, fora do CI): semeia 300 mil vagas com locais e salários variados num arquivo temporário e cronometra `listar`, `contar_chips` e `contar_abas` com cada filtro e com todos juntos.
- Limite aceito: a página de vagas (lista, chips e abas) responde em menos de 1 s com 300 mil vagas numa máquina comum. Cidade e empresa por "contém" são lineares; se passarem do limite, a próxima versão troca por prefixo ou por FTS (registrar como D, não agora).

## 6. O que fica para o construtor

- Nomes finais de funções, de chaves de i18n e de classes CSS, seguindo o padrão das existentes.
- Onde mora a conversão Y para BRL do filtro (rota ou helper puro em `nucleo/cambio.py`); a regra (arredondar "de" para baixo e "até" para cima) é fixa.
- Se o `SUM(CASE ...)` de `publicada` entra no `contar_chips` ou numa função própria.
- Símbolo das coroas (`kr` ou código) e o texto exato das notas e avisos (linguagem simples: diz o que aconteceu e o que fazer).
- Confirmar no `EXPLAIN QUERY PLAN`, já com a consulta real de `listar`, que o SQLite usa os índices de expressão ("publicada há" e os dois de salário). Se algum não for usado, ajustar a consulta para repetir a expressão do índice letra por letra antes de mexer no índice, e conferir de novo.
- Repartir em tarefas `Tn` no plano (sugestão: A e E juntas; B; C e D juntas; F; G em duas, configuração e exibição; H primeiro, porque a 0005 é base das outras).

## 7. Perguntas pendentes do dono

1. Vaga sem salário fica fora quando o filtro de salário está ligado?
   Recomendação: sim, fica fora, com o aviso "N vagas sem salário ficaram de fora" e um jeito de incluí-las (`sem_salario=1`). O desenho acima já segue isso.
2. Pedir "Meu país" no passo 1 da primeira execução, já marcado pelo `Accept-Language` e, sem ele, BR?
   Recomendação: sim.
3. Os filtros novos ficam escondidos em "Mais filtros"? Duas opções, com o mesmo custo de construir:
   - (a) tudo dentro de "Mais filtros": campos e chips de país e "publicada há". Tela inicial mais limpa, mas a pessoa só vê as contagens por país e por data depois de abrir;
   - (b) os campos (salário, cidade, empresa, "não pode ter") dentro de "Mais filtros", e os chips de país e "publicada há" à vista, junto dos outros chips.
   Recomendação: (b). Os chips mostram quantas vagas há e cortam num clique, como os de UF e modalidade; os campos de digitar são os que pesam na tela. É um desvio do que a sessão tinha decidido (tudo escondido), por isso a decisão é do dono. O desenho acima segue (b).
4. País fora das 11 moedas cai em USD?
   Recomendação: sim.

Enquanto o dono não responde, o construtor segue as recomendações e registra cada uma no `duvidas.md` como "para confirmar".

## 8. Testes esperados, por parte

Todos com o relógio injetado (`tests/apoio/semear.py:14`, `AGORA = 2026-11-13 12:00 UTC`) e sem rede. `inserir_vaga` hoje cria `local_vaga` só com `uf` e país BR (`tests/apoio/semear.py:79`): ganha parâmetros opcionais de cidade e país.

A. Palavras (`tests/integracao/test_leitura.py`, com `_lista`/`_pagina`, `:74-78`)
- "não pode ter" exclui a vaga com a palavra no título, na empresa e na descrição; mantém a que não tem; com FTS e sem FTS.
- Duas palavras excluem quem tiver qualquer uma (OR), com controle positivo.
- Termo com aspa, `%`, `_`, NUL e surrogate não quebra nem casa errado; só pontuação não filtra nada.
- `q` e `excluir` juntos.

B. Salário (`test_leitura.py`, `tests/integracao/test_rota_vagas.py` classe `Painel`, `tests/integracao/test_cotacoes.py`)
- Sobreposição: vaga 5–8 mil casa com filtro 7–10 mil e com 1–5 mil; não casa com 9–10 mil; vaga sem máximo usa o mínimo; vaga só com máximo ("até 8 mil") usa o máximo nas duas pontas.
- Salário implausível fica fora e conta como "sem salário".
- Conversão Y para BRL com cotação semeada: valor de borda dentro (arredondamento a favor da vaga).
- Sem cotação de Y: nada é cortado e o aviso aparece.
- Conversão desligada e Y ≠ BRL: só vagas em Y, com aviso; vaga em Y de 5–8 mil por mês casa com 7–10 mil (máximo mensal pelo `CASE` de `sal_periodo`), também com período `hora` e `ano`.
- `sem_salario=1` no modo desligado com Y ≠ BRL traz a vaga sem salário e não traz a vaga em Y fora da faixa nem a vaga em outra moeda.
- Sem salário fora, e `sem_salario=1` traz de volta.
- Contagem dos dois avisos: com a conversão desligada e Y = BRL, a vaga em USD conta em "sem valor convertido", não em "sem salário"; idem com a conversão ligada e sem cotação de X; a vaga sem `sal_moeda` conta só em "sem salário".
- URL torta (`sal_de=abc`, `-5`, `0`, número enorme, `sal_de > sal_ate`): 200, nunca 422.

C. Publicada (`test_leitura.py`, `test_rota_vagas.py`)
- Vaga de 23 h e de 25 h atrás contra `24h` (borda); vaga sem `publicada_em` usa `primeira_vista_em`.
- Contagem dos três chips com outro filtro ligado; valor fora do conjunto é ignorado.

D. País (`test_leitura.py`, `test_rota_vagas.py`)
- Chip filtra por `local_vaga.pais`; contagem considera os outros filtros; rótulo em pt e em en; código inválido é ignorado.

E. Cidade e empresa (`test_leitura.py`)
- "contém" sem acento e sem caixa ("sao" acha "São Paulo"); `%` e `_` no texto não viram curinga.
- Vaga cujo local não tem cidade (só UF, como a semeadura grava) com o filtro de cidade ligado: a consulta não levanta erro e a vaga fica fora; na rota (`test_rota_vagas.py`), resposta 200.

F. Tela (`test_rota_vagas.py`, `tests/tela/test_vagas.py`)
- Cada parâmetro novo vai e volta na URL; clicar num chip mantém salário, cidade, empresa e "não pode ter".
- `<details>` fechado sem filtro e aberto com filtro; contador no `summary`.
- Teste de tela: preencher "Mais filtros", mandar, conferir a lista e a URL; claro e escuro.

G. Moeda e Meu país (`tests/unidade/test_formatos.py`, `tests/integracao/test_rota_configuracoes.py`, `tests/integracao/test_buscas.py`, `tests/integracao/test_cotacoes.py`, teste da execução)
- `moeda_do_pais` para cada país do mapa, um da zona do euro e um fora (USD); todo código do mapa existe em `_PAISES`.
- Moeda efetiva: `moeda_exibicao` vazia segue o país; valor inválido cai no padrão.
- `salario_texto` em Y: vaga em X ≠ Y, vaga em BRL com Y ≠ BRL, vaga em Y (sem linha), conversão desligada (sem linha), sem cotação de Y (reais com nota); taxa cruzada e data mais antiga.
- Conta com número conhecido: 5.000 reais com venda_EUR = 6,25 dá "≈ € 800"; com venda_JPY = 0,0368 dá "≈ ¥ 135.870" (arredondado para unidade inteira, meio para cima), sem centavos, sem valor 100 vezes menor e sem `MemoryError` (o caso do JPY é uma divisão que não termina). Um caso de borda no meio exato (x,5 unidades) sobe.
- Taxa cruzada com divisão que não termina (ex.: venda_JPY / venda_USD) sai formatada, sem erro.
- Encaixe com Meu país (`tests/unidade/test_encaixe.py`): busca sem cidade e `pais_padrao="PT"`: a vaga remota restrita a PT não é oculta pela regra `pais` e a restrita a BR é; com `pais_padrao="BR"`, o contrário (o comportamento de hoje); busca com cidade em PT ignora o `pais_padrao`.
- Recálculo ao trocar o Meu país (`test_rota_configuracoes.py`): com uma busca sem cidade e uma vaga remota restrita a PT oculta por `pais`, salvar Meu país = PT deixa o `encaixe.oculta_motivo` dela nulo; salvar só a moeda de exibição não recalcula.
- Exibição pedida pelo dono, em teste de rota: no cartão (`templates/vagas/corpo.html:43-46`) e no detalhe (`templates/detalhe/pagina.html:44-47`), o valor convertido fica num elemento próprio depois do `strong` do salário, com a classe nova (linha de baixo, letra menor, `--texto-2`). Teste de tela (`tests/tela/test_vagas.py`) do bloco de salário no claro e no escuro.
- Texto da cotação sem `R$` fixo, em pt e en.
- Configurações grava e lê `meu_pais` e `moeda_exibicao`; valor de fora é recusado sem 500.
- `paises_das_buscas` com Meu país = PT e busca sem cidade dá `("PT",)`; com cidade continua o país da cidade (`test_buscas.py:143`).
- `_cotacoes` pede Y quando Y não está em `moedas_em_aberto` (`httpx.MockTransport`) e não pede nada com a conversão desligada.
- Primeira execução: `Accept-Language: en-GB` marca GB; sem região marca BR.
- Contraste: se o construtor criar cor nova, ela entra em `test_contraste_minimo` (`tests/unidade/test_contraste.py:31`); com `--texto-2`, nada muda.

H. Desempenho (`tests/integracao/test_migracoes.py` e um teste novo de plano)
- A 0005 cria os índices e não mexe em gatilho, FTS nem dados (teste lê só o arquivo da 0005); `ULTIMA` acompanha.
- `EXPLAIN QUERY PLAN` usa os índices esperados em cada filtro novo; o de salário em três casos: só "de", só "até" e os dois juntos; país com `local_vaga_pais`, UF e cidade com `local_vaga_vaga`.
- A 0005 roda num banco já semeado com os formatos reais (vagas gravadas por `gravar_escopo`, `banco/gravacao.py:290`, com `publicada_em` presente e ausente) e, depois dela, gravar e atualizar uma vaga continua funcionando (o índice com `julianday()` recusa texto como `'now'`).
- i18n: toda chave nova em pt e en, mesmo conjunto; chave com parâmetro testada com o nome certo.
