# Treino do Laya

O Laya é o Qwen3.5 2B do joBot ajustado (LoRA) para a tarefa `encaixe`: tirar da vaga as
habilidades que ela pede, no mesmo esquema de `nucleo/ia` (`SaidaEncaixe`), e responder
"verdadeiro ou falso" sobre um item da vaga. O resultado é um GGUF Q4_K_M que o `llama-server` do
joBot lê, com sha256 no formato de `src/jobot/nucleo/dados/ia_local.json`.

Estes scripts ficam fora do pacote `jobot` e não entram no instalador. O dono autorizou o treino no
RunPod em 2026-11-24 (D219, ADR 0015).

## Regras

- **Só Community Cloud, nunca Secure.** Todo pod do treino, da medida e do professor é Community.
- **Menor custo total.** A GPU é a de menor preço por hora × horas previstas, mesmo que seja a mais
  lenta, com teto de 20 dias (`custo.py`).
- **Gabarito do dono nunca entra.** Os scripts recusam caminho com `joBot-dados` ou `dados_locais`.
  Se o gabarito estiver no banco do dono, ele gera fora do repositório um arquivo com o `url_hash`
  dessas vagas (um por linha) e passa em `--excluir`. Sem esse arquivo, `montar` só roda com
  `--sem-gabarito`, e a decisão fica anotada na D219.
- **Conjunto de ouro fora do treino.** `tests/fixtures/ia/ouro_habilidades.json` é só para avaliar:
  `montar_conjunto.py` tira essas vagas, e `rotular.py` e `treinar.py` param se uma aparecer.
- **Só fontes públicas, com os termos conferidos.** A lista de fontes permitidas é vazia por padrão
  (`--fonte <chave>` para cada uma) e só aceita coletores públicos do joBot; vaga vista em site com
  login nunca entra. Cada fonte liberada fica anotada na D219 antes da coleta (passo 0).
- **Sem dado pessoal.** E-mail, telefone, CPF, contato (perfil, mensageiro, "fale com") e o
  recrutador saem do texto até o fim da frase; vaga com resto de dado pessoal sai inteira. Nome
  solto em texto corrido não é garantido: confira uma amostra sorteada antes de rotular (passo 2).
- **Dados fora do clone.** A coleta e os exemplos guardam vagas cruas: os scripts recusam saída
  dentro do repositório. Os exemplos abaixo usam `DADOS=/workspace/laya-dados`.
- **Coleta educada.** A coleta é a do próprio joBot: user agent do joBot, intervalo por host,
  429 e `Retry-After` (ADR 0004).
- **Vaga é dado, nunca instrução.** O pedido ao professor e ao Laya é o de produção, com o texto da
  vaga entre marcas.

## Fluxo

Tudo roda num clone do repositório, com o `uv` do projeto (`uv sync --locked`). A coleta e a
montagem podem rodar em qualquer máquina; o professor, o treino e a medida rodam no pod.

```
export DADOS=/workspace/laya-dados   # fora do clone
```

### 0. Liberar as fontes

Para cada fonte que vai entrar, leia os termos dela e anote na D219 a chave, a data e o trecho que
permite usar as vagas em treino de modelo público (ADR 0015). Fonte sem anotação não entra.

### 1. Coletar

```
uv run python scripts/treino_laya/montar_conjunto.py coletar --dados $DADOS/coleta \
    --fonte <chave> --fonte <chave>
```

Uma busca do joBot num banco separado (`$DADOS/coleta/jobot.db`), só com essas fontes ligadas.
Para ter mais vagas, rode de novo outro dia (as fontes têm intervalo mínimo).

### 2. Montar o conjunto

```
uv run python scripts/treino_laya/montar_conjunto.py montar --banco $DADOS/coleta/jobot.db \
    --saida $DADOS/conjunto --fonte <chave> --fonte <chave> --excluir <hashes do dono>
```

Sem a lista do dono, troque `--excluir` por `--sem-gabarito` e anote a decisão na D219. O script
diz quantos hashes leu e quantos casaram, e avisa quando nenhum casou (arquivo em formato errado).
Escreve `$DADOS/conjunto/treino.jsonl` e `$DADOS/conjunto/validacao.jsonl` (10% dos grupos). A
mesma vaga em duas fontes (mesma empresa e mesmo título) fica num lado só.

Antes de rotular, leia umas 50 vagas sorteadas e procure nome de pessoa e contato que passaram:

```
shuf -n 50 $DADOS/conjunto/treino.jsonl | less
```

### 3. Rotular com o professor

No pod do professor (Community, GPU de 24 GB ou mais, escolhida pelo `custo.py` com a vazão do
professor), sirva um modelo aberto maior, como o Qwen3.5 de 27 a 32B ou o maior que couber, sem
raciocínio, com a API compatível com a da OpenAI:

```
vllm serve <repositório do modelo> --max-model-len 8192 --port 8000
# ou: llama-server -m <modelo>.gguf -c 8192 -ngl 99 --reasoning off --port 8000
uv run python scripts/treino_laya/rotular.py --conjunto $DADOS/conjunto \
    --saida $DADOS/rotulado --endereco http://127.0.0.1:8000/v1 --modelo <nome servido>
```

