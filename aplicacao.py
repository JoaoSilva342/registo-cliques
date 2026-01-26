from flask import Flask, render_template, request, jsonify, send_from_directory, abort
import sqlite3
from datetime import datetime
import os
from werkzeug.utils import secure_filename

NOME_BASE_DADOS = "cliques.db"

# ===== ADMIN / UPLOADS =====
PASTA_UPLOADS = "uploads"
EXTENSOES_PERMITIDAS = {"txt", "csv", "pdf", "png", "jpg", "jpeg"}
PALAVRA_PASSE_ADMIN = os.getenv("ADMIN_PASSWORD", "admin123")  # podes alterar

aplicacao = Flask(__name__)
aplicacao.config["UPLOAD_FOLDER"] = PASTA_UPLOADS
aplicacao.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB

def garantir_pasta_uploads():
    os.makedirs(PASTA_UPLOADS, exist_ok=True)

def extensao_permitida(nome: str) -> bool:
    if "." not in nome:
        return False
    ext = nome.rsplit(".", 1)[1].lower()
    return ext in EXTENSOES_PERMITIDAS

def verificar_admin() -> bool:
    # simples para escola: /admin?pw=admin123
    pw = request.args.get("pw", "")
    return pw == PALAVRA_PASSE_ADMIN

# ===== BD =====
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

# ===== ADMIN =====
@aplicacao.route("/admin", methods=["GET"])
def pagina_admin():
    if not verificar_admin():
        return render_template("admin.html", autorizado=False, mensagem="Acesso negado. Usa ?pw=..."), 403

    garantir_pasta_uploads()
    ficheiros = sorted(os.listdir(PASTA_UPLOADS))
    return render_template(
        "admin.html",
        autorizado=True,
        mensagem="",
        ficheiros=ficheiros,
        extensoes=", ".join(sorted(EXTENSOES_PERMITIDAS)),
        pw=request.args.get("pw", "")
    )

@aplicacao.route("/admin/upload", methods=["POST"])
def admin_upload():
    if not verificar_admin():
        abort(403)

    garantir_pasta_uploads()

    if "ficheiro" not in request.files:
        abort(400)

    ficheiro = request.files["ficheiro"]
    if ficheiro.filename is None or ficheiro.filename.strip() == "":
        abort(400)

    nome_original = ficheiro.filename
    nome_seguro = secure_filename(nome_original)

    if not extensao_permitida(nome_seguro):
        return jsonify({"erro": "Extensão não permitida."}), 400

    caminho = os.path.join(PASTA_UPLOADS, nome_seguro)
    ficheiro.save(caminho)

    return jsonify({"ok": True, "ficheiro": nome_seguro})

@aplicacao.route("/admin/ficheiros/<nome_ficheiro>", methods=["GET"])
def admin_download(nome_ficheiro):
    if not verificar_admin():
        abort(403)

    garantir_pasta_uploads()
    nome_seguro = secure_filename(nome_ficheiro)
    caminho = os.path.join(PASTA_UPLOADS, nome_seguro)
    if not os.path.exists(caminho):
        abort(404)

    return send_from_directory(PASTA_UPLOADS, nome_seguro, as_attachment=True)

@aplicacao.route("/admin/apagar/<nome_ficheiro>", methods=["POST"])
def admin_apagar(nome_ficheiro):
    if not verificar_admin():
        abort(403)

    garantir_pasta_uploads()
    nome_seguro = secure_filename(nome_ficheiro)
    caminho = os.path.join(PASTA_UPLOADS, nome_seguro)
    if os.path.exists(caminho):
        os.remove(caminho)

    return jsonify({"ok": True})

if __name__ == "__main__":
    garantir_pasta_uploads()
    iniciar_base_dados()
    aplicacao.run(host="0.0.0.0", port=5000, debug=True)
else:
    garantir_pasta_uploads()
    iniciar_base_dados()
