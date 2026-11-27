"""PizZap - servidor Flask (telas, API e rate limit).

Para rodar:  python app.py   e abrir http://127.0.0.1:5000
"""
import hashlib
import hmac
import logging
import os
import re
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler

from flask import Flask, abort, g, jsonify, redirect, render_template, request, session, url_for
from flask_limiter import Limiter
from werkzeug.exceptions import HTTPException

import config
import models
from api_banco import api_banco
from receita import (
    MAX_LINHAS, MAX_SABORES, TAMANHOS, UNIDADES,
    ErroValidacao, formatar_gramas, gerar_receita, validar_pedido,
)

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
app.json.ensure_ascii = False
app.json.sort_keys = False
app.jinja_env.filters["gramas"] = formatar_gramas
app.jinja_env.filters["data"] = lambda iso: datetime.fromisoformat(iso).strftime("%d/%m/%Y às %H:%M")


# ----------------------------------- EAP 1.5.3 - logs rotativos e métricas
# logs/pizzap.log guarda cada requisição (método, caminho, status e tempo).
# Ao passar de 1 MB, o arquivo vira pizzap.log.1 (são mantidos 5 arquivos).
PASTA_LOGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(PASTA_LOGS, exist_ok=True)
log = logging.getLogger("pizzap")
log.setLevel(logging.INFO)
if not log.handlers:
    arquivo = RotatingFileHandler(os.path.join(PASTA_LOGS, "pizzap.log"), maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    arquivo.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(arquivo)

INICIO = time.time()
METRICAS = {"requisicoes": 0, "erros_5xx": 0, "bloqueadas_429": 0, "tempo_total_ms": 0.0}


@app.before_request
def _marcar_inicio():
    g.inicio = time.perf_counter()


@app.after_request
def _registrar(resposta):
    if request.endpoint == "static" or not hasattr(g, "inicio"):
        return resposta
    ms = (time.perf_counter() - g.inicio) * 1000
    resposta.headers["X-Tempo-Resposta-ms"] = f"{ms:.1f}"
    METRICAS["requisicoes"] += 1
    METRICAS["tempo_total_ms"] += ms
    if resposta.status_code >= 500:
        METRICAS["erros_5xx"] += 1
    elif resposta.status_code == 429:
        METRICAS["bloqueadas_429"] += 1
    nivel = logging.WARNING if ms > 250 or resposta.status_code >= 500 else logging.INFO
    log.log(nivel, "%s %s %s %.1fms", request.method, request.path, resposta.status_code, ms)
    return resposta


# ---------------------------------------------- EAP 1.3.1 - Rate Limit
def ip_anonimizado():
    """O IP vira um código (hash), para não ser guardado em texto puro (LGPD)."""
    ip = (request.remote_addr or "") + config.SECRET_KEY
    return hashlib.sha256(ip.encode()).hexdigest()[:20]


# application_limits: os 100/minuto valem para o site todo, não por rota
limiter = Limiter(ip_anonimizado, app=app, application_limits=[config.LIMITE_REQUISICOES], storage_uri="memory://", enabled=getattr(config, "LIMITE_ATIVO", True))


@limiter.request_filter
def sem_limite():
    return request.endpoint == "static"


# --------------------------------------------- API só para a equipe
# Tudo o que começa com /api exige a CHAVE_API do config.py. Quem não tem a chave recebe 404, como se a API não existisse.
# O site (home, formulário e receita) não usa a API, então continua público.
def _chave_certa(valor):
    chave = getattr(config, "CHAVE_API", "")
    if not chave or not valor:
        return False
    return hmac.compare_digest(str(valor).encode("utf-8"), chave.encode("utf-8"))


@app.before_request
def _proteger_api():
    if request.path != "/api" and not request.path.startswith("/api/"):
        return None
    if _chave_certa(request.args.get("chave")):
        session["acesso_api"] = True
        session.permanent = False  # vale até fechar o navegador
    if session.get("acesso_api") or _chave_certa(request.headers.get("X-Chave-API")):
        return None
    abort(404)


@app.get("/api/sair")
def sair_da_api():
    session.pop("acesso_api", None)
    return redirect(url_for("index"))


# API do banco de dados (/api/banco/...), em api_banco.py
app.register_blueprint(api_banco)


# ---------------------------------------------------------------- apoio
def criar_receita(dados):
    cat = models.catalogo()
    pedido = validar_pedido(dados, cat)
    return models.salvar_receita(gerar_receita(pedido, cat))


def buscar(receita_id):
    """Receita pelo id; as antigas são recalculadas com os parâmetros gravados no banco."""
    def remontar(pedido):
        try:
            return gerar_receita(pedido, models.catalogo())
        except (KeyError, TypeError):  # massa ou sabor que saiu do dados.py
            return None

    return models.buscar_receita(receita_id, remontar)


def opcoes():
    """Listas usadas no formulário (e em GET /api/opcoes)."""
    cat = models.catalogo()
    return {
        "unidades": [{"id": k, "nome": v} for k, v in UNIDADES.items()],
        "tamanhos": [{"diametro_cm": d, "nome": n} for d, n in TAMANHOS.items()],
        "massas": [{"id": i, "nome": m["nome"], "descricao": m["descricao"]} for i, m in cat["massas"].items()],
        "recheios": [
            {"id": i, "nome": r["nome"], "descricao": r["descricao"], "doce": r["doce"]}
            for i, r in cat["recheios"].items()
        ],
        "limites": {"tipos_de_pizza": MAX_LINHAS, "sabores_por_pizza": MAX_SABORES},
    }


def pedido_do_formulario(form):
    """Lê os campos do formulário, que têm os mesmos nomes do JSON da API"""
    pizzas = {}
    for nome in form.keys():
        achado = re.fullmatch(r"pizzas\[(\d+)\]\[(\w+)\]", nome)
        if achado:
            indice, campo = int(achado.group(1)), achado.group(2)
            valor = form.getlist(nome) if campo == "recheio_ids" else form.get(nome, "").strip()
            pizzas.setdefault(indice, {"recheio_ids": []})[campo] = valor
    return {"unidade": form.get("unidade", "").strip(), "pizzas": [pizzas[i] for i in sorted(pizzas)]}


LINHA_PADRAO = {"quantidade": 1, "diametro_cm": 35, "tipo_massa_id": 1, "recheio_ids": []}


# ---------------------------------------------------------------- telas
@app.get("/")
def index():
    return render_template("index.html")


@app.route("/receita/nova", methods=["GET", "POST"])
def nova_receita():
    if request.method == "GET":
        return render_template("form.html", opcoes=opcoes(), linhas=[LINHA_PADRAO], unidade="ambas", erros={})

    dados = pedido_do_formulario(request.form)
    try:
        receita = criar_receita(dados)
    except ErroValidacao as e:
        linhas = dados["pizzas"] or [LINHA_PADRAO]
        return render_template("form.html", opcoes=opcoes(), linhas=linhas, unidade=dados["unidade"], erros=e.campos), 400
    return redirect(url_for("ver_receita", receita_id=receita["id"]), code=303)


@app.get("/receita/<int:receita_id>")
def ver_receita(receita_id):
    receita = buscar(receita_id)
    if receita is None:
        abort(404)
    return render_template("response.html", receita=receita)


@app.get("/api")
def pagina_api():
    """Página para testar a API pelo navegador (só com a chave)."""
    if request.args.get("chave"):  # tira a chave da barra de endereço
        return redirect(url_for("pagina_api"))
    return render_template("api.html")


# --------------------------------------------------- API (EAP 1.2.1)
@app.post("/api/receitas")
def api_criar():
    """Aceita JSON ou o próprio formulário (os nomes dos campos são os mesmos)."""
    if request.is_json:
        dados = request.get_json(silent=True)
    elif request.form:
        dados = pedido_do_formulario(request.form)
    else:
        dados = None
    if dados is None:
        return jsonify(erro="Envie um JSON válido (Content-Type: application/json) ou os campos do formulário."), 400
    try:
        return jsonify(criar_receita(dados)), 200
    except ErroValidacao as e:
        return jsonify(erro="Dados inválidos.", campos=e.campos), 400


@app.get("/api/receitas/<int:receita_id>")
def api_buscar(receita_id):
    receita = buscar(receita_id)
    if receita is None:
        return jsonify(erro="Receita não encontrada."), 404
    return jsonify(receita), 200


@app.get("/api/opcoes")
def api_opcoes():
    return jsonify(opcoes()), 200


@app.get("/api/status")
def api_status():
    """Monitoramento básico (EAP 1.5.3): servidor, desempenho, banco e máquina."""
    total = METRICAS["requisicoes"]
    estado = {
        "status": "ok",
        "no_ar_desde": datetime.fromtimestamp(INICIO).isoformat(timespec="seconds"),
        "uptime_segundos": int(time.time() - INICIO),
        "requisicoes": total,
        "tempo_medio_ms": round(METRICAS["tempo_total_ms"] / total, 1) if total else None,
        "erros_5xx": METRICAS["erros_5xx"],
        "bloqueadas_429": METRICAS["bloqueadas_429"],
        "banco": "desligado (USAR_MYSQL = False)",
    }
    if config.USAR_MYSQL:
        try:
            models._consultar("SELECT 1 AS ok")
            estado["banco"] = "conectado"
        except models.ErroBanco:
            estado["banco"], estado["status"] = "sem conexão", "degradado"
        estado["gravacao_receitas"] = models.estado_gravacao()
    try:  # CPU e memória
        import psutil

        processo = psutil.Process()
        estado["servidor"] = {
            "memoria_processo_mb": round(processo.memory_info().rss / 1_048_576, 1),
            "cpu_maquina_percentual": psutil.cpu_percent(interval=None),
            "memoria_maquina_percentual": psutil.virtual_memory().percent,
        }
    except ImportError:
        pass
    return jsonify(estado), 200 if estado["status"] == "ok" else 503


# ---------------------------------------------------------------- erros
MENSAGENS = {
    400: ("Requisição inválida", "Confira os dados enviados e tente de novo."),
    404: ("Página não encontrada", "O endereço não existe ou a receita não está mais disponível."),
    405: ("Método não permitido", "Esta ação não é aceita neste endereço."),
    429: ("Muitas requisições", "Você passou do limite de 100 requisições por minuto. Aguarde um pouco e tente de novo."),
    503: ("Banco de dados indisponível", "Não conseguimos falar com o MySQL. Confira se ele está ligado e os dados no .env."),
    500: ("Algo deu errado", "Não conseguimos gerar a receita agora. Tente novamente em instantes."),
}


@app.errorhandler(Exception)
def tratar_erro(e):
    if isinstance(e, models.ErroBanco):
        codigo = 503
        log.error(str(e))
    else:
        codigo = e.code if isinstance(e, HTTPException) and e.code in MENSAGENS else 500
    if codigo == 500:
        log.exception("Erro inesperado em %s %s", request.method, request.path)
    titulo, texto = MENSAGENS[codigo]
    if request.path.startswith("/api/"):
        return jsonify(erro=f"{titulo}. {texto}"), codigo
    return render_template("erro.html", codigo=codigo, titulo=titulo, texto=texto), codigo


if __name__ == "__main__":
    if config.USAR_MYSQL:
        try:
            models.catalogo()  # testa a conexão e carrega as tabelas de referência
            print("MySQL conectado: tabelas carregadas do banco.")
        except models.ErroBanco as e:
            print("ATENÇÃO:", e)
    else:
        print("Rodando sem banco (USAR_MYSQL = False): dados de dados.py, receitas na memória.")
    app.run(debug=True)