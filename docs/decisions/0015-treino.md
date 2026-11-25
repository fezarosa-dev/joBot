# 0015. Treino de modelos (fase 7)

- **Status:** aceita
- **Data:** 2026-11-13
- **Atualizada:** 2026-11-15 (seção do modelo leve na máquina da pessoa, D122; seção do Laya antes da fase 4, D141); antes, em 2026-11-13; 2026-11-17 (o Laya antes da fase 4 fica adiado, para confirmar, e o Laya público é um modelo de decisão, D185.8 e [0026](0026-ia-da-fase-4.md)); 2026-11-24 (o dono autoriza o treino do Laya no RunPod, só na Community Cloud e pela GPU de menor custo total; o Laya passa a ser o Qwen3.5 2B ajustado por LoRA, e a 0.5.0 sai sem ele treinado, D219); 2026-11-24 (o Laya treinado vira o modelo local padrão da 0.6.0, D219 confirmada pelo dono na D237); 2026-11-24 (o dono aprova as quatro fontes do treino do Laya sem o trecho dos termos que permite, D219.14)

## Contexto

Com o tempo, as vagas que a pessoa salva e descarta mostram o que ela quer de verdade. Isso pode ser usado para ensinar um modelo a sugerir melhor. Modelos pequenos também podem ser ajustados para entender vagas melhor do que saem de fábrica. O projeto ainda não tem código; isto é o plano para a fase 7.

## Decisão

### O que é treinado

- ~~Ajuste fino do Laya, um encoder multilíngue (mmBERT-base, 322M, licença Apache-2.0). Encoder é um modelo que lê o texto e devolve números ou rótulos, sem escrever texto. Sem ajuste, ele fica perto do acaso; por isso só é usado depois de ajustado.~~ Em 2026-11-24 o Laya passou a ser o LoRA do Qwen3.5 2B (seção "Laya autorizado", D219).
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

## Modelo leve na máquina da pessoa (2026-11-15)

- O problema: a mesma habilidade vem escrita de um jeito na vaga e de outro no currículo. A comparação pelo sentido resolve isso, com o Laya ajustado.
- Primeiro se quantiza o modelo (int8, cerca de 4 vezes menor). Só se ainda ficar lento num PC comum (8 a 16 GB, sem placa de vídeo) ele é destilado para um modelo menor. Poda manual fica de fora.
- O modelo roda só na máquina da pessoa. O GitHub Actions nunca recebe currículo nem as vagas da pessoa: só confere que o modelo carrega e acerta um teste pequeno, com exemplos públicos. Vale a regra da [0014](0014-seguranca-e-privacidade.md): os dados só saem do computador para os serviços que a pessoa ligar, e o modelo leve não precisa de nenhum.
- O treino continua no RunPod. Esta seção não muda o status da ADR, que segue aceita (D122).

## Laya antes da fase 4 (2026-11-15)

- Exceção ao título e ao resto desta ADR: o ajuste fino do Laya sai da fase 7 e ~~acontece antes da fase 4 (D141)~~ ~~fica adiado, para confirmar (2026-11-17, D185.8): o dono decide primeiro se autoriza o gasto do treino antes da fase 4 ou adia~~ o dono autorizou o treino em 2026-11-24 (D219); ele roda na fase 4, pelos scripts de `scripts/treino_laya/`. Os outros treinos (~~LoRA do Qwen~~ LoRA do Qwen3.5 4B, classificador pessoal) continuam na fase 7; o LoRA do 2B é o próprio Laya (2026-11-24, D219).
- O Laya ajustado entra no encaixe junto com o Qwen local e reconhece palavras diferentes que querem dizer a mesma competência. Isso fecha o descompasso: o encaixe pelo sentido (D122) dependia do Laya ajustado, que só ficaria pronto na fase 7.
- O resto vale como está: o modelo ajustado só substitui o original se ganhar no gabarito, o gabarito nunca entra no treino, e o treino roda no RunPod.
- O ponto em aberto abaixo (termos das fontes) passa a valer antes deste treino do Laya, não antes da fase 7.

## ~~Laya adiado na fase 4 (2026-11-17, para confirmar)~~

