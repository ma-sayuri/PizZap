"""Regras de negócio do PizZap.

1. Validação do pedido            (EAP 1.2.1)
2. Calculadora de proporções      (EAP 1.2.2)
3. Conversora de medidas          (EAP 1.2.3)
4. Montagem da receita completa
"""
import math
import re
from itertools import combinations

from dados import MAX_LINHAS, MAX_QUANTIDADE, MAX_SABORES, MAX_TOTAL, TAMANHOS  # noqa: F401

UNIDADES = {
    "gramas": "Gramas (g)",
    "quilogramas": "Quilogramas (kg)",
    "caseira": "Medidas caseiras (xícaras e colheres)",
    "ambas": "Gramas + medidas caseiras",
}
ERRO_MAXIMO = 5.0  # % aceito na conversão para medida caseira

MONTAGEM = [
    "Abra a massa no diâmetro indicado, deixando a borda um pouco mais alta.",
    "Espalhe o molho (pizza salgada) ou o creme (pizza doce), deixando cerca de 1 cm livre na borda.",
    "Com mais de um sabor, divida a pizza em partes iguais e monte cada parte com o seu recheio.",
    "Distribua os queijos primeiro (se houver) e os demais ingredientes por cima.",
    "Asse em forno pré-aquecido na temperatura máxima (250 °C a 280 °C) por 8 a 12 minutos, até a borda dourar.",
    "Ingredientes frescos (manjericão, rúcula, frutas) entram depois de assar.",
]


# ============================================================ 1. validação
class ErroValidacao(Exception):
    """Guarda as mensagens de erro por campo, ex.: {"pizzas[0].quantidade": "..."}."""

    def __init__(self, campos):
        super().__init__("Dados inválidos")
        self.campos = campos


