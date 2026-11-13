# 0011. Perfil, currículo, primeira execução e áudio

- **Status:** aceita
- **Data:** 2026-11-13

## Contexto

Sem um perfil bom, a IA não tem com o que trabalhar, e preencher formulário longo cansa. Para muita gente, falar é mais fácil do que digitar. O projeto ainda não tem código; o que segue é o plano.

## Decisão

### Perfil

- Dados pessoais, CPF, data de nascimento, experiências, formação, cursos, habilidades, projetos, idiomas, links, perguntas e respostas próprias e preferências de busca.

### Currículo

- A pessoa envia o PDF, que é lido com a biblioteca pypdf.
- A IA extrai os dados e a pessoa revisa antes de salvar.

### Primeira execução, em passos

- Passo 0: escolher a IA (o Claude Code é detectado sozinho).
- Passo 1: currículo.
- Passo 2: questionário.
- Passo 3: logins nos sites.
- Passo 4: Gmail (opcional).
- Passo 5: segundo plano e horários dos sites com login.

### Questionário

- Cerca de 25 perguntas base, mais perguntas geradas pela IA para cobrir lacunas do perfil.
- Resposta por texto, por alternativas ou por áudio: um microfone em cada pergunta e um botão "gravar geral".
- A pessoa aprova cada resposta ou usa "aprovar todas".

### Áudio

- Transcrição local, no próprio computador, com faster-whisper.
- Modelo padrão: "small" (484 MB). O "medium" (1,53 GB) é opcional.
- O áudio é apagado depois da transcrição.

## Consequências

- O perfil é a fonte única para encaixe, candidatura e extensão.
- Nada de áudio fica guardado.

## Ver também

- [0006. Agenda das buscas e segundo plano](0006-agenda-e-segundo-plano.md)
- [0009. Inteligência artificial: opções, modelos e pacote offline](0009-ia-backends-e-modelos.md)
- [0010. Usar o Claude Code que a pessoa já tem (sem login dentro do joBot)](0010-claude-code-da-pessoa.md)
- [0013. Gmail e avisos](0013-gmail-e-avisos.md)
- [0014. Segurança e privacidade](0014-seguranca-e-privacidade.md)
