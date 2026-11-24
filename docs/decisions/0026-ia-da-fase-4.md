# 0026. IA da fase 4: tarefas, backends e modelo local

- **Status:** proposta (tudo aqui vem da D185 do `duvidas.md`, escolhas da sessão de 2026-11-17 que o dono ainda não confirmou; cada frase da decisão leva a marca "para confirmar")
- **Data:** 2026-11-17
- **Atualizada:** 2026-11-24 (o dono autoriza o treino do Laya; a 0.5.0 sai sem o Laya treinado, para confirmar, D219 e [0015](0015-treino.md)); 2026-11-24 (o Laya é o modelo local padrão da 0.6.0, D219 e D237)

## Contexto

A fase 4 traz a IA ([0017](0017-fases.md)). As decisões do dono deixaram pontos abertos ou em conflito: o pacote offline perguntado pelo instalador, com áudio ([0009](0009-ia-backends-e-modelos.md)), contra o instalador sem rede (D174.1) e o áudio na fase 6 (D139.11); o ajuste do Laya antes da fase 4 (D141), cujo treino custa; os termos da Anthropic e da OpenAI para as sessões do Claude Code e do Codex (D1, D125, D139.2); o perfil, que ainda não existe; e onde a IA entra no encaixe, que hoje é só código. O desenho da fase 4 (`docs/superpowers/specs/2026-11-17-fase-4-design.md`) fechou esses pontos na D185, para o dono confirmar.

## Decisão

- **Duas versões** (para confirmar, D185.1). A 0.5.0 traz o contrato de IA, os serviços por chave, o modelo local, o perfil mínimo (as habilidades), o encaixe por habilidade, a aba IA, Ferramentas › Modelo local e o item do instalador. A 0.6.0 traz o currículo, o questionário, as perguntas de lacuna, a IA manual, "Preparar candidatura" e os passos da primeira execução.
- **Tarefas desligadas por padrão** (para confirmar, D185.2): cada tarefa de IA tem liga, backend e modelo próprios, e nada sai da máquina sem a pessoa ligar.
- **Backends** (para confirmar, D185.4 e D185.23): um cliente compatível com OpenAI atende a OpenAI, o Gemini, o modelo local, o Ollama, o LM Studio e serviços como o OpenRouter; soma-se o cliente da API da Anthropic, só com Haiku 5.5 e Sonnet 5.5. Sem SDK de provedor: basta o `httpx`. A resposta é conferida por esquemas pydantic (D185.3).
- **Sessões do Claude Code e do Codex esperam o dono** (para confirmar, D185.5 e D185.6): o texto legal atual do Claude Code e a documentação do Codex pedem chave de API para produto e automação. Até a resposta do dono, nada dessas sessões é construído.
- **Modelo local da fonte oficial** (para confirmar, D185.7, D185.18 e D185.19): o `llama-server` do build b12359 e o Qwen3.5-2B ou 4B da Unsloth, com sha256 fixo, baixados pelo joBot a pedido da pessoa para a pasta de dados, sem ir no instalador nem na release. O tamanho do modelo vem da memória do computador, e roda só em CPU.
- **A IA só extrai; o encaixe é do código** (para confirmar, D185.11 e D185.12): a tarefa `encaixe` lista o que a vaga pede, sem ver o perfil; o código compara com as habilidades da pessoa. A IA não dá nota nem esconde vaga. Um laço à parte, fora da busca, cuida das vagas mais novas.
- **Laya e e5-small** (para confirmar, D185.8, D185.9 e D219): ~~o treino do Laya é a primeira pergunta ao dono (autoriza o gasto ou adia), e o multilingual-e5-small volta junto do Laya. Até a resposta, as habilidades vêm da IA escolhida.~~ O dono autorizou o treino do Laya em 2026-11-24 (D219): o Laya passa a ser o Qwen3.5 2B ajustado por LoRA, treinado no RunPod pelos scripts de `scripts/treino_laya/` ([0015](0015-treino.md)). A 0.5.0 sai sem o Laya treinado, porque o treino espera uma GPU barata da Community Cloud, e as habilidades vêm da IA escolhida; ~~o Laya entra numa versão seguinte, se acertar mais que o 2B original no conjunto de ouro.~~ Treinado, o Laya acertou mais que o 2B original no conjunto de ouro e é o modelo local padrão da 0.6.0 (D219, confirmada na D237). O multilingual-e5-small continua adiado.
- **Sem áudio no pacote offline** (para confirmar, D185.10): o áudio fica na fase 6 (D139.11).
- **Perfil mínimo** (para confirmar, D185.13): na 0.5.0, só as habilidades, com "Apagar perfil"; na 0.6.0, experiências, cursos e perguntas. CPF, data de nascimento e projetos ficam de fora.
- **Segurança e custo** (para confirmar, D185.22 e D185.28): lista permitida de campos por tarefa, sem nome, e-mail, telefone ou cidade; serviço pago aparece como "cobrado por uso", com teto diário de chamadas do laço. Os serviços pagos ficam marcados "experimental" até o dono os provar com a chave dele (D185.27).

## Consequências

- O joBot continua funcionando sem IA nenhuma, como na fase 1.
- O pydantic passa a dependência direta; ele já está no `uv.lock` pelo FastAPI.
- A pasta de dados pode guardar até 2,7 GB de modelo, que Ferramentas › Remover apaga.
- Qualquer item que o dono trocar muda esta ADR e as notas das ADRs vizinhas.

## Ver também

- [0002. Duas versões, um núcleo](0002-duas-versoes-um-nucleo.md)
- [0007. Tratamento das vagas: duplicadas, ciclo de vida, salário e rótulos](0007-tratamento-dos-dados.md)
- [0009. Inteligência artificial: opções, modelos e pacote offline](0009-ia-backends-e-modelos.md)
- [0010. Usar o Claude Code que a pessoa já tem (sem login dentro do joBot)](0010-claude-code-da-pessoa.md)
- [0011. Perfil, currículo, primeira execução e áudio](0011-perfil-e-primeira-execucao.md)
- [0014. Segurança e privacidade](0014-seguranca-e-privacidade.md)
- [0015. Treino de modelos (fase 7)](0015-treino.md)
- [0017. Fases do projeto](0017-fases.md)
- [0023. Tudo pelo painel](0023-tudo-pelo-painel.md)
- [duvidas.md: D185 (fase 4), D186 (documentos da T400) e D219 (treino do Laya)](../../duvidas.md)