Anote na D219 o repositório e o commit do professor. A resposta que não valida no esquema ou que
fica vazia depois da anti-invenção não entra. O prazo por vaga é de 300 s (`--prazo`). A vaga em
que o servidor falha 3 vezes fica marcada como pulada e a rodada segue; 5 puladas seguidas param a
rodada (o servidor caiu), e as 20 primeiras vagas todas vazias também (servidor ou modelo mal
configurado). Uma linha de andamento sai a cada 50 vagas. Se o pod cair, rode de novo: o que já
foi rotulado não é pedido outra vez.

### 4. Ensaio

No pod da primeira GPU a medir, antes de tudo, dois passos num recorte pequeno e a exportação
deles (passo 7), para pegar qualquer incompatibilidade entre as versões fixadas:

```
uv run --with-requirements scripts/treino_laya/requirements.txt \
    python scripts/treino_laya/treinar.py treinar --dados $DADOS/rotulado \
    --saida /workspace/ensaio --max-passos 2 --recorte 64
```

Depois rode o passo 7 com `--saida /workspace/ensaio` e apague `/workspace/ensaio`. Versão trocada
entra no `requirements.txt` e na D219.

### 5. Escolher a GPU do treino

Em pods curtos (uns 10 minutos cada), meça as GPUs Community mais baratas por hora que tenham 16 GB
ou mais. A medida usa os exemplos mais longos, com o lote e o tamanho do treino:

```
uv run --with-requirements scripts/treino_laya/requirements.txt \
    python scripts/treino_laya/custo.py --medir --dados $DADOS/rotulado \
    --escrever $DADOS/vazao/<gpu>.json --gpu <id do catálogo>
```

Depois, em qualquer máquina:

```
uv run python scripts/treino_laya/custo.py --vazao $DADOS/vazao/*.json \
    --exemplos $(wc -l < $DADOS/rotulado/treino.jsonl) --epocas 2
```

O `custo.py` lê o catálogo de preços do RunPod (só leitura, sem chave) e imprime a tabela e a
escolha. Vazão de GPU que não está no catálogo, ou menor ou igual a zero, para com erro.

### 6. Treinar

No pod da GPU escolhida:

```
uv run --with-requirements scripts/treino_laya/requirements.txt \
    python scripts/treino_laya/treinar.py treinar --dados $DADOS/rotulado --saida /workspace/laya
```

Um checkpoint a cada 100 passos (`--salvar-a-cada`), os três últimos guardados. A avaliação é uma
por época, em 400 exemplos fixos da validação (`--avaliar`).

### 7. Exportar

O conversor do `llama.cpp` fixa outro `transformers` e outro `torch`: ele roda num ambiente próprio
(`--python-conversor`), e o merge do LoRA fica no ambiente do treino.

```
git clone --depth 1 --branch b12359 https://github.com/ggml-org/llama.cpp /workspace/llama.cpp
cmake -S /workspace/llama.cpp -B /workspace/llama.cpp/build
cmake --build /workspace/llama.cpp/build --target llama-quantize -j
uv run --with-requirements scripts/treino_laya/requirements.txt \
    python scripts/treino_laya/treinar.py exportar --saida /workspace/laya \
    --llama-cpp /workspace/llama.cpp \
    --python-conversor "uv run --no-project --with-requirements /workspace/llama.cpp/requirements/requirements-convert_hf_to_gguf.txt python" \
    --url <endereço onde o GGUF será publicado, com versão fixa>
```

A versão do `llama.cpp` é a do manifesto (`b12359`). Sai
`/workspace/laya/Laya-2B-Q4_K_M.gguf` e `/workspace/laya/manifesto_laya.json`, com o sha256 e o
tamanho do Q4_K_M no formato de `ia_local.json`.

### 8. Avaliar

Sirva o GGUF com o `llama-server` no pod e rode a mesma prova do CI. Rode antes o 2B original
(`Qwen3.5-2B-Q4_K_M.gguf` do manifesto) no mesmo pod e com o mesmo comando: os 83% a 84% da T410
vieram de outro backend (`local`, no CI) e não servem de comparação direta.

```
llama-server -m <GGUF> -c 8192 --reasoning off --port 8080 &
uv run python scripts/provar_ia.py --backend compativel --endereco http://127.0.0.1:8080/v1 \
    --modelo laya
```

O Laya só substitui o Qwen3.5 2B original se acertar mais que ele no conjunto de ouro (ADR 0015).

## Retomar depois de uma queda

O pod Community pode cair ou sumir. Com o mesmo pod (parado e religado), basta rodar o mesmo
comando: `rotular.py` pula o que já fez (e refaz a última linha cortada), e `treinar.py` retoma do
último checkpoint inteiro em `--saida` (o cortado pela queda fica de fora). Se a máquina do pod
sumir, o disco `/workspace` vai junto: guarde de tempos em tempos o último `checkpoint-<n>` e o
`$DADOS/rotulado/` fora do pod (por exemplo, `runpodctl send`), suba um pod novo, copie de volta
para os mesmos caminhos e rode o mesmo comando.

## No fim: desligar e apagar o pod

Pod parado ainda cobra o disco. Quando o GGUF e o manifesto estiverem copiados para fora:

1. Copie para fora o `manifesto_laya.json`, o GGUF e, se quiser, o `lora/`.
2. Pare o pod (`runpodctl pod stop <id>` ou o botão Stop do console).
3. Apague o pod (`runpodctl pod delete <id>` ou Terminate no console): o disco some junto.
4. Confira em Billing que nada mais está cobrando.
