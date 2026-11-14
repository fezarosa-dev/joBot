# 0015. Treino de modelos (fase 6)

- **Status:** aceita
- **Data:** 2026-11-13
- **Atualizada:** 2026-11-13

## Contexto

Com o tempo, as vagas que a pessoa salva e descarta mostram o que ela quer de verdade. Isso pode ser usado para ensinar um modelo a sugerir melhor. Modelos pequenos também podem ser ajustados para entender vagas melhor do que saem de fábrica. O projeto ainda não tem código; isto é o plano para a fase 6.

## Decisão

### O que é treinado

- Ajuste fino do Laya, um encoder multilíngue (mmBERT-base, 322M, licença Apache-2.0). Encoder é um modelo que lê o texto e devolve números ou rótulos, sem escrever texto. Sem ajuste, ele fica perto do acaso; por isso só é usado depois de ajustado.
- Ajuste fino LoRA (um treino leve de um modelo já pronto) do Qwen3.5-2B e do Qwen3.5-4B.
- Os dois treinos rodam no RunPod (serviço de computadores alugados).
- O Qwen ajustado é exportado em GGUF (o formato de arquivo que o llama-server lê), para rodar no llama-server.

### Quando o modelo ajustado entra

- O modelo ajustado só substitui o original se ganhar dele no gabarito (o conjunto de ouro da ADR 0007).
- O gabarito nunca entra no treino.

### Com que dados os modelos públicos treinam

Modelos públicos são os publicados no Hugging Face (site onde se publicam modelos). Eles treinam só com:

- vagas coletadas, sem e-mail, telefone e nome de recrutador;
- respostas certas geradas pelo Claude;
- currículos fictícios gerados pelo Claude;
- exemplos em que falta informação e o certo é perguntar.

Nunca entra dado pessoal: currículo real e ações da pessoa no painel ficam fora.

### Classificador pessoal

- Um classificador "salvar ou descartar" é treinado com o que a pessoa faz no painel. Duas técnicas possíveis: TF-IDF com regressão logística (conta palavras e aprende um peso para cada uma), ou embeddings do próprio llama.cpp (números que representam o sentido do texto).
- Ele treina e fica no computador de cada pessoa. Nada dele sai de lá.

### Base para usar respostas do Claude como dados de treino

- O artigo da central de ajuda da Anthropic "Can I use my Outputs to train an AI model?" (https://support.claude.com/en/articles/12326764) permite treinar modelos que não competem com os da Anthropic. Ele cita extração de informação e classificação.
- A política de uso de 12/11/2026 fala em autorização prévia.
- O dono decidiu seguir a central de ajuda, em 2026-11-13.

## Consequências

- Um modelo ajustado que não ganha do original no gabarito não é usado.
- Dado pessoal nunca sai do computador da pessoa por causa de treino.
- A fase 1 já guarda o que a fase 6 vai usar: o texto completo das vagas e o histórico das ações da pessoa no painel (ADR 0007).

## Pontos em aberto

- Antes da fase 6, conferir nos termos de cada fonte se as vagas dela podem entrar em treino de modelo público. Algumas fontes proíbem repassar as vagas (ADR 0004).

## Ver também

- [0004. Fontes públicas de vagas e coleta educada](0004-fontes-publicas.md)
- [0007. Tratamento das vagas: duplicadas, ciclo de vida, salário e rótulos](0007-tratamento-dos-dados.md)
- [0009. Inteligência artificial: opções, modelos e pacote offline](0009-ia-backends-e-modelos.md)
- [0014. Segurança e privacidade](0014-seguranca-e-privacidade.md)
