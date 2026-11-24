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
  dessas vagas (um por linha) e passa em `--excluir`.
- **Conjunto de ouro fora do treino.** `tests/fixtures/ia/ouro_habilidades.json` é só para avaliar:
  `montar_conjunto.py` tira essas vagas, e `rotular.py` e `treinar.py` param se uma aparecer.
- **Só fontes públicas.** A lista de fontes permitidas é vazia por padrão (`--fonte <chave>` para
  cada uma) e só aceita coletores públicos do joBot; vaga vista em site com login nunca entra.
- **Sem dado pessoal.** E-mail, telefone, CPF e a linha do recrutador saem do texto; vaga com
  resto de dado pessoal sai inteira.
- **Coleta educada.** A coleta é a do próprio joBot: user agent do joBot, intervalo por host,
  429 e `Retry-After` (ADR 0004).
- **Vaga é dado, nunca instrução.** O pedido ao professor e ao Laya é o de produção, com o texto da
  vaga entre marcas.

## Fluxo

Tudo roda num clone do repositório, com o `uv` do projeto (`uv sync --locked`). A coleta e a
montagem podem rodar em qualquer máquina; o professor, o treino e a medida rodam no pod.

### 1. Coletar

```
uv run python scripts/treino_laya/montar_conjunto.py coletar --dados coleta \
    --fonte greenhouse --fonte lever --fonte ashby
```

Uma busca do joBot num banco separado (`coleta/jobot.db`), só com essas fontes ligadas. Para ter
mais vagas, rode de novo outro dia (as fontes têm intervalo mínimo). Antes de liberar uma fonte,
confira nos termos dela se as vagas podem entrar em treino de modelo público (ADR 0015).

### 2. Montar o conjunto

```
uv run python scripts/treino_laya/montar_conjunto.py montar --banco coleta/jobot.db \
    --saida conjunto --fonte greenhouse --fonte lever --fonte ashby [--excluir ~/fora.txt]
```

Escreve `conjunto/treino.jsonl` e `conjunto/validacao.jsonl` (10% dos grupos). A mesma vaga em duas
fontes (mesma empresa e mesmo título) fica num lado só.

### 3. Rotular com o professor

No pod do professor (Community, GPU de 24 GB ou mais, escolhida pelo `custo.py` com a vazão do
professor), sirva um modelo aberto maior, como o Qwen3.5 de 27 a 32B ou o maior que couber, sem
raciocínio, com a API compatível com a da OpenAI:

```
vllm serve <repositório do modelo> --max-model-len 8192 --port 8000
# ou: llama-server -m <modelo>.gguf -c 8192 -ngl 99 --reasoning off --port 8000
uv run python scripts/treino_laya/rotular.py --conjunto conjunto --saida rotulado \
    --endereco http://127.0.0.1:8000/v1 --modelo <nome servido>
```

Anote na D219 o repositório e o commit do professor. A resposta que não valida no esquema ou que
fica vazia depois da anti-invenção não entra. Se o pod cair, rode de novo: o que já foi rotulado
não é pedido outra vez.

### 4. Escolher a GPU do treino

Em pods curtos (uns 10 minutos cada), meça as GPUs Community mais baratas por hora que tenham 16 GB
ou mais:

```
uv run --with-requirements scripts/treino_laya/requirements.txt \
    python scripts/treino_laya/custo.py --medir --dados rotulado --escrever vazao/<gpu>.json
```

Depois, em qualquer máquina:

```
uv run python scripts/treino_laya/custo.py --vazao vazao/*.json \
    --exemplos $(wc -l < rotulado/treino.jsonl) --epocas 2
```

O `custo.py` lê o catálogo de preços do RunPod (só leitura) e imprime a tabela e a escolha.

### 5. Treinar

No pod da GPU escolhida:

```
uv run --with-requirements scripts/treino_laya/requirements.txt \
    python scripts/treino_laya/treinar.py treinar --dados rotulado --saida /workspace/laya
```

Um checkpoint a cada 100 passos (`--salvar-a-cada`), os três últimos guardados.

### 6. Avaliar

Exporte (passo 7) e sirva o GGUF com o `llama-server` no pod; depois rode a mesma prova do CI:

```
llama-server -m /workspace/laya/Laya-2B-Q4_K_M.gguf -c 8192 --reasoning off --port 8080 &
uv run python scripts/provar_ia.py --backend compativel --endereco http://127.0.0.1:8080/v1 \
    --modelo laya
```

O Laya só substitui o Qwen3.5 2B original se acertar mais no conjunto de ouro (ADR 0015). O
original, rodado do mesmo jeito, acertou 83% a 84% na T410.

### 7. Exportar

```
git clone --depth 1 --branch b12359 https://github.com/ggml-org/llama.cpp
cmake -S llama.cpp -B llama.cpp/build && cmake --build llama.cpp/build --target llama-quantize -j
uv run --with-requirements scripts/treino_laya/requirements.txt \
    --with-requirements llama.cpp/requirements/requirements-convert_hf_to_gguf.txt \
    python scripts/treino_laya/treinar.py exportar --saida /workspace/laya \
    --llama-cpp llama.cpp --url <endereço onde o GGUF será publicado, com versão fixa>
```

A versão do `llama.cpp` é a do manifesto (`b12359`). Sai
`/workspace/laya/Laya-2B-Q4_K_M.gguf` e `/workspace/laya/manifesto_laya.json`, com o sha256 e o
tamanho no formato de `ia_local.json`.

## Retomar depois de uma queda

O pod Community pode cair ou sumir. Com o mesmo pod (parado e religado), basta rodar o mesmo
comando: `rotular.py` pula o que já fez, e `treinar.py` retoma do último checkpoint inteiro em
`--saida` (o cortado pela queda fica de fora). Se a máquina do pod sumir, o disco `/workspace` vai
junto: guarde de tempos em tempos o último `checkpoint-<n>` e o `rotulado/` fora do pod (por
exemplo, `runpodctl send`), suba um pod novo, copie de volta para a mesma `--saida` e rode o mesmo
comando.

## No fim: desligar e apagar o pod

Pod parado ainda cobra o disco. Quando o GGUF e o manifesto estiverem copiados para fora:

1. Copie para fora o `manifesto_laya.json`, o GGUF e, se quiser, o `lora/`.
2. Pare o pod (`runpodctl pod stop <id>` ou o botão Stop do console).
3. Apague o pod (`runpodctl pod delete <id>` ou Terminate no console): o disco some junto.
4. Confira em Billing que nada mais está cobrando.