- ~~Até o dono responder (D185.8, para confirmar), a fase 4 segue sem o Laya: as habilidades da vaga vêm da IA escolhida pela pessoa, e o código compara com o perfil ([0026](0026-ia-da-fase-4.md)). A fase 4 só prepara o conjunto de exemplos e o preço; nenhum treino roda e nenhum recurso do RunPod é criado sem o dono autorizar (para confirmar).~~ Caiu em 2026-11-24 (D219).
- Nota (para confirmar): o Laya público (`convaiinnovations/laya-multilingual`, Apache-2.0, sobre o mmBERT-base) é um modelo de decisão (escolha, nota e "verdadeiro ou falso"), não um modelo que compara competências pelo sentido. O ajuste fino teria de ensinar essa comparação.

## Laya autorizado (2026-11-24)

- O dono autorizou o treino no RunPod em 2026-11-24, com duas regras: só Community Cloud, nunca Secure; e a GPU de menor custo total (preço por hora × horas do treino), mesmo que leve até uns 20 dias (D219).
- O que é treinado: um ajuste LoRA do Qwen3.5 2B do modelo local (o mesmo do `ia_local.json`), para a tarefa `encaixe` (as habilidades da vaga, no esquema de `nucleo/ia`) e para perguntas "verdadeiro ou falso" sobre a vaga. O nome Laya passa a ser esse modelo; o encoder mmBERT da seção "O que é treinado" fica de fora (escolha da sessão, para discutir com o dono, D219).
- As respostas certas vêm de um modelo professor aberto e maior (um Qwen3.5 de 27 a 32B) rodando no próprio pod, não do Claude. Continuam valendo: só vagas de fontes públicas, sem e-mail, telefone e nome; o gabarito nunca entra (o conjunto de ouro público da T410 mede, e uma lista de hashes que o dono gera fora do repositório tira as vagas do gabarito dele).
- O Laya só substitui o Qwen3.5 2B original se acertar mais no conjunto de ouro. A saída é um GGUF Q4_K_M com sha256, no formato do `ia_local.json`.
- A 0.5.0 sai sem o Laya treinado: o treino espera uma GPU barata da Community Cloud. ~~O Laya entra numa versão seguinte, pelo manifesto `ia_local.json`.~~ Treinado e medido, o Laya acertou mais que o 2B original no conjunto de ouro e é o modelo local padrão da 0.6.0, pelo manifesto `ia_local.json` (D219, confirmada pelo dono em 2026-11-24, D237).

## Consequências

- Um modelo ajustado que não ganha do original no gabarito não é usado.
- Dado pessoal nunca sai do computador da pessoa por causa de treino.
- A fase 1 já guarda o que a fase 7 vai usar: o texto completo das vagas e o histórico das ações da pessoa no painel (ADR 0007).

## Pontos em aberto

- Antes da fase 7, conferir nos termos de cada fonte se as vagas dela podem entrar em treino de modelo público. Algumas fontes proíbem repassar as vagas (ADR 0004).
- Para o Laya da 0.6.0, nenhuma das quatro fontes usadas (Greenhouse, Lever, We Work Remotely e Jobicy) tem nos termos o trecho que permite: os termos delas não proíbem reaproveitar as vagas, mas também não autorizam expressamente treinar um modelo público. O dono decidiu em 2026-11-24 aprovar as quatro com essa leitura, mantendo o Laya como padrão e as fontes declaradas; se alguma fonte reclamar, ela sai e o Laya é retreinado sem ela (D219.14). É uma decisão do dono, não uma leitura de que os termos permitem.

## Ver também

- [0004. Fontes públicas de vagas e coleta educada](0004-fontes-publicas.md)
- [0007. Tratamento das vagas: duplicadas, ciclo de vida, salário e rótulos](0007-tratamento-dos-dados.md)
- [0009. Inteligência artificial: opções, modelos e pacote offline](0009-ia-backends-e-modelos.md)
- [0014. Segurança e privacidade](0014-seguranca-e-privacidade.md)
- [0026. IA da fase 4: tarefas, backends e modelo local](0026-ia-da-fase-4.md)
- [duvidas.md: D141 (Laya antes da fase 4), D185 (fase 4) e D219 (treino do Laya)](../../duvidas.md)
