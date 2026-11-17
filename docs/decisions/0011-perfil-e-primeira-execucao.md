# 0011. Perfil, currículo, primeira execução e áudio

- **Status:** aceita
- **Data:** 2026-11-13
- **Atualizada:** 2026-11-13; 2026-11-17 (perfil mínimo na 0.5.0, passos IA e Perfil na 0.6.0, sem CPF, data de nascimento e projetos; tudo para confirmar, D185 e [0026](0026-ia-da-fase-4.md))

## Contexto

Sem um perfil bom, a IA não tem com o que trabalhar, e preencher formulário longo cansa. Para muita gente, falar é mais fácil do que digitar. O projeto ainda não tem código; o que segue é o plano.

## Decisão

### Perfil

- Dados pessoais, CPF, data de nascimento, experiências, formação, cursos, habilidades, projetos, idiomas, links, perguntas e respostas próprias e preferências de busca.

### Currículo

- A pessoa envia o PDF, que é lido com a biblioteca pypdf.
- A IA extrai os dados e a pessoa revisa antes de salvar.

### Primeira execução, em passos

- Na fase 1, o assistente tem só dois passos: preferências de busca (cargos ou palavras-chave, cidades, remoto/híbrido/presencial, nível, salário mínimo e idiomas) e segundo plano.
- Os passos abaixo entram nas fases deles: logins na fase 2; IA, currículo e questionário na fase 4; Gmail e áudio na fase 6.
- Passo 0: escolher a IA (o Claude Code é detectado sozinho).
- Passo 1: currículo.
- Passo 2: questionário.
- Passo 3: logins nos sites.
- Passo 4: Gmail (opcional).
- Passo 5: segundo plano e horários dos sites com login. Na fase 1, o segundo plano aparece como o passo 2 do assistente.

### Questionário

- Cerca de 25 perguntas base, mais perguntas geradas pela IA para cobrir lacunas do perfil.
- Resposta por texto, por alternativas ou por áudio: um microfone em cada pergunta e um botão "gravar geral".
- A pessoa aprova cada resposta ou usa "aprovar todas".

### Áudio

- Transcrição local, no próprio computador, com faster-whisper.
- Modelo padrão: "small" (484 MB). O "medium" (1,53 GB) é opcional.
- O áudio é apagado depois da transcrição.

## Fase 4 (2026-11-17, para confirmar)

- **Perfil em duas versões** (D185.13, para confirmar): na 0.5.0, o perfil guarda só as habilidades, com "Apagar perfil"; na 0.6.0, experiências, cursos e as perguntas do perfil. CPF, data de nascimento e projetos ficam de fora, por minimização e porque nenhuma tarefa os pede. O texto do currículo não é guardado.
- **Currículo** (D185.14, para confirmar): na 0.6.0, lido pelo pypdf num processo à parte, com prazo, tamanho e número de páginas limitados; o PDF não é guardado.
- **Primeira execução** (D185.15, para confirmar): na 0.6.0, dois passos opcionais antes dos de hoje, IA (os atalhos) e Perfil (currículo e as primeiras perguntas). O Claude Code só é detectado quando a sessão dele vier (ver [0010](0010-claude-code-da-pessoa.md)).
- **Áudio** fica na fase 6 (D139.11).

## Consequências

- O perfil é a fonte única para encaixe, candidatura e extensão.
- Nada de áudio fica guardado.

## Ver também

- [0006. Agenda das buscas e segundo plano](0006-agenda-e-segundo-plano.md)
- [0009. Inteligência artificial: opções, modelos e pacote offline](0009-ia-backends-e-modelos.md)
- [0010. Usar o Claude Code que a pessoa já tem (sem login dentro do joBot)](0010-claude-code-da-pessoa.md)
- [0013. Gmail e avisos](0013-gmail-e-avisos.md)
- [0014. Segurança e privacidade](0014-seguranca-e-privacidade.md)
- [0026. IA da fase 4: tarefas, backends e modelo local](0026-ia-da-fase-4.md)
- [duvidas.md: D185 (fase 4)](../../duvidas.md)
