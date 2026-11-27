"""API do banco de dados do PizZap (só para a equipe: exige a CHAVE_API).

Cadastrar (POST, corpo em JSON):
    /api/banco/ingredientes       novo ingrediente  {"ingrediente": "...", "densidade": 0.5}
    /api/banco/medidas            nova medida caseira  {"medida_caseira": "...", "volume": 15}
    /api/banco/recheios           novo sabor, com os ingredientes (inclusive os cadastrados pela API) em gramas por cm² de pizza

Consultar (GET, abre direto no navegador ou pela página /api):

    /api/banco/medidas            MedidasCaseiras
    /api/banco/ingredientes       Ingredientes
    /api/banco/ingredientes/3     um ingrediente
    /api/banco/templates          TemplatesReceitas (modo de preparo de cada massa)
    /api/banco/recheios           sabores com os ingredientes (Recheios + RecheiosXIngredientes)
    /api/banco/recheios/1         um sabor
    /api/banco/receitas           últimas receitas geradas (Receitas_Geradas)
    /api/banco/receitas/1         uma receita: parâmetros do pedido e ingredientes usados (Receitas_Geradas + ReceitasXIngredientes)

Para corrigir ou apagar um registro, use o MySQL Workbench e reinicie o servidor. Precisa de USAR_MYSQL = True.
"""
import json

import pymysql
from flask import Blueprint, jsonify, request

import config
import dados
import models

api_banco = Blueprint("api_banco", __name__, url_prefix="/api/banco")


@api_banco.before_request
def _precisa_do_mysql():
    if not config.USAR_MYSQL:
        return jsonify(erro="A API do banco precisa do MySQL (USAR_MYSQL = True no config.py)."), 503


def _numero(valor):
    """DECIMAL do MySQL vira número comum no JSON."""
    return float(valor) if valor is not None else None


@api_banco.get("/medidas")
def medidas():
    linhas = models._consultar("SELECT id, medida_caseira, volume FROM MedidasCaseiras ORDER BY volume DESC")
    itens = [{"id": m["id"], "medida_caseira": m["medida_caseira"], "volume_ml": _numero(m["volume"])}
            for m in linhas]
    return jsonify(total=len(itens), itens=itens)


@api_banco.get("/ingredientes")
def ingredientes():
    linhas = models._consultar("SELECT id, ingrediente, densidade FROM Ingredientes ORDER BY id")
    itens = [{"id": i["id"], "ingrediente": i["ingrediente"], "densidade_g_ml": _numero(i["densidade"])}
            for i in linhas]
    return jsonify(total=len(itens), itens=itens)


@api_banco.get("/ingredientes/<int:ingrediente_id>")
def ingrediente(ingrediente_id):
    linhas = models._consultar("SELECT id, ingrediente, densidade FROM Ingredientes WHERE id = %s", (ingrediente_id,))
    if not linhas:
        return jsonify(erro=f"Ingrediente {ingrediente_id} não encontrado."), 404
    i = linhas[0]
    return jsonify(id=i["id"], ingrediente=i["ingrediente"], densidade_g_ml=_numero(i["densidade"]))


@api_banco.get("/templates")
def templates():
    linhas = models._consultar("SELECT id, modo_de_preparo FROM TemplatesReceitas ORDER BY id")
    itens = [{
        "id": t["id"],
        "tipo_massa": dados.MASSAS.get(t["id"], {}).get("nome"),
        "modo_de_preparo": [p.strip() for p in t["modo_de_preparo"].splitlines() if p.strip()],
    } for t in linhas]
    return jsonify(total=len(itens), itens=itens)


def _recheios(filtro="", params=()):
    """Sabores com a lista de ingredientes (duas consultas)."""
    linhas = models._consultar(f"SELECT id, recheio, descricao, doce FROM Recheios{filtro} ORDER BY id", params)
    itens = models._consultar(
        "SELECT x.id_recheio, x.id_ingrediente, i.ingrediente, x.gramas_por_cm2 "
        "FROM RecheiosXIngredientes x JOIN Ingredientes i ON i.id = x.id_ingrediente ORDER BY x.id")
    return [{
        "id": r["id"], "recheio": r["recheio"], "descricao": r["descricao"], "doce": bool(r["doce"]),
        "ingredientes": [{"id_ingrediente": x["id_ingrediente"], "ingrediente": x["ingrediente"], "gramas_por_cm2": _numero(x["gramas_por_cm2"])}
                        for x in itens if x["id_recheio"] == r["id"]],
    } for r in linhas]


