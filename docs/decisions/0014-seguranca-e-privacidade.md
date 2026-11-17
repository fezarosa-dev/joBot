# 0014. Segurança e privacidade

- **Status:** aceita
- **Data:** 2026-11-13
- **Atualizada:** 2026-11-16 (senha de app do Gmail, ver [0024](0024-gmail-por-senha-de-app.md)); 2026-11-17 (serviços e downloads novos da fase 4 e o RunPod do Laya só com o dono, para confirmar, D185 e [0026](0026-ia-da-fase-4.md))

## Contexto

O joBot guarda dados sensíveis (CPF, data de nascimento, currículo) e segredos (tokens e chaves). Por isso a proteção precisa ser decidida antes do código. O projeto ainda não tem código; isto é o plano.

## Decisão

- Segredos (senha de app do Gmail, chave da API da Anthropic, token do bot do Telegram) ficam no cofre de senhas do sistema, pela biblioteca keyring (licença MIT). Sem cofre disponível: arquivo legível só pelo usuário e aviso no painel.
- CPF e data de nascimento ficam no SQLite (banco de dados em arquivo), numa pasta de dados do usuário do sistema, que não é sincronizada com nuvem e que só o usuário acessa. O painel recomenda ligar a criptografia de disco (LUKS, BitLocker ou FileVault).
- Exportar o perfil não leva documentos pessoais (como o CPF), a menos que a pessoa marque a opção.
- Sem telemetria: o joBot não manda dados de uso para ninguém.
- O painel só escuta em 127.0.0.1 (acessível só a partir do próprio computador) e confere o cabeçalho Host. A extensão usa pareamento (ver [0012](0012-extensao-do-navegador.md)).
- O joBot nunca digita senha. Só resolve CAPTCHA pelo serviço que a pessoa liga (2Captcha, com a chave dela, só na navegação com login), nunca sozinho e nunca nas fontes públicas (ver [0022](0022-captcha-pelo-servico-da-pessoa.md)).
- A chave do 2Captcha segue a mesma regra dos outros segredos: cofre de senhas do sistema, ou arquivo legível só pelo usuário. Nunca aparece no painel, no log nem em mensagem de erro.
- A chave do RunPod (só para o treino da fase 7) fica no arquivo `.env`, escrita pela própria pessoa. Esse arquivo não entra no git.

## Consequências

- Os dados só saem do computador para os serviços que a pessoa ligar: Anthropic, OpenAI, Google (Gmail e Gemini), Telegram e o serviço que a pessoa configurar no backend compatível com OpenAI (ver [0009](0009-ia-backends-e-modelos.md)), e também o Jev (classificação de e-mail, ver [0009](0009-ia-backends-e-modelos.md)), o 2Captcha (só na navegação com login e só com a chave posta e o interruptor ligado; vão o endereço da página, a `sitekey` e o user agent do navegador, e nada de dado pessoal; a chave vai ao serviço para resolver e para o botão de teste) e o RunPod (só no treino da fase 7). Na IA manual, os dados vão para a IA de chat onde a pessoa colar. Pedidos sem dado pessoal que o joBot faz por padrão: às fontes públicas de vagas, ao Banco Central (cotação) e ao GitHub (aviso de versão, uma vez por dia; desliga em Configurações, Privacidade).

## Nota (2026-11-16): botão de e-mail na vaga

- Exceção à regra 14.3 da fase 1: o botão de candidatura por e-mail é um link `mailto:`. Só `mailto:`, só com um endereço que passou pela lista fechada de caracteres, montado pelo joBot, com o título da vaga como único parâmetro.
- O endereço não é guardado. Link dentro da descrição continua não clicável, e nenhum outro esquema vale.
- Nenhuma rede nova: o `mailto:` é navegação da pessoa, não um pedido do painel.

## Nota (2026-11-17, para confirmar): pedidos novos da fase 4

- Serviços de IA (D185.4 e D185.22, para confirmar): a API da Anthropic, a OpenAI, o Gemini e o serviço do backend compatível só recebem dados com a tarefa ligada pela pessoa, e só os campos da lista permitida de cada tarefa. Nome, e-mail, telefone e cidade nunca vão; e-mail, telefone e CPF são tirados de todo texto livre. As chaves seguem a regra dos outros segredos.
- Downloads do modelo local (D185.7, para confirmar): o `llama-server` vem do GitHub e o modelo do Hugging Face (com os CDNs deles), só a pedido da pessoa, com sha256 conferido. O `llama-server` escuta só em `127.0.0.1`.
- RunPod (D185.8, para confirmar): o treino do Laya antes da fase 4 só roda se o dono autorizar o gasto; até lá, nenhuma chamada cria recurso cobrado.
- O README e a tela Privacidade passam a citar esses pedidos quando eles chegarem.

## Ver também

- [0008. Painel e visual](0008-painel-e-visual.md)
- [0010. Usar o Claude Code que a pessoa já tem (sem login dentro do joBot)](0010-claude-code-da-pessoa.md)
- [0012. Extensão do navegador](0012-extensao-do-navegador.md)
- [0013. Gmail e avisos](0013-gmail-e-avisos.md)
- [0022. CAPTCHA resolvido pelo serviço que a pessoa liga](0022-captcha-pelo-servico-da-pessoa.md)
- [0024. Gmail por senha de app](0024-gmail-por-senha-de-app.md)
- [0026. IA da fase 4: tarefas, backends e modelo local](0026-ia-da-fase-4.md)
- [duvidas.md: D185 (fase 4)](../../duvidas.md)