def _inteiro(valor):
    """Aceita 3, 3.0 e "3". Recusa texto, decimais, vazio e True/False."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    if isinstance(valor, int):
        return valor
    # não podem derrubar a validação (viraria erro 500 em vez de 400)
    if isinstance(valor, str) and re.fullmatch(r"-?[0-9]{1,18}", valor.strip()):
        return int(valor.strip())
    return None


def validar_pedido(dados, catalogo):
    """Confere o pedido e devolve uma versão limpa (só com números inteiros).

    Formato: {"unidade": "ambas", "pizzas": [{"quantidade": 2, "diametro_cm": 35, "tipo_massa_id": 1, "recheio_ids": [1, 2]}]}
    """
    if not isinstance(dados, dict):
        raise ErroValidacao({"geral": "Envie os dados no formato JSON."})

    erros = {}
    if dados.get("unidade") not in UNIDADES:
        erros["unidade"] = "Escolha a unidade de medida."

    pizzas = dados.get("pizzas")
    if not isinstance(pizzas, list) or not pizzas:
        erros["pizzas"] = "Informe os dados de pelo menos uma pizza."
        pizzas = []
    elif len(pizzas) > MAX_LINHAS:
        erros["pizzas"] = f"No máximo {MAX_LINHAS} tipos de pizza por receita."
        pizzas = []

    limpas = []
    for i, p in enumerate(pizzas):
        campo = f"pizzas[{i}]."
        if not isinstance(p, dict):
            erros[f"pizzas[{i}]"] = "Dados da pizza inválidos."
            continue

        qtd = _inteiro(p.get("quantidade"))
        if qtd is None or qtd < 1:
            erros[campo + "quantidade"] = "A quantidade deve ser um número inteiro maior que zero."
        elif qtd > MAX_QUANTIDADE:
            erros[campo + "quantidade"] = f"No máximo {MAX_QUANTIDADE} pizzas iguais."

        diametro = _inteiro(p.get("diametro_cm"))
        if diametro not in TAMANHOS:
            erros[campo + "diametro_cm"] = "Escolha um tamanho válido."

        massa = _inteiro(p.get("tipo_massa_id"))
        if massa not in catalogo["massas"]:
            erros[campo + "tipo_massa_id"] = "Escolha um tipo de massa válido."

        recheios = p.get("recheio_ids")
        ids = [_inteiro(r) for r in recheios] if isinstance(recheios, list) else []
        if not ids:
            erros[campo + "recheio_ids"] = "Escolha pelo menos um recheio."
        elif any(r not in catalogo["recheios"] for r in ids):
            erros[campo + "recheio_ids"] = "Recheio inválido."
        elif len(set(ids)) != len(ids):
            erros[campo + "recheio_ids"] = "O mesmo recheio foi escolhido mais de uma vez."
        elif len(ids) > MAX_SABORES:
            erros[campo + "recheio_ids"] = f"No máximo {MAX_SABORES} sabores por pizza."

        limpas.append({"quantidade": qtd, "diametro_cm": diametro, "tipo_massa_id": massa, "recheio_ids": ids})

    if not erros and sum(p["quantidade"] for p in limpas) > MAX_TOTAL:
        erros["pizzas"] = f"O total de pizzas não pode passar de {MAX_TOTAL}."
    if erros:
        raise ErroValidacao(erros)
    return {"unidade": dados["unidade"], "pizzas": limpas}


# ==================================================== 2. calculadora
def area_pizza(diametro_cm):
    return math.pi * (diametro_cm / 2) ** 2


def calcular_massa(diametro_cm, fator, proporcoes):
    """Gramas de cada ingrediente da massa de UMA pizza.

    Peso total = área x fator. A farinha vale 100% e o resto é proporcional a ela (porcentagem do padeiro). A soma dá exatamente o peso total.
    """
    peso_total = area_pizza(diametro_cm) * fator
    farinha = peso_total * 100 / sum(proporcoes.values())
    return {ing: farinha * pct / 100 for ing, pct in proporcoes.items()}


def calcular_cobertura(diametro_cm, sabores):
    """Gramas de cada ingrediente da cobertura de UMA pizza.

    sabores: lista de {ingrediente: gramas por cm²}. Com mais de um sabor, cada um cobre uma parte igual da pizza (meio a meio, terços...).
    """
    area_por_sabor = area_pizza(diametro_cm) / len(sabores)
    total = {}
    for sabor in sabores:
        for ing, g_cm2 in sabor.items():
            total[ing] = total.get(ing, 0) + g_cm2 * area_por_sabor
    return total


# ====================================================== 3. conversora
FRACOES = {0.125: "⅛", 0.25: "¼", 0.333: "⅓", 0.375: "⅜", 0.5: "½", 0.625: "⅝", 0.667: "⅔", 0.75: "¾", 0.875: "⅞"}


def texto_quantidade(q):
    """1.75 -> "1 ¾", 0.5 -> "½", 3 -> "3"."""
    inteiro = int(q + 1e-9)
    fracao = FRACOES.get(round(q - inteiro, 3), "")
    if inteiro and fracao:
        return f"{inteiro} {fracao}"
    return fracao or str(inteiro)


def _texto(partes):
    return " + ".join(
        f"{texto_quantidade(q)} {m['plural'] if q > 1 else m['nome']}" for q, m in partes
    )


def _passos(medida):
    """Frações aceitas: a da tabela e, nas medidas grandes (xícara), também terços."""
    return [medida["fracao"]] + ([1 / 3] if medida["ml"] >= 100 else [])


def _limite(medida):
    """Quantas unidades da medida ainda são práticas ("13 colheres" não é)."""
    if medida["ml"] >= 100:
        return math.inf
    return 4 if medida["ml"] >= 10 else 3


def _arredonda(valor_ml, medida, para_baixo=False):
    funcao = math.floor if para_baixo else round
    opcoes = [funcao(valor_ml / medida["ml"] / p + 1e-9) * p for p in _passos(medida)]
    return min(opcoes, key=lambda q: abs(q * medida["ml"] - valor_ml))


def para_medida_caseira(gramas, densidade, medidas):
    """Converte gramas em medidas caseiras (as da tabela MedidasCaseiras).

    Funciona com qualquer lista de medidas. Testa cada medida sozinha e as combinações de duas (a maior arredondada para baixo e a menor completando) e fica com a mais simples cujo erro é menor que 5%. Se nenhuma serve, fica com a de menor erro e marca como aproximada. Sem densidade, devolve None (o ingrediente fica em gramas).
    """
    if not densidade or gramas <= 0 or not medidas:
        return None
    ml = gramas / densidade
    medidas = sorted(medidas, key=lambda m: m["ml"], reverse=True)

    tentativas = [[(_arredonda(ml, m), m)] for m in medidas]  # mais simples primeiro
    for maior, menor in combinations(medidas, 2):
        q1 = min(_arredonda(ml, maior, para_baixo=True), _limite(maior))
        tentativas.append([(q1, maior), (_arredonda(ml - q1 * maior["ml"], menor), menor)])

    validas = []
    for partes in tentativas:
        if any(q <= 0 or q > _limite(m) for q, m in partes):
            continue
        erro = abs(sum(q * m["ml"] for q, m in partes) - ml) / ml * 100
        validas.append((erro, partes))

    if not validas:  # menos da metade da menor fração possível
        return {"texto": "1 pitada", "erro": None, "aproximado": True}

    boas = [v for v in validas if v[0] < ERRO_MAXIMO - 1e-6]
    erro, partes = boas[0] if boas else min(validas, key=lambda v: v[0])
    return {"texto": _texto(partes), "erro": round(erro, 2), "aproximado": not boas}


def formatar_gramas(g):
    if g >= 10:
        return f"{round(g)} g"
    return f"{g:.1f} g".replace(".", ",").replace(",0 g", " g")


def formatar_kg(g):
    return f"{g / 1000:.3f} kg".replace(".", ",")


def medida(gramas, ingrediente, unidade, medidas):
    """Quantidade pronta para exibir, conforme a unidade escolhida."""
    caseira = para_medida_caseira(gramas, ingrediente["densidade"], medidas)
    texto = formatar_kg(gramas) if unidade == "quilogramas" else formatar_gramas(gramas)
    extra = None
    if unidade == "caseira" and caseira:
        texto = caseira["texto"]
    elif unidade == "ambas" and caseira:
        extra = caseira["texto"]
    usa_caseira = unidade in ("caseira", "ambas") and caseira is not None
    return {
        "gramas": round(gramas, 2),
        "texto": texto,
        "caseira": extra,
        "aproximado": usa_caseira and caseira["aproximado"],
    }


# ============================================================ 4. receita
def gerar_receita(pedido, catalogo):
    """Monta a receita completa a partir de um pedido já validado."""
    ing = catalogo["ingredientes"]
    medidas = catalogo["medidas"]
    unidade = pedido["unidade"]

    def linhas(quantidades, qtd):
        return [
            {
                "ingrediente_id": i,
                "ingrediente": ing[i]["nome"],
                "por_pizza": medida(g, ing[i], unidade, medidas),
                "total": medida(g * qtd, ing[i], unidade, medidas),
            }
            for i, g in quantidades.items()
        ]

    pizzas, compras, preparos = [], {}, []
    for p in pedido["pizzas"]:
        massa = catalogo["massas"][p["tipo_massa_id"]]
        sabores = [catalogo["recheios"][r] for r in p["recheio_ids"]]
        qtd = p["quantidade"]

        g_massa = calcular_massa(p["diametro_cm"], massa["fator"], massa["ingredientes"])
        g_cobertura = calcular_cobertura(p["diametro_cm"], [s["ingredientes"] for s in sabores])

        pizzas.append({
            "quantidade": qtd,
            "diametro_cm": p["diametro_cm"],
            "tamanho": TAMANHOS[p["diametro_cm"]],
            "tipo_massa": massa["nome"],
            "recheios": [s["nome"] for s in sabores],
            "peso_massa_g": round(sum(g_massa.values())),
            "massa": linhas(g_massa, qtd),
            "cobertura": linhas(g_cobertura, qtd),
        })

        for i, g in list(g_massa.items()) + list(g_cobertura.items()):
            compras[i] = compras.get(i, 0) + g * qtd
        if massa["nome"] not in [m["tipo_massa"] for m in preparos]:
            preparos.append({"tipo_massa": massa["nome"], "passos": massa["preparo"]})

    ordem = {"massa": 0, "molho": 1, "cobertura": 2}
    lista_compras = [
        {"ingrediente_id": i, "ingrediente": ing[i]["nome"], "total": medida(g, ing[i], unidade, medidas)}
        for i, g in sorted(compras.items(), key=lambda item: ordem[ing[item[0]]["categoria"]])
    ]

    return {
        "unidade": unidade,
        "parametros": pedido,  # o pedido validado (vai para o banco)
        "resumo": {
            "total_pizzas": sum(p["quantidade"] for p in pizzas),
            "massa_total_g": sum(p["peso_massa_g"] * p["quantidade"] for p in pizzas),
        },
        "pizzas": pizzas,
        "lista_de_compras": lista_compras,
        "modo_de_preparo": preparos,
        "montagem": MONTAGEM,
    }