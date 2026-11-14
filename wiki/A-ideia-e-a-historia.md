🌐 **Português** · [English](The-idea-and-the-story)

# 💡 A ideia e a história

**Por que o joBot existe, o que ele quer ser e o que ele nunca vai fazer.**

---

## 🌱 Como tudo começou

O joBot nasceu para ajudar jovens universitários a encontrar o primeiro emprego.
Depois a ideia se expandiu para todo mundo. Hoje o joBot é pensado para todo tipo de vaga e toda área: CLT, PJ, estágio, trainee, temporário, aprendiz, pesquisa e bolsa, programas e escolas de verão, concursos e editais.

### Linha do tempo

| Quando | O que aconteceu |
|---|---|
| 2026-11-13 | As decisões principais foram tomadas em 9 rodadas de perguntas e respostas e registradas em documentos curtos, as ADRs (ADR 0001 a 0017). |
| 2026-11-14 | O projeto passou a ser desenhado para ser mantido pela comunidade (ADR 0018), ganhou esta wiki (ADR 0019) e passou a aceitar só doação como apoio (ADR 0020). |
| Agora | A fase 1 de 8 (a base) está concluída: o joBot 0.1.0 já funciona. Veja o [roteiro](Roteiro). |

## 😩 O problema

Procurar vaga hoje cansa. É preciso abrir muitos sites, repetir os mesmos filtros e torcer para não perder um prazo.

## 💡 A ideia

Um painel pessoal que junta e organiza as vagas para você.

- 🖥️ **Roda no seu computador.** Uma instalação serve a uma pessoa, que pode ter várias buscas salvas.
- 🔒 **Privacidade primeiro.** Não existe servidor do joBot. Seus dados ficam com você.
- 🧠 **IA opcional.** Sem IA, o joBot funciona com regras e palavras-chave. Com IA, ela calcula o encaixe com o seu perfil e ajuda a preparar candidaturas, mas só usa o que está no seu perfil.
- 🎚️ **Tudo desligável.** Toda função e toda fonte tem uma chave liga/desliga.

## ✅ O que ele vai fazer

- 🔎 **Buscar** vagas em dezenas de fontes: sites públicos, quadros de vagas de empresas e, se você quiser, sites que exigem login.
- 🧹 **Limpar**: remover vagas repetidas, ler o salário e marcar área, nível, modalidade, região e tipo de contrato.
- 🎯 **Ranquear**: mostrar o quanto cada vaga combina com você (● bom, ◐ médio, ○ fraco) e explicar o porquê.
- 🗂️ **Organizar**: cada vaga tem um status, de "nova" até "oferta".
- ✍️ **Preparar candidatura**: carta de apresentação, resumo do currículo ajustado à vaga e lista do que você tem e do que falta, sempre no idioma da vaga.
- 🧩 **Ajudar nos formulários**: uma extensão do navegador sugere respostas, e você confirma.
- 📬 **Ler o Gmail** (opcional): trazer vagas dos e-mails de alerta e sugerir mudanças de status quando um recrutador responde.

## 🚫 O que ele não faz

> [!IMPORTANT]
> - **Não se candidata em massa.** Não existe "aplicar em 200 vagas com um clique".
> - **Não envia nada sozinho.** Quem envia a candidatura é sempre você.
> - **Não digita a sua senha.** Nos sites com login, você entra com as próprias mãos.
> - **Não contorna CAPTCHA.** Se aparecer um, ele para e avisa você.
> - **Não manda telemetria.** O joBot não envia dados de uso para ninguém.
> - **Não inventa experiência.** A IA só usa o que está no seu perfil.

## 🧭 Princípios

| | Princípio | O que quer dizer |
|:---:|---|---|
| 🖥️ | **Roda no seu computador** | O painel só funciona no próprio computador (endereço 127.0.0.1). Os dados ficam num banco local. |
| 🤝 | **Coleta educada** | O robô se identifica, espera entre um pedido e outro e espera mais quando o site pede calma. Nunca contorna login, CAPTCHA ou bloqueio anti-robô. |
| 📖 | **Código aberto (MIT)** | Qualquer pessoa pode ler, usar e melhorar o código, sob a licença MIT. |
| 🧼 | **Sala limpa** | Ideias e fatos públicos podem ser usados. Código e dados de teste de terceiros nunca são copiados. |
| 🌍 | **Mantido pela comunidade** | Os sites de vagas mudam sem aviso. Cada fonte tem o seu coletor (o código que lê as vagas de uma fonte), com exemplos e testes próprios, para qualquer pessoa conseguir consertar. |
| 🎁 | **Grátis** | O joBot é grátis. O projeto aceita só doação, sem anúncio, sem afiliado e sem rastreio. Veja [Apoie](Apoie). |

## 🔗 Para saber mais

- [Como funciona](Como-funciona): o caminho de uma vaga até o painel.
- [Decisões](Decisoes): cada decisão do projeto em uma linha.
- [README](https://github.com/fezarosa-dev/joBot#o-que-e): a descrição completa.
