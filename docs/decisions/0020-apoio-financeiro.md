# 0020. Apoio financeiro: só doação

- **Status:** aceita
- **Data:** 2026-11-14

## Contexto

O joBot é mantido por uma pessoa. O dono quer uma ajuda pequena para manter o projeto.

Foram pensadas várias formas de ter essa ajuda: doação, versão paga na nuvem, anúncio, link de afiliado e recurso pago.

## Decisão

- O apoio é só por doação: Pix com chave aleatória e Buy Me a Coffee. O GitHub Sponsors entra quando o perfil for ativado.
- O joBot continua inteiro grátis.
- Não há anúncio, link de afiliado, rastreio, venda de dado nem recurso pago.
- A doação não muda a ordem das vagas e não destaca nenhuma empresa.
- A chave Pix aparece só em texto, sem QR code. O QR code levaria o nome e a cidade de quem recebe.
- Onde o apoio aparece:
  - o botão de apoio do repositório no GitHub (`.github/FUNDING.yml`);
  - uma seção no README;
  - a página Apoie na wiki;
  - numa tarefa futura, um link discreto no painel. Nunca pop-up nem aviso insistente.

## Por que não as outras formas

- **Versão paga na nuvem:** quebra o "roda no seu computador" (ver a [0002](0002-duas-versoes-um-nucleo.md) e a [0014](0014-seguranca-e-privacidade.md)).
- **Anúncio e link de afiliado:** tiram a confiança de quem procura emprego.
- **Recurso pago:** dividiria quem procura emprego entre quem pode e quem não pode pagar; o joBot é inteiro grátis.

## Consequências

- Quem paga pelo Pix vê o nome de quem recebe.
- Mudança de canal de doação atualiza o README, a wiki e o `FUNDING.yml` juntos.

## Ver também

- [0002. Duas versões, um núcleo](0002-duas-versoes-um-nucleo.md)
- [0014. Segurança e privacidade](0014-seguranca-e-privacidade.md)
- [0018. Manutenção pela comunidade e CI aberto a todo PR](0018-manutencao-pela-comunidade.md)
