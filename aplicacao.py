from flask import Flask, render_template, request, jsonify, send_file, abort, Response
import sqlite3
from datetime import datetime
import os

NOME_BASE_DADOS = "cliques.db"

# ADMIN
UTILIZADOR_ADMIN = "admin"
SENHA_ADMIN = os.getenv("ADMIN_PASSWORD", "admin123")  # podes deixar assim

aplicacao = Flask(__name__)

def verificar_admin() -> bool:
    # Admin entra com /admin?u=admin&p=admin123
    u = request.args.get("u", "")
    p = request.args.get("p", "")
    return (u == UTILIZADOR_ADMIN and p == SENHA_ADMIN)

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

    agora = datetime.now()
    data_texto = agora.strftime("%Y-%m-%d")
    hora_texto = agora.strftime("%H:%M")

    ligacao = obter_ligacao_base_dados()
    cursor = ligacao.cursor()

    cursor.execute("SELECT COALESCE(MAX(sequencial), 0) AS maximo FROM cliques WHERE data = ?", (data_texto,))
    sequencial = cursor.fetchone()["maximo"] + 1

    cursor.execute(
        "INSERT INTO cliques(botao, sequencial, data, hora) VALUES (?, ?, ?, ?)",
        (botao, sequencial, data_texto, hora_texto)
    )
    ligacao.commit()

    cursor.execute("SELECT COUNT(*) AS total FROM cliques WHERE data = ? AND botao = ?", (data_texto, botao))
    total_botao_hoje = cursor.fetchone()["total"]

    ligacao.close()

    return jsonify({
        "botao": botao,
        "sequencial": sequencial,
        "data": data_texto,
        "hora": hora_texto,
        "total_botao_hoje": total_botao_hoje
    })

@aplicacao.route("/contagens_hoje", methods=["GET"])
def contagens_hoje():
    agora = datetime.now()
    data_texto = agora.strftime("%Y-%m-%d")

    ligacao = obter_ligacao_base_dados()
    cursor = ligacao.cursor()

    contagens = {}
    for b in ["Botão 1", "Botão 2", "Botão 3", "Botão 4"]:
        cursor.execute("SELECT COUNT(*) AS total FROM cliques WHERE data = ? AND botao = ?", (data_texto, b))
        contagens[b] = cursor.fetchone()["total"]

    ligacao.close()
    return jsonify({"data": data_texto, "contagens": contagens})

@aplicacao.route("/hoje", methods=["GET"])
def ver_cliques_de_hoje():
    agora = datetime.now()
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

    return jsonify({"data": data_texto, "ultimos_20": registos})

# =========================
# ADMIN: página simples
# =========================
@aplicacao.route("/admin", methods=["GET"])
def pagina_admin():
    if not verificar_admin():
        return render_template("admin.html", autorizado=False, u="", p=""), 403

    u = request.args.get("u", "")
    p = request.args.get("p", "")
    return render_template("admin.html", autorizado=True, u=u, p=p)

@aplicacao.route("/admin/download_db", methods=["GET"])
def admin_download_db():
    if not verificar_admin():
        abort(403)

    if not os.path.exists(NOME_BASE_DADOS):
        abort(404)

    # Faz download do ficheiro cliques.db
    return send_file(
        NOME_BASE_DADOS,
        as_attachment=True,
        download_name="cliques.db"
    )

@aplicacao.route("/admin/download_txt", methods=["GET"])
def admin_download_txt():
    if not verificar_admin():
        abort(403)

    ligacao = obter_ligacao_base_dados()
    cursor = ligacao.cursor()
    cursor.execute("""
        SELECT id, botao, sequencial, data, hora
        FROM cliques
        ORDER BY id ASC
    """)
    linhas = cursor.fetchall()
    ligacao.close()

    # Gerar texto simples
    conteudo = []
    conteudo.append("REGISTO DE CLIQUES (BASE DE DADOS)\n")
    conteudo.append("Formato: id | botao | sequencial | data | hora\n")
    conteudo.append("-" * 60 + "\n")

    for l in linhas:
        conteudo.append(f"{l['id']} | {l['botao']} | {l['sequencial']} | {l['data']} | {l['hora']}\n")

    texto_final = "".join(conteudo)

    return Response(
        texto_final,
        mimetype="text/plain",
        headers={
            "Content-Disposition": "attachment; filename=cliques.txt"
        }
    )

if __name__ == "__main__":
    iniciar_base_dados()
    aplicacao.run(host="0.0.0.0", port=5000, debug=True)
else:
    iniciar_base_dados()