@api_banco.get("/recheios")
def recheios():
    itens = _recheios()
    return jsonify(total=len(itens), itens=itens)


@api_banco.get("/recheios/<int:recheio_id>")
def recheio(recheio_id):
    itens = _recheios(" WHERE id = %s", (recheio_id,))
    if not itens:
        return jsonify(erro=f"Sabor {recheio_id} não encontrado."), 404
    return jsonify(itens[0])


@api_banco.get("/receitas")
def receitas():
    """Últimas receitas geradas. ?limite=20 (de 1 a 200)."""
    limite = request.args.get("limite", "20")
    if not limite.isdigit() or not 1 <= int(limite) <= 200:
        return jsonify(erro="O parâmetro 'limite' deve ser um número de 1 a 200."), 400
    linhas = models._consultar(
        "SELECT id, `timestamp`, parametros FROM Receitas_Geradas ORDER BY id DESC LIMIT %s", (int(limite),))
    itens = []
    for r in linhas:
        pedido = json.loads(r["parametros"])
        itens.append({
            "id": r["id"],
            "timestamp": r["timestamp"].isoformat(),
            "unidade": pedido["unidade"],
            "total_pizzas": sum(p["quantidade"] for p in pedido["pizzas"]),
        })
    return jsonify(total=len(itens), itens=itens)


@api_banco.get("/receitas/<int:receita_id>")
def receita(receita_id):
    """Uma receita gerada: parâmetros do pedido e gramas de cada ingrediente usado."""
    linhas = models._consultar(
        "SELECT id, `timestamp`, parametros FROM Receitas_Geradas WHERE id = %s", (receita_id,))
    if not linhas:
        return jsonify(erro=f"Receita {receita_id} não encontrada."), 404
    usados = models._consultar(
        "SELECT x.id_ingrediente, i.ingrediente, x.quantidade_usada_gramas "
        "FROM ReceitasXIngredientes x JOIN Ingredientes i ON i.id = x.id_ingrediente "
        "WHERE x.id_receita_gerada = %s ORDER BY x.id",
        (receita_id,),
    )
    return jsonify(
        id=linhas[0]["id"],
        timestamp=linhas[0]["timestamp"].isoformat(),
        parametros=json.loads(linhas[0]["parametros"]),
        ingredientes_usados=[{"id_ingrediente": u["id_ingrediente"], "ingrediente": u["ingrediente"], "gramas": _numero(u["quantidade_usada_gramas"])} for u in usados],
    )


# ================================================================ cadastros
def _corpo_json():
    corpo = request.get_json(silent=True)
    if not isinstance(corpo, dict):
        return None, (jsonify(erro="Envie os dados em JSON, ex.: {\"ingrediente\": \"Atum\"}."), 400)
    return corpo, None


def _texto(valor, maximo):
    """Texto obrigatório de 1 a `maximo` caracteres (ou None se inválido)."""
    if isinstance(valor, str) and 1 <= len(valor.strip()) <= maximo:
        return valor.strip()
    return None


