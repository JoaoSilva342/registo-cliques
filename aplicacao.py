from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo  # Python 3.9+

NOME_BASE_DADOS = "cliques.db"
FUSO_HORARIO = ZoneInfo("Europe/Lisbon")

aplicacao = Flask(__name__)

def obter_ligacao_base_dados():
    ligacao = sqlite3.connect(NOME_BASE_DADOS)
    ligacao.row_factory = sqlite3.Row
    return ligacao

def iniciar_base_dados():
    ligacao = obter_ligacao_base_dados()
    cursor = ligacao.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cliques (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            botao TEXT NOT NULL,
            sequencial INTEGER NOT NULL,
            data TEXT NOT NULL,   -- AAAA-MM-DD
            hora TEXT NOT NULL    -- HH:MM
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS indice_data ON cliques(data)")
    ligacao.commit()
    ligacao.close()

@aplicacao.route("/")
def pagina_inicial():
    return render_template("pagina_inicial.html")

@aplicacao.route("/clique", methods=["POST"])
def registar_clique():
    dados = request.get_json(silent=True) or {}
    botao = dados.get("botao")

    if botao not in ["Botão 1", "Botão 2", "Botão 3", "Botão 4"]:
        return jsonify({"erro": "Botão inválido."}), 400

    agora = datetime.now(FUSO_HORARIO)
    data_texto = agora.strftime("%Y-%m-%d")
    hora_texto = agora.strftime("%H:%M")

    ligacao = obter_ligacao_base_dados()
    cursor = ligacao.cursor()

    # Sequencial diário: vai buscar o maior valor do dia e soma 1
    cursor.execute("SELECT COALESCE(MAX(sequencial), 0) AS maximo FROM cliques WHERE data = ?", (data_texto,))
    maximo = cursor.fetchone()["maximo"]
    sequencial = maximo + 1

    cursor.execute(
        "INSERT INTO cliques(botao, sequencial, data, hora) VALUES (?, ?, ?, ?)",
        (botao, sequencial, data_texto, hora_texto)
    )

    ligacao.commit()
    ligacao.close()

    return jsonify({
        "botao": botao,
        "sequencial": sequencial,
        "data": data_texto,
        "hora": hora_texto
    })

@aplicacao.route("/hoje", methods=["GET"])
def ver_cliques_de_hoje():
    """Página extra só para confirmar que a base de dados está a guardar corretamente."""
    agora = datetime.now(FUSO_HORARIO)
    data_texto = agora.strftime("%Y-%m-%d")

    ligacao = obter_ligacao_base_dados()
    cursor = ligacao.cursor()

    cursor.execute("""
        SELECT botao, sequencial, data, hora
        FROM cliques
        WHERE data = ?
        ORDER BY id DESC
        LIMIT 20
    """, (data_texto,))

    registos = [dict(linha) for linha in cursor.fetchall()]
    ligacao.close()

    return jsonify({
        "data": data_texto,
        "ultimos_20": registos
    })

if __name__ == "__main__":
    iniciar_base_dados()
    aplicacao.run(host="0.0.0.0", port=5000, debug=True)
else:
    # Isto serve para garantir que a base de dados existe quando o servidor arranca noutro ambiente
    iniciar_base_dados()
