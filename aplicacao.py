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

NUM_BOTOES = 4

def obter_botoes():
    """Devolve lista de botões configurados (id, nome)."""
    ligacao = obter_ligacao_base_dados()
    cursor = ligacao.cursor()
    cursor.execute("SELECT id, nome FROM botoes ORDER BY id")
    botoes = [dict(linha) for linha in cursor.fetchall()]
    ligacao.close()
    return botoes

def obter_mapa_botoes():
    return {b["id"]: b["nome"] for b in obter_botoes()}


def iniciar_base_dados():
    ligacao = obter_ligacao_base_dados()
    cursor = ligacao.cursor()

    # Tabela de cliques
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cliques (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            botao_id INTEGER,
            botao TEXT NOT NULL,
            sequencial INTEGER NOT NULL,
            data TEXT NOT NULL,   -- AAAA-MM-DD
            hora TEXT NOT NULL    -- HH:MM
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS indice_data ON cliques(data)")

    # Tabela de configuração dos botões (nomes editáveis no admin)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS botoes (
            id INTEGER PRIMARY KEY,
            nome TEXT NOT NULL
        )
    """)

    # Nomes por defeito (se ainda não existirem)
    for i in range(1, NUM_BOTOES + 1):
        cursor.execute(
            "INSERT OR IGNORE INTO botoes (id, nome) VALUES (?, ?)",
            (i, f"Botão {i}")
        )

    # Migração simples: garantir coluna botao_id (caso a BD seja antiga)
    cursor.execute("PRAGMA table_info(cliques)")
    colunas = [linha["name"] for linha in cursor.fetchall()]
    if "botao_id" not in colunas:
        cursor.execute("ALTER TABLE cliques ADD COLUMN botao_id INTEGER")

    # Preencher botao_id em registos antigos (quando possível)
    for i in range(1, NUM_BOTOES + 1):
        cursor.execute(
            "UPDATE cliques SET botao_id = ? WHERE botao_id IS NULL AND botao = ?",
            (i, f"Botão {i}")
        )

    ligacao.commit()
    ligacao.close()

@aplicacao.route("/")
def pagina_inicial():
    botoes = obter_botoes()
    return render_template("pagina_inicial.html", botoes=botoes)


@aplicacao.route("/clique", methods=["POST"])
def registar_clique():
    dados = request.get_json(silent=True) or {}
    try:
        botao_id = int(dados.get("botao_id"))
    except (TypeError, ValueError):
        botao_id = None

    mapa = obter_mapa_botoes()
    if not botao_id or botao_id not in mapa:
        return jsonify({"erro": "Botão inválido."}), 400

    nome_botao = mapa[botao_id]

    agora = datetime.now()
    data_texto = agora.strftime("%Y-%m-%d")
    hora_texto = agora.strftime("%H:%M")

    ligacao = obter_ligacao_base_dados()
    cursor = ligacao.cursor()

    # Sequencial diário: máximo do dia + 1
    cursor.execute(
        "SELECT COALESCE(MAX(sequencial), 0) AS maximo FROM cliques WHERE data = ?",
        (data_texto,)
    )
    maximo = cursor.fetchone()["maximo"]
    sequencial = maximo + 1

    cursor.execute(
        "INSERT INTO cliques(botao_id, botao, sequencial, data, hora) VALUES (?, ?, ?, ?, ?)",
        (botao_id, nome_botao, sequencial, data_texto, hora_texto)
    )
    ligacao.commit()

    # Quantas vezes este botão foi clicado HOJE (por id)
    cursor.execute(
        "SELECT COUNT(*) AS total FROM cliques WHERE data = ? AND botao_id = ?",
        (data_texto, botao_id)
    )
    total_botao_hoje = cursor.fetchone()["total"]

    ligacao.close()

    return jsonify({
        "botao_id": botao_id,
        "botao": nome_botao,
        "sequencial": sequencial,
        "data": data_texto,
        "hora": hora_texto,
        "total_botao_hoje": total_botao_hoje
    })

@aplicacao.route("/contagens_hoje", methods=["GET"])
def contagens_hoje():
    agora = datetime.now()
    data_texto = agora.strftime("%Y-%m-%d")

    botoes = obter_botoes()

    ligacao = obter_ligacao_base_dados()
    cursor = ligacao.cursor()

    contagens = {}
    for b in botoes:
        cursor.execute(
            "SELECT COUNT(*) AS total FROM cliques WHERE data = ? AND botao_id = ?",
            (data_texto, b["id"])
        )
        contagens[str(b["id"])] = cursor.fetchone()["total"]

    ligacao.close()

    return jsonify({
        "data": data_texto,
        "botoes": botoes,
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

    botoes = obter_botoes()
    contagens = {}
    for b in botoes:
        cursor.execute(
            "SELECT COUNT(*) AS total FROM cliques WHERE data = ? AND botao_id = ?",
            (data_texto, b["id"])
        )
        contagens[str(b["id"])] = cursor.fetchone()["total"]

    # Últimos 100 cliques (geral)
    cursor.execute("""
        SELECT botao, botao_id, sequencial, data, hora
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
        ultimos=ultimos,
        botoes=botoes
    )

@aplicacao.route("/admin/guardar_botoes", methods=["POST"])
def guardar_botoes():
    red = _exigir_admin()
    if red:
        return red

    nomes = request.form.getlist("nomes")

    ligacao = obter_ligacao_base_dados()
    cursor = ligacao.cursor()

    # Garante exactamente NUM_BOTOES nomes
    for i in range(1, NUM_BOTOES + 1):
        nome = (nomes[i-1] if i-1 < len(nomes) else f"Botão {i}").strip() or f"Botão {i}"
        cursor.execute("UPDATE botoes SET nome = ? WHERE id = ?", (nome, i))

    ligacao.commit()
    ligacao.close()

    return redirect(url_for("admin_painel"))


def _obter_resumo_e_cliques_do_dia(data_texto: str):
    ligacao = obter_ligacao_base_dados()
    cursor = ligacao.cursor()

    cursor.execute("SELECT COUNT(*) AS total FROM cliques WHERE data = ?", (data_texto,))
    total = cursor.fetchone()["total"]

    botoes = obter_botoes()
    contagens = {}
    for b in botoes:
        cursor.execute(
            "SELECT COUNT(*) AS total FROM cliques WHERE data = ? AND botao_id = ?",
            (data_texto, b["id"])
        )
        contagens[str(b["id"])] = cursor.fetchone()["total"]

    cursor.execute('''
        SELECT botao, botao_id, sequencial, data, hora
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
    botoes = obter_botoes()

    linhas = []
    linhas.append(f"Relatório de cliques — {data_texto}")
    linhas.append("")
    linhas.append(f"Total do dia: {total}")
    for b in botoes:
        linhas.append(f'{b["nome"]}: {contagens.get(str(b["id"]), 0)}')
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
    w.writerow(["data", "hora", "sequencial", "botao_id", "botao"])
    for r in registos:
        w.writerow([r["data"], r["hora"], r["sequencial"], r.get("botao_id"), r["botao"]])

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
