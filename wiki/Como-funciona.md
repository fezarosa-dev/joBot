🌐 **Português** · [English](How-it-works)

# ⚙️ Como funciona

**O caminho de uma vaga, do site onde ela foi publicada até o seu painel.**

---

## 🛤️ O caminho da vaga

```mermaid
flowchart LR
    subgraph Fontes["🌎 Fontes de vagas"]
        P["Fontes públicas<br/>(APIs, quadros de vagas, GitHub)"]
        L["🔐 Sites com login<br/>(opcional)"]
        G["📬 Gmail<br/>(opcional)"]
    end

    C["🤖 Coletores<br/>(um por fonte)"]

    subgraph Tratamento["🧹 Tratamento"]
        T1["Remove duplicadas"]
        T2["Lê o salário"]
        T3["Coloca rótulos"]
        T4["Controla o ciclo de vida"]
    end

    DB[("🗄️ Banco local<br/>SQLite, no seu computador")]
    UI["📋 Painel no navegador<br/>127.0.0.1"]
    IA["🧠 IA opcional"]

    P --> C
    L -.-> C
    G -.-> C
    C --> T1 --> T2 --> T3 --> T4 --> DB --> UI
    IA <-.-> UI
```

Um ciclo de busca, passo a passo:

1. ⏰ **Na hora marcada**, o joBot acorda. Ou quando você aperta "buscar agora".
2. 🤖 **Cada coletor** (o código que lê as vagas de uma fonte) visita a sua fonte com calma e traz as vagas num formato único.
3. 🧹 **O tratamento** junta vagas repetidas, entende o salário, coloca rótulos e marca como fechadas as vagas que sumiram.
4. 🗄️ **Tudo vai para o banco** SQLite, um arquivo que fica no seu computador.
5. 📋 **O painel** mostra o resultado no seu navegador. Ele só funciona no seu computador (endereço 127.0.0.1).
6. 🧠 **Se você ligou a IA**, ela calcula o encaixe com o seu perfil e ajuda a preparar candidaturas.

> [!TIP]
> Se uma fonte falhar, as outras continuam. Se o computador estava desligado na hora marcada, a busca perdida roda quando ele liga.

> [!NOTE]
> Quer ver o joBot por dentro, com as pastas, as camadas, o banco e os diagramas? Veja a página [Arquitetura](Arquitetura).

## 🧹 O tratamento das vagas

<details>
<summary><strong>Duplicadas e ciclo de vida</strong></summary>

- A vaga repetida é encontrada pelo endereço dela, sem os parâmetros de rastreamento.
- A vaga fecha quando some da fonte. Se a fonte estava "parcial", só fecha depois de 30 dias sumida.
- Vaga com prazo vencido sai das listas.
- Nenhuma vaga é apagada. O ciclo de vida marca, não apaga.
</details>

<details>
<summary><strong>Salário</strong></summary>

- O leitor de salário separa salário de benefícios, confere o período (por hora, mês ou ano) e se o valor é plausível.
- Salário em moeda estrangeira é convertido para a moeda de exibição que você escolhe em Configurações (a do seu país por padrão), pela cotação PTAX do Banco Central, quando houver cotação.
- Sem cotação, a vaga não é eliminada pelo filtro de salário mínimo.
</details>

<details>
<summary><strong>Rótulos e encaixe</strong></summary>

- Rótulos: área, nível, modalidade (presencial, híbrido, remoto), região e tipo de contrato, além de avisos como "exige visto".
- Encaixe com o seu perfil em três níveis (● bom, ◐ médio, ○ fraco), sempre com os motivos.
- O acerto de cada rótulo é medido num gabarito de 329 vagas reais, de 30 fontes.
</details>

## 🖥️ As duas versões

O joBot tem um núcleo só e duas "caras".

| | 💻 Versão para baixar | 🌐 Versão no navegador (GitHub Pages) |
|---|---|---|
| **Instalação** | Nativa, com um comando (planejada) | Nenhuma: é só abrir o site |
| **Fontes** | Todas | Só fontes públicas |
| **Sites com login** | Sim, você entra numa janela comum do navegador | Não |
| **IA** | Automática (Claude, modelo local) ou manual | Manual (copiar e colar); rótulos só por regras |
| **Extensão, Gmail e áudio** | Sim | Não |
| **Onde ficam os dados** | No banco SQLite do seu computador | Seu perfil fica no seu navegador |
| **Atualização** | A cada 3 h (públicas) e 2x por dia (login) | Uma vez por dia |
| **Quando chega** | É o foco do projeto | Fase 8 |

