from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
import sqlite3
import os
import io
import csv
from datetime import datetime

NOME_BASE_DADOS = "cliques.db"

aplicacao = Flask(__name__)
aplicacao.secret_key = "muda-isto-para-uma-chave-secreta"

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

    # Sequencial diário: máximo do dia + 1
    cursor.execute("SELECT COALESCE(MAX(sequencial), 0) AS maximo FROM cliques WHERE data = ?", (data_texto,))
    maximo = cursor.fetchone()["maximo"]
    sequencial = maximo + 1

    cursor.execute(
        "INSERT INTO cliques(botao, sequencial, data, hora) VALUES (?, ?, ?, ?)",
        (botao, sequencial, data_texto, hora_texto)
    )
    ligacao.commit()

    # Quantas vezes este botão foi clicado HOJE
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

    return jsonify({
        "data": data_texto,
        "contagens": contagens
    })

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

    return jsonify({
        "data": data_texto,
        "ultimos_20": registos
    })



# ===== Admin (simples) =====
UTILIZADOR_ADMIN = "admin"
SENHA_ADMIN = "admin123"

def _esta_admin():
    return bool(session.get("admin_autenticado"))

def _exigir_admin():
    if not _esta_admin():
        return redirect(url_for("admin_login"))
    return None

@aplicacao.route("/admin", methods=["GET", "POST"])
def admin_login():
    erro = None
    if request.method == "POST":
        utilizador = (request.form.get("utilizador") or "").strip()
        senha = request.form.get("senha") or ""
        if utilizador == UTILIZADOR_ADMIN and senha == SENHA_ADMIN:
            session["admin_autenticado"] = True
            return redirect(url_for("admin_painel"))
        erro = "Credenciais inválidas."
    return render_template("admin_login.html", erro=erro)

@aplicacao.route("/admin/painel")
def admin_painel():
    red = _exigir_admin()
    if red:
        return red

    ligacao = obter_ligacao_base_dados()
    cursor = ligacao.cursor()

    # Resumo de hoje
    agora = datetime.now()
    data_texto = agora.strftime("%Y-%m-%d")

    cursor.execute("SELECT COUNT(*) AS total FROM cliques WHERE data = ?", (data_texto,))
    total_hoje = cursor.fetchone()["total"]

    contagens = {}
    for b in ["Botão 1", "Botão 2", "Botão 3", "Botão 4"]:
        cursor.execute("SELECT COUNT(*) AS total FROM cliques WHERE data = ? AND botao = ?", (data_texto, b))
        contagens[b] = cursor.fetchone()["total"]

    # Últimos 100 cliques (geral)
    cursor.execute("""
        SELECT botao, sequencial, data, hora
        FROM cliques
        ORDER BY id DESC
        LIMIT 100
    """)
    ultimos = [dict(linha) for linha in cursor.fetchall()]

    ligacao.close()

    return render_template(
        "admin_painel.html",
        data_hoje=data_texto,
        total_hoje=total_hoje,
        contagens=contagens,
        ultimos=ultimos
    )

def _obter_resumo_e_cliques_do_dia(data_texto: str):
    ligacao = obter_ligacao_base_dados()
    cursor = ligacao.cursor()

    cursor.execute("SELECT COUNT(*) AS total FROM cliques WHERE data = ?", (data_texto,))
    total = cursor.fetchone()["total"]

    contagens = {}
    for b in ["Botão 1", "Botão 2", "Botão 3", "Botão 4"]:
        cursor.execute("SELECT COUNT(*) AS total FROM cliques WHERE data = ? AND botao = ?", (data_texto, b))
        contagens[b] = cursor.fetchone()["total"]

    cursor.execute('''
        SELECT botao, sequencial, data, hora
        FROM cliques
        WHERE data = ?
        ORDER BY id ASC
    ''', (data_texto,))
    registos = [dict(linha) for linha in cursor.fetchall()]

    ligacao.close()
    return total, contagens, registos


@aplicacao.route("/admin/export/txt")
def admin_exportar_txt():
    red = _exigir_admin()
    if red:
        return red

    data_texto = request.args.get("dia") or datetime.now().strftime("%Y-%m-%d")
    total, contagens, registos = _obter_resumo_e_cliques_do_dia(data_texto)

    linhas = []
    linhas.append(f"Relatório de cliques — {data_texto}")
    linhas.append("")
    linhas.append(f"Total do dia: {total}")
    for b in ["Botão 1", "Botão 2", "Botão 3", "Botão 4"]:
        linhas.append(f"{b}: {contagens.get(b, 0)}")
    linhas.append("")
    linhas.append("Registos (ordem de criação):")
    linhas.append("hora\tsequencial\tbotao")
    for r in registos:
        linhas.append(f"{r['hora']}\t{r['sequencial']}\t{r['botao']}")

    conteudo = "\n".join(linhas) + "\n"
    nome = f"cliques_{data_texto}.txt"
    return Response(
        conteudo,
        mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={nome}"}
    )


@aplicacao.route("/admin/export/csv")
def admin_exportar_csv():
    red = _exigir_admin()
    if red:
        return red

    data_texto = request.args.get("dia") or datetime.now().strftime("%Y-%m-%d")
    _total, _contagens, registos = _obter_resumo_e_cliques_do_dia(data_texto)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["data", "hora", "sequencial", "botao"])
    for r in registos:
        w.writerow([r["data"], r["hora"], r["sequencial"], r["botao"]])

    nome = f"cliques_{data_texto}.csv"
    return Response(
        buf.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={nome}"}
    )


@aplicacao.route("/admin/export/json")
def admin_exportar_json():
    red = _exigir_admin()
    if red:
        return red

    data_texto = request.args.get("dia") or datetime.now().strftime("%Y-%m-%d")
    total, contagens, registos = _obter_resumo_e_cliques_do_dia(data_texto)

    payload = {
        "data": data_texto,
        "total": total,
        "contagens": contagens,
        "registos": registos
    }

    nome = f"cliques_{data_texto}.json"
    import json
    return Response(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        mimetype="application/json; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={nome}"}
    )


@aplicacao.route("/admin/logout")
def admin_logout():
    session.pop("admin_autenticado", None)
    return redirect(url_for("pagina_inicial"))


if __name__ == "__main__":
    iniciar_base_dados()
    aplicacao.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
else:
    iniciar_base_dados()
