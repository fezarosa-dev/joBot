// O único JavaScript próprio do painel (desenho 13.1). Sem script inline: o CSP só aceita 'self'.
(() => {
  "use strict";

  const token = document.querySelector('meta[name="csrf-token"]')?.content ?? "";

  // token CSRF em todo pedido do HTMX (desenho 14.4)
  document.addEventListener("htmx:configRequest", (evento) => {
    evento.detail.headers["X-CSRF-Token"] = token;
  });

  // depois de uma troca, o foco vai para o [data-foco] do trecho novo, se ele tiver um;
  // trecho sem [data-foco] (ex.: andamento que atualiza sozinho) não rouba o foco.
  // Com hx-swap="outerHTML" o alvo é o nó antigo, já fora do DOM: aí vale o nó do evento
  document.addEventListener("htmx:afterSwap", (evento) => {
    const alvo = evento.detail.target;
    const raiz = alvo && alvo.isConnected ? alvo : evento.target;
    if (!raiz) return;
    const foco = raiz.matches("[data-foco]") ? raiz : raiz.querySelector("[data-foco]");
    if (!foco) return;
    if (!foco.matches("a[href], button, input, select, textarea, [tabindex]")) {
      foco.setAttribute("tabindex", "-1");
    }
    foco.focus();
  });

  // erro de um clique do HTMX (T151; D106): o aviso fixo da casca mostra o texto que o servidor
  // mandou em <p data-aviso-erro> ou, sem ele, o genérico da faixa do status. Só textContent.
  // Voltar/avançar troca o conteúdo do body (push-url sem hx-history-elt): o nó é buscado na hora,
  // o botão fechar usa delegação e o aviso é escondido antes de o histórico guardar a página.
  // Depois de fechado, o mesmo texto não reabre (polling e carga com o servidor fora do ar errariam a
  // cada 2 s): `fechado` guarda o texto que a pessoa fechou; um aviso novo (texto diferente) ou um
  // pedido que dá certo zera. Todo erro continua aparecendo; só não insiste depois de fechado.
  // shortcut: guarda só um texto; dois erros diferentes que se alternam reabrem a cada ciclo, trocar por um conjunto se aparecer
  let fechado = null;
  const textoDoAviso = (aviso) => aviso.querySelector("[data-aviso-texto]");
  const mostrarAviso = (chave, texto) => {
    const aviso = document.getElementById("aviso-erro");
    if (!aviso) return;
    const final = texto || aviso.getAttribute(chave);
    if (final === fechado) return;
    fechado = null;
    textoDoAviso(aviso).textContent = final;
    aviso.hidden = false;
  };
  document.addEventListener("htmx:responseError", (evento) => {
    const xhr = evento.detail.xhr;
    const doc = new DOMParser().parseFromString(xhr.responseText ?? "", "text/html");
    const texto = doc.querySelector("[data-aviso-erro]")?.textContent.trim();
    mostrarAviso(xhr.status < 500 ? "data-msg-4xx" : "data-msg-5xx", texto);
  });
  document.addEventListener("htmx:sendError", () => mostrarAviso("data-msg-rede"));
  document.addEventListener("htmx:beforeHistorySave", () => {
    const aviso = document.getElementById("aviso-erro");
    if (aviso) aviso.hidden = true;
  });
  document.addEventListener("htmx:afterRequest", (evento) => {
    if (evento.detail.successful) fechado = null;
  });
  document.addEventListener("click", (evento) => {
    if (!evento.target.closest("[data-aviso-fechar]")) return;
    const aviso = document.getElementById("aviso-erro");
    fechado = textoDoAviso(aviso).textContent;
    aviso.hidden = true;
  });

  // tecla "/" vai para a busca ([data-busca]), fora de campos de texto
  document.addEventListener("keydown", (evento) => {
    if (evento.key !== "/" || evento.ctrlKey || evento.metaKey || evento.altKey) return;
    const ativo = document.activeElement;
    if (ativo && (ativo.isContentEditable || ativo.matches("input, textarea, select"))) return;
    const busca = document.querySelector("[data-busca]");
    if (!busca) return;
    evento.preventDefault();
    busca.focus();
  });

  // chave de tema: troca na hora, sem esperar a volta do servidor
  document.addEventListener("submit", (evento) => {
    const botao = evento.submitter;
    if (botao && botao.name === "tema") document.documentElement.dataset.tema = botao.value;
  });
})();
