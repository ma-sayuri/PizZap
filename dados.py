"""Dados do PizZap usados no cálculo (os "objetos de proporções" da EAP 1.2.2)

Como está organizado:
- Banco MySQL (database/schema.sql):
    ficam as medidas caseiras, ingredientes com a densidade, modo de preparo de cada massa e os SABORES (com os gramas de cada ingrediente). No config.py, o USAR_MYSQL = True, puxa tudo isso só do banco, e os sabores e ingredientes novos podem ser cadastrados pela API.
- Este arquivo dados.py:
    ficam os tamanhos, limites do pedido, proporções de cada massa, categoria dos ingredientes e plural das medidas, ligados pelo mesmo id.
    Por segurança, também guarda a cópia dos dados iniciais do banco, usada só para rodar sem banco (USAR_MYSQL = False no config.py), são os nomes, volumes e densidades em MEDIDAS_CASEIRAS e INGREDIENTES, e os sabores em RECHEIOS.

Fontes dos dados utilizados:
- Medidas caseiras: 
    Anvisa, Instrução Normativa nº 75/2020, Anexo VII.
- Densidades:
    FAO/INFOODS Density Database v2.0 (FAO, 2012).
- Massa "Napolitana tradicional" e sabores "Margherita (ETG)" e "Marinara (ETG)":
    Regulamento (UE) nº 97/2010, Anexo II (Pizza Napoletana ETG).
- Demais massas e sabores:
    receitas de referência da equipe (Gerente de projeto Victor possui curso de Pizzaiolo).
"""

# Tamanhos oferecidos no formulário: diâmetro em cm -> nome
TAMANHOS = {25: "Broto", 30: "Média", 35: "Grande", 40: "Gigante"}

# Limites do pedido
MAX_LINHAS = 10      # tipos de pizza (linhas) por pedido
MAX_QUANTIDADE = 50  # pizzas iguais numa linha
MAX_TOTAL = 100      # pizzas no pedido inteiro
MAX_SABORES = 4      # sabores numa mesma pizza

# MEDIDAS CASEIRAS (tabela MedidasCaseiras)
# id: nome, plural, volume em ml e menor fração usada no arredondamento
MEDIDAS_CASEIRAS = {
    1: {"nome": "xícara de chá", "plural": "xícaras de chá", "ml": 200, "fracao": 0.25},
    2: {"nome": "colher de sopa", "plural": "colheres de sopa", "ml": 10, "fracao": 0.5},
    3: {"nome": "colher de chá", "plural": "colheres de chá", "ml": 5, "fracao": 0.125},
}

# INGREDIENTES (tabela Ingredientes)
# id: nome, categoria e densidade em g/ml (FAO/INFOODS)
# densidade None = sem valor na base da FAO: o ingrediente fica só em gramas
INGREDIENTES = {
    1: {"nome": "Farinha de trigo tipo 1", "categoria": "massa", "densidade": 0.521},  # FAO: "Wheat, flour"
    2: {"nome": "Farinha de trigo integral", "categoria": "massa", "densidade": 0.55},  # FAO: "Wheat, flour, wholemeal"
    3: {"nome": "Água", "categoria": "massa", "densidade": 1.0},  # FAO: "Water"
    4: {"nome": "Sal refinado", "categoria": "massa", "densidade": 1.217},  # FAO: "Salt, table"
    5: {"nome": "Fermento biológico seco", "categoria": "massa", "densidade": 0.95},  # FAO: "Yeast"
    6: {"nome": "Açúcar", "categoria": "massa", "densidade": 0.88},  # FAO: "Sugar, white"
    7: {"nome": "Azeite de oliva", "categoria": "massa", "densidade": 0.918},  # FAO: "Oil, vegetable, olive"
    8: {"nome": "Mel", "categoria": "massa", "densidade": None},
    9: {"nome": "Molho de tomate", "categoria": "molho", "densidade": None},
    10: {"nome": "Leite condensado", "categoria": "molho", "densidade": None},
    11: {"nome": "Requeijão cremoso", "categoria": "molho", "densidade": None},
    12: {"nome": "Mussarela ralada", "categoria": "cobertura", "densidade": None},
    13: {"nome": "Provolone ralado", "categoria": "cobertura", "densidade": None},
    14: {"nome": "Parmesão ralado", "categoria": "cobertura", "densidade": None},
    15: {"nome": "Gorgonzola", "categoria": "cobertura", "densidade": None},
    16: {"nome": "Calabresa fatiada", "categoria": "cobertura", "densidade": None},
    17: {"nome": "Cebola fatiada", "categoria": "cobertura", "densidade": None},
    18: {"nome": "Tomate em rodelas", "categoria": "cobertura", "densidade": None},
    19: {"nome": "Manjericão fresco", "categoria": "cobertura", "densidade": None},
    20: {"nome": "Presunto em cubos", "categoria": "cobertura", "densidade": None},
    21: {"nome": "Ovo cozido picado", "categoria": "cobertura", "densidade": 0.6},  # FAO: "Egg, chicken, boiled/poached"
    22: {"nome": "Azeitona preta", "categoria": "cobertura", "densidade": None},
    23: {"nome": "Ervilha", "categoria": "cobertura", "densidade": 0.73},  # FAO: "Fresh green peas"
    24: {"nome": "Milho verde", "categoria": "cobertura", "densidade": 0.73},  # FAO: "Corn, sweet, boiled"
    25: {"nome": "Frango desfiado", "categoria": "cobertura", "densidade": None},
    26: {"nome": "Bacon em cubos", "categoria": "cobertura", "densidade": None},
    27: {"nome": "Champignon fatiado", "categoria": "cobertura", "densidade": None},
    28: {"nome": "Rúcula", "categoria": "cobertura", "densidade": None},
    29: {"nome": "Tomate seco", "categoria": "cobertura", "densidade": None},
    30: {"nome": "Orégano seco", "categoria": "cobertura", "densidade": None},
    31: {"nome": "Chocolate ao leite derretido", "categoria": "cobertura", "densidade": None},
    32: {"nome": "Morango picado", "categoria": "cobertura", "densidade": None},
    33: {"nome": "Banana em rodelas", "categoria": "cobertura", "densidade": None},
    34: {"nome": "Canela em pó", "categoria": "cobertura", "densidade": 0.56},  # FAO: "Cinnamon, powder"
    35: {"nome": "Granulado de chocolate", "categoria": "cobertura", "densidade": None},
    36: {"nome": "Fermento biológico fresco", "categoria": "massa", "densidade": None},
    37: {"nome": "Tomate pelado triturado", "categoria": "molho", "densidade": None},
    38: {"nome": "Mussarela fatiada", "categoria": "cobertura", "densidade": None},
    39: {"nome": "Alho fatiado", "categoria": "cobertura", "densidade": None},
}