Na versão no navegador, você pode exportar o perfil num arquivo e importar depois na versão para baixar. Ela nunca usa logins nem segredos.

## 🌎 Fontes de vagas

Cada fonte tem uma chave liga/desliga.

| Grupo | Exemplos |
|---|---|
| Repositórios de vagas no GitHub | backend-br, frontendbr, soujava, remotejobsbr, developersRJ |
| Sites e APIs internacionais | Jobicy, Hacker News "Who is hiring", Remotive, RemoteOK, Himalayas, We Work Remotely |
| Quadros de vagas de empresas (sistemas de recrutamento, os "ATS") | Greenhouse, Lever, Ashby, SmartRecruiters, Workday, Eightfold, Oracle HCM, InHire, Quickin, Recrutei |
| Portais brasileiros | Gupy, CIEE, Sólides, IEL, Super Estágios, Cia de Talentos, Eureca, Abler |
| Carreiras de grandes empresas | Google, Amazon, Microsoft, NVIDIA |
| Murais de estágio | Murais públicos, como o da USP |
| 🔐 Site com login (o único por enquanto) | LinkedIn |
| 🔐 Sites com login (ideias para o futuro, ainda sem data) | Vagas.com, Catho, Indeed |
| 🔐 Sites com login (ideias para o futuro, um de cada vez) | InfoJobs, Glassdoor, Remotar, Trampos |
| 🔐 Sites com login só de tecnologia (ideias para o futuro, por último, um de cada vez) | Programathor, GeekHunter, Revelo, Coodesh |

- 🤝 **Coleta educada.** O robô se identifica, espera entre um pedido e outro e espera mais quando o site pede calma.
- 🩺 **Saúde de cada fonte.** A cada busca, cada fonte fica marcada como ok, parcial ou falhou, e você vê isso no painel.
- 🏷️ **Crédito.** Fontes que pedem crédito mostram "via &lt;fonte&gt;" com link para a vaga original.

> [!WARNING]
> **Sites com login têm risco.** Eles podem restringir contas que acessam de forma automática.
> O joBot reduz o risco: você entra numa janela comum do navegador, sem automação, como quiser (Google, e-mail e senha), e fecha a janela; o joBot confere a sessão sozinho e nunca digita a senha. Depois ele só lê e visita poucas vezes, devagar. Mesmo assim, o risco existe. **Você decide se liga cada site.**

## 📋 O painel

- **Abas:** Destaques de hoje, Todas, Novas, Fecham logo, Salvas, Candidatei, Programas e Ocultas.
- **Filtros** em "chips" (botõezinhos) com contagem: país e há quantos dias a vaga foi publicada ficam à vista; salário, cidade, empresa e palavras que a vaga não pode ter ficam em "Mais filtros". O filtro atual fica no endereço da página, então dá para salvar o link. Busca rápida com a tecla `/`.
- **Status de cada vaga:** nova → salva → candidatei → entrevista → recusada ou oferta.
- **Calendário de 12 meses** em cada vaga, para ver prazos de relance.
- **"Algo errado nesta vaga?"**: um botão para corrigir um rótulo ou dado.
- **Visual inspirado no estilo da Apple:** translucidez, animações suaves, modo claro e escuro seguindo o sistema.
- **Idiomas:** português e inglês.

## 🌙 Segundo plano

| Fonte | Frequência |
|---|---|
| Fontes públicas | A cada 3 horas |
| Sites com login | Duas vezes por dia (9h e 18h, ajustável) |
| Botão "buscar agora" | Na hora, respeitando o intervalo mínimo de algumas fontes |

Rodar em segundo plano é escolha sua, no assistente da primeira execução ou nas configurações. Ligado, o joBot inicia com o computador, sem janela, e um atalho "joBot" abre o painel.

## 🧠 Inteligência artificial (opcional)

> **Regra de ouro:** a IA só usa os dados do seu perfil. Ela nunca inventa experiência, curso ou habilidade, e mostra quais dados usou.

Cada tarefa escolhe a sua opção: sessão do Claude Code que você já tem, chave da API da Anthropic, modelo local (Qwen, grátis e sem internet), palavras-chave (sem IA) ou IA manual (copiar e colar). Detalhes em [Tecnologias](Tecnologias) e no [README](https://github.com/fezarosa-dev/joBot#inteligencia-artificial).
