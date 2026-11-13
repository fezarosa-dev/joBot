# 0015. Treino de modelos (fase 6)

- **Status:** aceita
- **Data:** 2026-11-13

## Contexto

Com o tempo, as vagas que a pessoa salva e descarta mostram o que ela quer de verdade. Isso pode ser usado para ensinar um modelo a sugerir melhor. O projeto ainda não tem código; isto é o plano para a fase 6.

## Decisão

- Um classificador "salvar ou descartar" é treinado com o que a pessoa faz no painel. Duas técnicas possíveis: TF-IDF com regressão logística (conta palavras e aprende um peso para cada uma), ou embeddings do próprio llama.cpp (números que representam o sentido do texto).
- Laya: experimento opcional.
- Ajuste fino LoRA (um treino leve de um modelo já pronto), feito no RunPod (serviço de computadores alugados), só se uma avaliação mostrar necessidade.

## Consequências

- Treino pesado só acontece se os números pedirem.

## Ver também

- [0009. Inteligência artificial: opções, modelos e pacote offline](0009-ia-backends-e-modelos.md)
- [0014. Segurança e privacidade](0014-seguranca-e-privacidade.md)