# TIPOS DE MASSA (o modo de preparo está na tabela TemplatesReceitas)
# fator: gramas de massa por cm² de pizza (define a espessura)
# ingredientes: {id do ingrediente: porcentagem do padeiro}
MASSAS = {
    # Receita de referência da equipe
    1: {
        "nome": "Tradicional",
        "descricao": "Massa brasileira de pizzaria, macia e de espessura média.",
        "fator": 0.36,
        "ingredientes": {1: 100, 3: 60, 4: 2, 5: 1, 6: 2, 7: 3},
        "preparo": [
            "Dissolva o fermento e o açúcar em parte da água morna (cerca de 35 °C) e deixe descansar 10 minutos.",
            "Misture a farinha e o sal, junte a água com fermento, o restante da água e o azeite.",
            "Sove por 10 minutos, até a massa ficar lisa e elástica.",
            "Divida em bolinhas com o peso indicado para cada pizza.",
            "Deixe as bolinhas crescerem cobertas por 1 hora, até dobrarem de volume.",
        ],
    },
    # Fonte: Regulamento (UE) nº 97/2010, Anexo II
    2: {
        "nome": "Napolitana tradicional",
        "descricao": "Pizza Napoletana conforme a especificação oficial da União Europeia: massa fina no centro e borda alta.",
        "fator": 0.26,
        "ingredientes": {1: 100, 3: 55.56, 4: 2.92, 36: 0.167},
        "preparo": [
            "Coloque a água na masseira e dissolva o sal; junte 10% da farinha e o fermento e misture.",
            "Acrescente o resto da farinha aos poucos, até dar o ponto; essa etapa leva cerca de 10 minutos.",
            "Sove por 20 minutos em velocidade baixa, até a massa ficar lisa e não grudar.",
            "Primeira fermentação: deixe a massa 2 horas sobre a bancada, coberta com pano úmido (cerca de 25 °C).",
            "Divida em bolinhas com o peso indicado (a especificação aceita de 180 g a 250 g).",
            "Segunda fermentação: 4 a 6 horas em temperatura ambiente; use as bolinhas nas 6 horas seguintes.",
            "Abra com as pontas dos dedos, do centro para fora, sem rolo: centro com até 0,4 cm e borda de 1 a 2 cm.",
            "Pela especificação, asse em forno a lenha a cerca de 485 °C por 60 a 90 segundos.",
        ],
    },
    # Receita de referência da equipe
    3: {
        "nome": "Fina e crocante",
        "descricao": "Massa baixa e sequinha, que estala na mordida.",
        "fator": 0.24,
        "ingredientes": {1: 100, 3: 55, 4: 2, 5: 0.8, 7: 5},
        "preparo": [
            "Misture a farinha, o sal e o fermento.",
            "Junte a água e o azeite e sove por 8 minutos.",
            "Deixe descansar 40 minutos coberta.",
            "Divida em bolinhas com o peso indicado e abra bem fina com o rolo.",
            "Fure a massa com um garfo antes de montar, para não estufar.",
        ],
    },
    # Receita de referência da equipe
    4: {
        "nome": "Massa grossa",
        "descricao": "Massa alta e fofinha, assada em forma untada.",
        "fator": 0.55,
        "ingredientes": {1: 100, 3: 68, 4: 2, 5: 1.2, 6: 2, 7: 6},
        "preparo": [
            "Dissolva o fermento e o açúcar na água morna e deixe descansar 10 minutos.",
            "Junte a farinha, o sal e metade do azeite e sove por 10 minutos (a massa fica mais mole).",
            "Deixe crescer coberta por 1 hora.",
            "Unte a forma com o restante do azeite, acomode a massa e deixe crescer mais 30 minutos na forma.",
            "Monte e asse em forno a 230 °C por 15 a 18 minutos.",
        ],
    },
    # Receita de referência da equipe
    5: {
        "nome": "Integral",
        "descricao": "Mistura de farinha branca e integral, com toque de mel.",
        "fator": 0.36,
        "ingredientes": {1: 60, 2: 40, 3: 70, 4: 2, 5: 1, 8: 3, 7: 4},
        "preparo": [
            "Dissolva o fermento e o mel na água morna e deixe descansar 10 minutos.",
            "Misture as duas farinhas e o sal; junte a água com fermento e o azeite.",
            "Sove por 12 minutos (a massa fica levemente pegajosa).",
            "Divida em bolinhas com o peso indicado.",
            "Deixe crescer coberta por 1 hora e 30 minutos.",
        ],
    },
}

