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
      await enviarClique(nomeBotao);
    } catch (erro) {
      alert(erro.message);
    } finally {
      botao.disabled = false;
    }
  });
});
