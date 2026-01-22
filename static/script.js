const fundoModal = document.getElementById("fundo-modal");
const botaoFecharModal = document.getElementById("fechar-modal");

const modalBotao = document.getElementById("modal-botao");
const modalData = document.getElementById("modal-data");
const modalHora = document.getElementById("modal-hora");
const modalTotalBotao = document.getElementById("modal-total-botao");

const contB1 = document.getElementById("cont-b1");
const contB2 = document.getElementById("cont-b2");
const contB3 = document.getElementById("cont-b3");
const contB4 = document.getElementById("cont-b4");

function abrirModal(dados) {
  modalBotao.textContent = dados.botao;
  modalData.textContent = dados.data;
  modalHora.textContent = dados.hora;
  modalTotalBotao.textContent = dados.total_botao_hoje;

  fundoModal.classList.remove("escondido");
  botaoFecharModal.focus();
}

function fecharModal() {
  fundoModal.classList.add("escondido");
}

async function obterContagensHoje() {
  const resposta = await fetch("/contagens_hoje");
  if (!resposta.ok) throw new Error("Não foi possível obter as contagens.");
  return resposta.json();
}

function aplicarContagens(contagens) {
  contB1.textContent = contagens["Botão 1"] ?? 0;
  contB2.textContent = contagens["Botão 2"] ?? 0;
  contB3.textContent = contagens["Botão 3"] ?? 0;
  contB4.textContent = contagens["Botão 4"] ?? 0;
}

async function enviarClique(nomeBotao) {
  const resposta = await fetch("/clique", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ botao: nomeBotao })
  });

  if (!resposta.ok) {
    const erro = await resposta.json().catch(() => ({}));
    throw new Error(erro.erro || "Erro ao registar o clique.");
  }

  return resposta.json();
}

document.querySelectorAll(".botao").forEach(botao => {
  botao.addEventListener("click", async () => {
    const nomeBotao = botao.dataset.botao;
    botao.disabled = true;

    try {
      const dados = await enviarClique(nomeBotao);
      abrirModal(dados);

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