# ==================================================================
# CÓPIA PARA RODAR SEM BANCO (USAR_MYSQL = False)
# ==================================================================

# Sabores (tabelas Recheios e RecheiosXIngredientes)
# ingredientes: {id do ingrediente: gramas por cm² de pizza}
RECHEIOS = {
    1: {"nome": "Mussarela", "descricao": "Molho de tomate, mussarela e orégano.", "doce": False,
        "ingredientes": {9: 0.08, 12: 0.2, 30: 0.002}},
    2: {"nome": "Calabresa", "descricao": "Calabresa fatiada, cebola e mussarela.", "doce": False,
        "ingredientes": {9: 0.08, 12: 0.1, 16: 0.12, 17: 0.05, 30: 0.002}},
    3: {"nome": "Margherita (ETG)", "descricao": "Tomate pelado, mussarela fatiada, manjericão e azeite, conforme a especificação da Pizza Napoletana.", "doce": False,
        "ingredientes": {37: 0.0728, 38: 0.0935, 19: 0.005, 7: 0.0047}},
    4: {"nome": "Portuguesa", "descricao": "Presunto, ovo, cebola, ervilha e azeitona.", "doce": False,
        "ingredientes": {9: 0.08, 12: 0.14, 20: 0.08, 21: 0.06, 17: 0.04, 23: 0.03, 22: 0.03, 30: 0.002}},
    5: {"nome": "Frango com requeijão", "descricao": "Frango desfiado, requeijão cremoso e milho.", "doce": False,
        "ingredientes": {9: 0.08, 12: 0.1, 25: 0.12, 11: 0.08, 24: 0.04, 30: 0.002}},
    6: {"nome": "Quatro queijos", "descricao": "Mussarela, provolone, parmesão e gorgonzola.", "doce": False,
        "ingredientes": {9: 0.08, 12: 0.12, 13: 0.05, 14: 0.04, 15: 0.05}},
    7: {"nome": "Bacon com champignon", "descricao": "Bacon crocante, champignon e mussarela.", "doce": False,
        "ingredientes": {9: 0.08, 12: 0.14, 26: 0.07, 27: 0.07, 30: 0.002}},
    8: {"nome": "Rúcula com tomate seco", "descricao": "Mussarela, tomate seco e rúcula fresca.", "doce": False,
        "ingredientes": {9: 0.08, 12: 0.16, 29: 0.05, 28: 0.03, 14: 0.02}},
    9: {"nome": "Chocolate com morango", "descricao": "Chocolate ao leite derretido e morangos.", "doce": True,
        "ingredientes": {31: 0.15, 32: 0.1, 35: 0.01}},
    10: {"nome": "Banana com canela", "descricao": "Leite condensado, banana, mussarela e canela.", "doce": True,
        "ingredientes": {10: 0.08, 12: 0.08, 33: 0.15, 6: 0.01, 34: 0.002}},
    11: {"nome": "Marinara (ETG)", "descricao": "Tomate pelado, alho, orégano e azeite, sem queijo, conforme a especificação da Pizza Napoletana.", "doce": False,
        "ingredientes": {37: 0.0883, 39: 0.004, 30: 0.001, 7: 0.0047}},
}
