from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime, date
import os

# ---------------------- App & Mongo ----------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

# Usa a variável de ambiente MONGO_URI se existir; senão, usa sua URI do Atlas
MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://bicudo:bicudo25@cluster0.b9gbf2n.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
)
client = MongoClient(MONGO_URI)
db = client["buscativa_escolar"]  # database que o app utiliza
colecao_frequencia = db["frequencia"]
colecao_buscativa = db["registro"]

# índices úteis
try:
    colecao_buscativa.create_index([("dataRegistro", -1)])
    colecao_buscativa.create_index([("dedupeKey", 1), ("responsavel", 1)])
    colecao_frequencia.create_index([("dataRegistro", -1)])
except Exception:
    pass

# ---------------------- Helpers ----------------------
def round_pct(p):
    try:
        return int(round(p))
    except Exception:
        return 0

def iso_week_key(d: date) -> str:
    y, wk, _ = d.isocalendar()
    return f"{y}-W{wk:02d}"

def s(v):
    return (v or "").strip()

def to_str_id(doc):
    d = dict(doc)
    d["_id"] = str(d["_id"])
    return d

# ---------------------- Views ----------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/frequencia")
def frequencia_page():
    return render_template("frequencia.html")

@app.route("/buscativa")
def buscativa_page():
    return render_template("buscativa.html")

# ---------------------- API Frequência ----------------------
@app.route("/api/frequencia", methods=["POST"])
def registrar_frequencia():
    dados = request.get_json(force=True)

    aluno = s(dados.get("aluno"))
    serie = s(dados.get("serie"))
    presencas = int(dados.get("presencas", 0) or 0)
    aulas = int(dados.get("aulas", 0) or 0)
    dias_falta = dados.get("dias_falta") or []  # opcional: ["Terça","Quinta"]

    if not aluno or not serie or aulas <= 0 or presencas < 0 or presencas > aulas:
        return jsonify({"status": "error", "message": "Dados inválidos"}), 400

    freq = round_pct((presencas / aulas) * 100)

    doc = {
        "aluno": aluno,
        "serie": serie,
        "presencas": presencas,
        "aulas": aulas,
        "frequencia": freq,
        "dias_falta": dias_falta,
        "dataRegistro": datetime.now()
    }
    colecao_frequencia.insert_one(doc)

    # Criar Buscativa automática (<80%), com dedupe por semana ISO
    if freq < 80:
        hoje = date.today()
        faltas = max(0, aulas - presencas)
        resultado_txt = f"Frequência abaixo: {freq}% (faltas: {faltas}/{aulas})"
        if dias_falta:
            resultado_txt += f" — Dias: {', '.join(dias_falta)}"

        dedupe_key = f"{aluno.lower()}|{serie.lower()}|{iso_week_key(hoje)}"
        ja_existe = colecao_buscativa.find_one({
            "dedupeKey": dedupe_key,
            "responsavel": "Sistema Frequência"
        })

        if not ja_existe:
            alerta = {
                "aluno": aluno,
                "serie": serie,
                "dataFalta": hoje.isoformat(),      # YYYY-MM-DD
                "tipoContato": "Automático",
                "responsavel": "Sistema Frequência",
                "resultado": resultado_txt,
                "observacoes": f"Dias faltados: {', '.join(dias_falta)}" if dias_falta else "",
                # campos ricos para a Buscativa exibir bonito
                "freqNum": freq,
                "faltasNum": faltas,
                "aulasNum": aulas,
                "diasFalta": dias_falta,
                "dedupeKey": dedupe_key,
                "dataRegistro": datetime.now()
            }
            colecao_buscativa.insert_one(alerta)

    return jsonify({"status": "success", "frequencia": freq})

@app.route("/api/frequencia-listar", methods=["GET"])
def listar_frequencias():
    registros = list(colecao_frequencia.find().sort("dataRegistro", -1))
    saida = []
    for r in registros:
        r = to_str_id(r)
        if isinstance(r.get("dataRegistro"), datetime):
            r["dataRegistro"] = r["dataRegistro"].isoformat()
        saida.append(r)
    return jsonify(salida if (salida := saida) else [])

