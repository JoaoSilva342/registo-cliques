const fundoModal = document.getElementById("fundo-modal");
const botaoFecharModal = document.getElementById("fechar-modal");

const modalBotao = document.getElementById("modal-botao");
const modalData = document.getElementById("modal-data");
const modalHora = document.getElementById("modal-hora");
const modalTotalBotao = document.getElementById("modal-total-botao");

// Fecha automaticamente o modal após alguns segundos.
let temporizadorFechoModal = null;

// ===== Tutorial (setas/realce) =====
function iniciarTutorial({ forcado = false } = {}) {
  // Intro.js é carregado via CDN; se falhar (sem net), não quebra a app.
  if (typeof window.introJs !== "function") return;

  const jaVisto = localStorage.getItem("tutorial_visto") === "1";
  if (!forcado && jaVisto) return;

  const intro = window.introJs();
  intro.setOptions({
    nextLabel: "Seguinte",
    prevLabel: "Anterior",
    doneLabel: "Fechar",
    showProgress: false,
    showBullets: false,
    exitOnOverlayClick: true,
    steps: [
      {
        element: document.querySelector("#btn-b1"),
        intro: "Clica num botão para registares um clique.",
        position: "bottom"
      },
      {
        element: document.querySelector("#cont-b1"),
        intro: "Aqui vês os cliques de hoje (actualiza automaticamente).",
        position: "bottom"
      },
      {
        element: document.querySelector("#link-admin"),
        intro: "Se fores admin, entra aqui.",
        position: "left"
      }
    ]
  });

  intro.oncomplete(() => localStorage.setItem("tutorial_visto", "1"));
  intro.onexit(() => localStorage.setItem("tutorial_visto", "1"));
  intro.start();
}

function mostrarDicaModalSePrimeiraVez() {
  if (typeof window.introJs !== "function") return;
  const jaVisto = localStorage.getItem("dica_modal_vista") === "1";
  if (jaVisto) return;

  // Pequena dica só para o modal.
  const intro = window.introJs();
  intro.setOptions({
    nextLabel: "Ok",
    prevLabel: "",
    doneLabel: "Ok",
    showProgress: false,
    showBullets: false,
    exitOnOverlayClick: true,
    steps: [
      {
        element: document.querySelector("#fechar-modal"),
        intro: "O clique ficou registado. Fecha aqui.",
        position: "top"
      }
    ]
  });
  intro.oncomplete(() => localStorage.setItem("dica_modal_vista", "1"));
  intro.onexit(() => localStorage.setItem("dica_modal_vista", "1"));
  intro.start();
}

function abrirModal(dados) {
  modalBotao.textContent = dados.botao;
  modalData.textContent = dados.data;
  modalHora.textContent = dados.hora;
  modalTotalBotao.textContent = dados.total_botao_hoje;

  fundoModal.classList.remove("escondido");
  botaoFecharModal.focus();

  // Se o utilizador clicar rapidamente várias vezes, garante que só há 1 temporizador.
  if (temporizadorFechoModal) clearTimeout(temporizadorFechoModal);
  temporizadorFechoModal = setTimeout(() => {
    fecharModal();
  }, 3000);

  // Dica curta na primeira vez que o modal aparece.
  mostrarDicaModalSePrimeiraVez();
}

function fecharModal() {
  fundoModal.classList.add("escondido");

  if (temporizadorFechoModal) {
    clearTimeout(temporizadorFechoModal);
    temporizadorFechoModal = null;
  }
}

async function obterContagensHoje() {
  const resposta = await fetch("/contagens_hoje");
  if (!resposta.ok) throw new Error("Não foi possível obter as contagens.");
  return resposta.json();
}

function aplicarContagens(contagens) {
  document.querySelectorAll("[data-contador-id]").forEach((el) => {
    const id = el.getAttribute("data-contador-id");
    el.textContent = contagens?.[id] ?? 0;
  });
}

function mostrarObrigado(botaoId) {
  const el = document.querySelector(`[data-mensagem-id="${botaoId}"]`);
  if (!el) return;

  el.textContent = "Obrigado por clicar";
  el.classList.add("mensagem-visivel");

  setTimeout(() => {
    el.textContent = "";
    el.classList.remove("mensagem-visivel");
  }, 2500);
}

async function enviarClique(botaoId) {
  const resposta = await fetch("/clique", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ botao_id: botaoId })
  });

  if (!resposta.ok) {
    const erro = await resposta.json().catch(() => ({}));
    throw new Error(erro.erro || "Erro ao registar o clique.");
  }

  return resposta.json();
}

document.querySelectorAll(".botao").forEach(botao => {
  botao.addEventListener("click", async () => {
        const botaoId = botao.dataset.botaoId;
    botao.disabled = true;

    try {
            const dados = await enviarClique(botaoId);
      abrirModal(dados);
      mostrarObrigado(dados.botao_id);

      const info = await obterContagensHoje();
      aplicarContagens(info.contagens);
    } catch (erro) {
      alert(erro.message);
    } finally {
      botao.disabled = false;
    }
  });
});

/* Fechar modal */
botaoFecharModal.addEventListener("click", fecharModal);
fundoModal.addEventListener("click", (e) => { if (e.target === fundoModal) fecharModal(); });
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !fundoModal.classList.contains("escondido")) fecharModal();
});

/* Contagens iniciais */
(async () => {
  try {
    const info = await obterContagensHoje();
    aplicarContagens(info.contagens);
  } catch {
    // não faz mal se falhar
  }
})();

// Tutorial: aparece só a quem entra pela primeira vez
document.addEventListener("DOMContentLoaded", () => {
  const btnAjuda = document.getElementById("btn-ajuda");
  if (btnAjuda) btnAjuda.addEventListener("click", () => iniciarTutorial({ forcado: true }));
  iniciarTutorial();
});
