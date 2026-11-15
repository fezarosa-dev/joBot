# 0014. Segurança e privacidade

- **Status:** aceita
- **Data:** 2026-11-13
- **Atualizada:** 2026-11-15 (mais serviços de IA, o aviso de versão ligado por padrão e o 2Captcha, ver [0022](0022-captcha-pelo-servico-da-pessoa.md))

## Contexto

O joBot guarda dados sensíveis (CPF, data de nascimento, currículo) e segredos (tokens e chaves). Por isso a proteção precisa ser decidida antes do código. O projeto ainda não tem código; isto é o plano.

## Decisão

- Segredos (token do Gmail, chave da API da Anthropic, token do bot do Telegram) ficam no cofre de senhas do sistema, pela biblioteca keyring (licença MIT). Sem cofre disponível: arquivo legível só pelo usuário e aviso no painel.
- CPF e data de nascimento ficam no SQLite (banco de dados em arquivo), numa pasta de dados do usuário do sistema, que não é sincronizada com nuvem e que só o usuário acessa. O painel recomenda ligar a criptografia de disco (LUKS, BitLocker ou FileVault).
- Exportar o perfil não leva documentos pessoais (como o CPF), a menos que a pessoa marque a opção.
- Sem telemetria: o joBot não manda dados de uso para ninguém.
- O painel só escuta em 127.0.0.1 (acessível só a partir do próprio computador) e confere o cabeçalho Host. A extensão usa pareamento (ver [0012](0012-extensao-do-navegador.md)).
- O joBot nunca digita senha. Só resolve CAPTCHA pelo serviço que a pessoa liga (2Captcha, com a chave dela, só na navegação com login), nunca sozinho e nunca nas fontes públicas (ver [0022](0022-captcha-pelo-servico-da-pessoa.md)).
- A chave do 2Captcha segue a mesma regra dos outros segredos: cofre de senhas do sistema, ou arquivo legível só pelo usuário. Nunca aparece no painel, no log nem em mensagem de erro.
- A chave do RunPod (só para o treino da fase 6) fica no arquivo `.env`, escrita pela própria pessoa. Esse arquivo não entra no git.

## Consequências

- Os dados só saem do computador para os serviços que a pessoa ligar: Anthropic, OpenAI, Google (Gmail e Gemini), Telegram e o serviço que a pessoa configurar no backend compatível com OpenAI (ver [0009](0009-ia-backends-e-modelos.md)), e também o Jev (classificação de e-mail, ver [0009](0009-ia-backends-e-modelos.md)), o 2Captcha (só na navegação com login e só com a chave posta e o interruptor ligado; vão o endereço da página, a `sitekey` e o user agent do navegador, e nada de dado pessoal; a chave vai ao serviço para resolver e para o botão de teste) e o RunPod (só no treino da fase 6). Na IA manual, os dados vão para a IA de chat onde a pessoa colar. Pedidos sem dado pessoal que o joBot faz por padrão: às fontes públicas de vagas, ao Banco Central (cotação) e ao GitHub (aviso de versão, uma vez por dia; desliga em Configurações, Privacidade).

## Ver também

- [0008. Painel e visual](0008-painel-e-visual.md)
- [0010. Usar o Claude Code que a pessoa já tem (sem login dentro do joBot)](0010-claude-code-da-pessoa.md)
- [0012. Extensão do navegador](0012-extensao-do-navegador.md)
- [0013. Gmail e avisos](0013-gmail-e-avisos.md)
- [0022. CAPTCHA resolvido pelo serviço que a pessoa liga](0022-captcha-pelo-servico-da-pessoa.md)