def _positivo(valor, maximo):
    """Número maior que zero e até `maximo` (ou None se inválido)."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not 0 < valor <= maximo:
        return None
    return valor


def _inserir(sql, valores, tabela):
    """INSERT simples; devolve o id novo ou a resposta de erro."""
    con = models.conectar()
    try:
        with con.cursor() as cur:
            cur.execute(sql, valores)
            novo_id = cur.lastrowid
        con.commit()
        return novo_id, None
    except pymysql.err.IntegrityError:
        con.rollback()
        return None, (jsonify(erro=f"Já existe um registro com esse nome em {tabela}."), 409)
    finally:
        con.close()


@api_banco.post("/ingredientes")
def novo_ingrediente():
    """Cadastra um ingrediente. Densidade (g/ml) é opcional: sem ela, fica só em gramas."""
    corpo, erro = _corpo_json()
    if erro:
        return erro
    campos = {}
    nome = _texto(corpo.get("ingrediente"), 80)
    if nome is None:
        campos["ingrediente"] = "Informe o nome (até 80 caracteres)."
    densidade = corpo.get("densidade")
    if densidade is not None and _positivo(densidade, 99.999) is None:
        campos["densidade"] = "Informe um número maior que 0 (g/ml) ou null."
    if campos:
        return jsonify(erro="Dados inválidos.", campos=campos), 400

    novo_id, erro = _inserir("INSERT INTO Ingredientes (ingrediente, densidade) VALUES (%s, %s)", (nome, densidade), "Ingredientes")
    if erro:
        return erro
    models.limpar_cache()  # vale na hora, sem reiniciar
    return jsonify(id=novo_id, ingrediente=nome, densidade_g_ml=densidade), 201


@api_banco.post("/medidas")
def nova_medida():
    """Cadastra uma medida caseira. Ela passa a ser usada na conversão das receitas."""
    corpo, erro = _corpo_json()
    if erro:
        return erro
    campos = {}
    nome = _texto(corpo.get("medida_caseira"), 40)
    if nome is None:
        campos["medida_caseira"] = "Informe o nome (até 40 caracteres)."
    volume = _positivo(corpo.get("volume"), 9999.99)
    if volume is None:
        campos["volume"] = "Informe o volume em ml (número maior que 0)."
    if campos:
        return jsonify(erro="Dados inválidos.", campos=campos), 400

    novo_id, erro = _inserir("INSERT INTO MedidasCaseiras (medida_caseira, volume) VALUES (%s, %s)", (nome, volume), "MedidasCaseiras")
    if erro:
        return erro
    models.limpar_cache()
    return jsonify(id=novo_id, medida_caseira=nome, volume_ml=float(volume)), 201


@api_banco.post("/recheios")
def novo_recheio():
    """Cadastra um sabor e os ingredientes dele, numa única transação.

    {"recheio": "Atum", "descricao": "...", "doce": false, "ingredientes": [{"id_ingrediente": 9, "gramas_por_cm2": 0.08}, ...]}
    """
    corpo, erro = _corpo_json()
    if erro:
        return erro
    campos = {}
    nome = _texto(corpo.get("recheio"), 60)
    if nome is None:
        campos["recheio"] = "Informe o nome do sabor (até 60 caracteres)."
    descricao = _texto(corpo.get("descricao"), 255)
    if descricao is None:
        campos["descricao"] = "Informe uma descrição curta (até 255 caracteres)."
    doce = corpo.get("doce", False)
    if not isinstance(doce, bool):
        campos["doce"] = "Use true ou false."

    itens = corpo.get("ingredientes")
    if not isinstance(itens, list) or not itens:
        campos["ingredientes"] = "Informe a lista de ingredientes (pelo menos um)."
        itens = []
    vistos = set()
    for n, item in enumerate(itens):
        ing = item.get("id_ingrediente") if isinstance(item, dict) else None
        if isinstance(ing, bool) or not isinstance(ing, int) or ing < 1:
            campos[f"ingredientes[{n}].id_ingrediente"] = "Informe o id do ingrediente (veja /api/banco/ingredientes)."
        elif ing in vistos:
            campos[f"ingredientes[{n}].id_ingrediente"] = "Ingrediente repetido."
        vistos.add(ing)
        gramas = item.get("gramas_por_cm2") if isinstance(item, dict) else None
        if _positivo(gramas, 999.9999) is None:
            campos[f"ingredientes[{n}].gramas_por_cm2"] = "Informe os gramas por cm² de pizza (maior que 0, ex.: 0.08)."
    if campos:
        return jsonify(erro="Dados inválidos.", campos=campos), 400

    con = models.conectar()
    try:
        with con.cursor() as cur:
            cur.execute("INSERT INTO Recheios (recheio, descricao, doce) VALUES (%s, %s, %s)", (nome, descricao, doce))
            novo_id = cur.lastrowid
            cur.executemany(
                "INSERT INTO RecheiosXIngredientes (id_recheio, id_ingrediente, gramas_por_cm2) VALUES (%s, %s, %s)",
                [(novo_id, i["id_ingrediente"], i["gramas_por_cm2"]) for i in itens])
        con.commit()  # sabor e ingredientes entram juntos, ou nada entra
    except pymysql.err.IntegrityError as e:
        con.rollback()
        if e.args[0] == 1452:  # chave estrangeira: ingrediente não existe
            return jsonify(erro="Algum id_ingrediente não existe. Confira em /api/banco/ingredientes."), 400
        return jsonify(erro="Já existe um sabor com esse nome."), 409
    finally:
        con.close()
    models.limpar_cache()  # o sabor já aparece no formulário, sem reiniciar
    return jsonify(_recheios(" WHERE id = %s", (novo_id,))[0]), 201