# ---------------------- API Buscativa ----------------------
@app.route("/api/buscativa", methods=["GET", "POST"])
def buscativa():
    if request.method == "POST":
        dados = request.get_json(force=True)

        aluno = s(dados.get("aluno"))
        serie = s(dados.get("serie"))
        dataFalta = s(dados.get("dataFalta")) or date.today().isoformat()
        tipoContato = s(dados.get("tipoContato") or "Registro")
        responsavel = s(dados.get("responsavel") or "Usuário")
        resultado = s(dados.get("resultado") or "Frequência abaixo de 80%")
        observacoes = s(dados.get("observacoes") or "")

        # extras opcionais
        freqNum = dados.get("freqNum")
        faltasNum = dados.get("faltasNum")
        aulasNum = dados.get("aulasNum")
        diasFalta = dados.get("diasFalta") or []

        # dedupe se for automático do sistema
        dedupeKey = None
        if responsavel == "Sistema Frequência":
            try:
                dt = date.fromisoformat(dataFalta)
            except Exception:
                dt = date.today()
            dedupeKey = f"{aluno.lower()}|{serie.lower()}|{iso_week_key(dt)}"
            ja_existe = colecao_buscativa.find_one({
                "dedupeKey": dedupeKey,
                "responsavel": "Sistema Frequência"
            })
            if ja_existe:
                return jsonify({"status": "ok", "message": "Já havia buscativa automática nesta semana"}), 200

        doc = {
            "aluno": aluno,
            "serie": serie,
            "dataFalta": dataFalta,
            "tipoContato": tipoContato,
            "responsavel": responsavel,
            "resultado": resultado,
            "observacoes": observacoes,
            "freqNum": freqNum,
            "faltasNum": faltasNum,
            "aulasNum": aulasNum,
            "diasFalta": diasFalta,
            "dedupeKey": dedupeKey,
            "dataRegistro": datetime.now()
        }
        colecao_buscativa.insert_one(doc)
        return jsonify({"status": "success"})

    # GET
    registros = list(colecao_buscativa.find().sort("dataRegistro", -1))
    saida = []
    for r in registros:
        r = to_str_id(r)
        if isinstance(r.get("dataRegistro"), datetime):
            r["dataRegistro"] = r["dataRegistro"].isoformat()
        saida.append(r)
    return jsonify(saida)

@app.route("/api/buscativa/<_id>", methods=["PUT"])
def atualizar_buscativa(_id):
    dados = request.get_json(force=True)
    try:
        res = colecao_buscativa.update_one(
            {"_id": ObjectId(_id)},
            {"$set": dados}
        )
        if res.matched_count == 0:
            return jsonify({"status":"error","message":"Não encontrado"}), 404
        doc = colecao_buscativa.find_one({"_id": ObjectId(_id)})
        return jsonify({"status":"success", **to_str_id(doc)})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)}), 400

@app.route("/api/buscativa/<_id>", methods=["DELETE"])
def deletar_buscativa(_id):
    try:
        res = colecao_buscativa.delete_one({"_id": ObjectId(_id)})
        if res.deleted_count == 0:
            return jsonify({"status":"error","message":"Não encontrado"}), 404
        return jsonify({"status":"success","deleted":_id})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)}), 400

@app.route("/api/limpar-alertas", methods=["DELETE"])
def limpar_alertas():
    resultado = colecao_buscativa.delete_many({
        "responsavel": "Sistema Frequência",
        "resultado": {"$regex": "Frequência abaixo", "$options": "i"}
    })
    return jsonify({"status": "ok", "removidos": resultado.deleted_count, "message": "Alertas removidos com sucesso."})

# ---------------------- Teste Mongo ----------------------
@app.route("/teste-mongo")
def teste_mongo():
    try:
        client.admin.command("ping")
        return jsonify({"status": "ok", "mensagem": "Conectado com sucesso ao MongoDB Atlas"})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)})

# ---------------------- Run ----------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
