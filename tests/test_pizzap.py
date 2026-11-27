"""Testes do PizZap.  Rodar na pasta do projeto:  python -m pytest"""
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config  # noqa: E402
import dados  # noqa: E402
from app import app, limiter  # noqa: E402
from receita import (  # noqa: E402
    ErroValidacao, area_pizza, calcular_cobertura, calcular_massa,
    para_medida_caseira, texto_quantidade, validar_pedido,
)

CATALOGO = {"massas": dados.MASSAS, "recheios": dados.RECHEIOS}
MEDIDAS = sorted(dados.MEDIDAS_CASEIRAS.values(), key=lambda m: m["ml"], reverse=True)
TRADICIONAL = dados.MASSAS[1]["ingredientes"]


@pytest.fixture(autouse=True)
def zerar_rate_limit(monkeypatch):
    # estes testes conferem as regras sem banco
    monkeypatch.setattr(config, "USAR_MYSQL", False)
    limiter.reset()  # cada teste começa com o contador zerado
    yield


CHAVE = "chave-de-teste"


@pytest.fixture()
def client(monkeypatch):
    """Cliente da equipe: manda a CHAVE_API em todas as requisições."""
    monkeypatch.setattr(config, "CHAVE_API", CHAVE)
    cliente = app.test_client()
    cliente.environ_base["HTTP_X_CHAVE_API"] = CHAVE
    return cliente


@pytest.fixture()
def visitante(monkeypatch):
    """Cliente sem a chave (qualquer pessoa)."""
    monkeypatch.setattr(config, "CHAVE_API", CHAVE)
    return app.test_client()


def pedido(**extra):
    p = {"unidade": "ambas",
        "pizzas": [{"quantidade": 2, "diametro_cm": 35, "tipo_massa_id": 1, "recheio_ids": [1, 2]}]}
    p.update(extra)
    return p


# ======================================= Calculadora (EAP 1.2.2 / US-05)
def test_soma_da_massa_e_igual_ao_peso_da_bolinha():
    massa = calcular_massa(35, 0.36, TRADICIONAL)
    assert sum(massa.values()) == pytest.approx(area_pizza(35) * 0.36)


@pytest.mark.parametrize("diametro", [25, 30, 35, 40])
def test_proporcoes_se_mantem_em_qualquer_tamanho(diametro):
    massa = calcular_massa(diametro, 0.36, TRADICIONAL)
    farinha = massa[1]
    for ingrediente, pct in TRADICIONAL.items():
        assert massa[ingrediente] / farinha * 100 == pytest.approx(pct)


def test_napolitana_segue_a_etg():
    massa = dados.MASSAS[2]["ingredientes"]
    assert massa[3] / massa[1] * 1800 == pytest.approx(1000, abs=1)   # água
    assert 50 <= massa[4] / massa[1] * 1800 <= 55                     # sal
    assert massa[36] / massa[1] * 1800 == pytest.approx(3, abs=0.1)   # fermento fresco
    assert area_pizza(35) * dados.MASSAS[2]["fator"] == pytest.approx(250, abs=1)  # bolinha de 250 g


def test_meio_a_meio_divide_a_area():
    area = area_pizza(35)
    cobertura = calcular_cobertura(35, [{9: 0.08, 12: 0.20}, {9: 0.08, 16: 0.12}])
    assert cobertura[9] == pytest.approx(area * 0.08)       # molho na pizza inteira
    assert cobertura[12] == pytest.approx(area / 2 * 0.20)  # mussarela só numa metade
    assert cobertura[16] == pytest.approx(area / 2 * 0.12)  # calabresa só na outra


# ======================================= Conversora (EAP 1.2.3 / US-06)
@pytest.mark.parametrize("q, texto", [(1, "1"), (0.5, "½"), (1.75, "1 ¾"), (2 / 3, "⅔"), (0.125, "⅛")])
def test_texto_das_fracoes(q, texto):
    assert texto_quantidade(q) == texto


def test_medidas_oficiais_da_anvisa():
    assert [(m["nome"], m["ml"]) for m in MEDIDAS] == [
        ("xícara de chá", 200), ("colher de sopa", 10), ("colher de chá", 5)]


def test_uma_xicara_de_agua():
    assert para_medida_caseira(200, 1.0, MEDIDAS)["texto"] == "1 xícara de chá"


def test_combina_medidas_quando_precisa():
    r = para_medida_caseira(180, 1.0, MEDIDAS)
    assert r["texto"] == "¾ xícara de chá + 3 colheres de sopa"
    assert r["aproximado"] is False


def test_sem_densidade_fica_em_gramas():
    assert para_medida_caseira(100, None, MEDIDAS) is None


def test_quantidade_muito_pequena_vira_pitada():
    assert para_medida_caseira(0.2, 1.0, MEDIDAS)["texto"] == "1 pitada"


def test_nao_usa_muitas_colheres():
    assert para_medida_caseira(45, 1.0, MEDIDAS)["texto"] == "4 colheres de sopa + 1 colher de chá"
    assert "xícara" in para_medida_caseira(150, 1.0, MEDIDAS)["texto"]


@pytest.mark.parametrize("densidade", [0.521, 0.6, 0.88, 0.918, 1.0, 1.217])
@pytest.mark.parametrize("gramas", [12, 20, 37, 55, 80, 124, 206, 333, 412, 777, 1000, 2500])
def test_erro_abaixo_de_5_por_cento(gramas, densidade):
    if gramas / densidade < 10:
        pytest.skip("menos de 1 colher de sopa")
    r = para_medida_caseira(gramas, densidade, MEDIDAS)
    assert r["erro"] < 5 and r["aproximado"] is False, r


# ================================================ Validação (US-02/US-04)
def test_pedido_do_formulario_vira_numeros():
    p = pedido()
    p["pizzas"][0].update(quantidade="2", recheio_ids=["1", "2"])
    assert validar_pedido(p, CATALOGO)["pizzas"][0]["recheio_ids"] == [1, 2]


@pytest.mark.parametrize("campo, valor", [
    ("quantidade", 0), ("quantidade", -2), ("quantidade", "abc"), ("quantidade", ""), ("quantidade", 51),
    ("diametro_cm", 33), ("tipo_massa_id", 99),
    ("recheio_ids", []), ("recheio_ids", [1, 1]), ("recheio_ids", [1, 2, 3, 4, 5]), ("recheio_ids", [99]),
])
def test_campo_invalido_indica_o_campo(campo, valor):
    p = pedido()
    p["pizzas"][0][campo] = valor
    with pytest.raises(ErroValidacao) as erro:
        validar_pedido(p, CATALOGO)
    assert list(erro.value.campos) == [f"pizzas[0].{campo}"]


def test_unidade_e_lista_de_pizzas_obrigatorias():
    with pytest.raises(ErroValidacao) as erro:
        validar_pedido({"unidade": "", "pizzas": []}, CATALOGO)
    assert set(erro.value.campos) == {"unidade", "pizzas"}


@pytest.mark.parametrize("dados, campo", [
    (["não é objeto"], "geral"),
    ({"unidade": "gramas", "pizzas": [{"quantidade": 1, "diametro_cm": 35, "tipo_massa_id": 1, "recheio_ids": [1]}] * 11}, "pizzas"),
    ({"unidade": "gramas", "pizzas": [{"quantidade": 50, "diametro_cm": 35, "tipo_massa_id": 1, "recheio_ids": [1]}] * 3}, "pizzas"),
    ({"unidade": "gramas", "pizzas": ["texto"]}, "pizzas[0]"),
])
def test_limites_do_pedido(dados, campo):
    with pytest.raises(ErroValidacao) as erro:
        validar_pedido(dados, CATALOGO)
    assert campo in erro.value.campos


@pytest.mark.parametrize("valor, aceito", [(True, False), (3.0, True), (2.5, False), (" 4 ", True)])
def test_quantidade_aceita_so_inteiros(valor, aceito):
    p = pedido()
    p["pizzas"][0]["quantidade"] = valor
    if aceito:
        assert validar_pedido(p, CATALOGO)["pizzas"][0]["quantidade"] == int(float(str(valor).strip()))
    else:
        with pytest.raises(ErroValidacao):
            validar_pedido(p, CATALOGO)


# ====================================================== API (EAP 1.2.1)
def test_post_valido_retorna_200(client):
    r = client.post("/api/receitas", json=pedido())
    assert r.status_code == 200
    d = r.get_json()
    assert d["resumo"]["total_pizzas"] == 2
    assert d["pizzas"][0]["recheios"] == ["Mussarela", "Calabresa"]
    farinha = d["pizzas"][0]["massa"][0]
    assert farinha["total"]["gramas"] == pytest.approx(farinha["por_pizza"]["gramas"] * 2, abs=0.01)


def test_post_invalido_retorna_400_com_os_campos(client):
    r = client.post("/api/receitas", json={"unidade": "gramas", "pizzas": [{"quantidade": 0}]})
    assert r.status_code == 400
    assert "pizzas[0].quantidade" in r.get_json()["campos"]


def test_post_sem_json_retorna_400(client):
    assert client.post("/api/receitas", data="texto").status_code == 400


def test_receita_gerada_fica_registrada(client):
    """Critério da EAP 1.2.4: toda receita gerada é registrada, com os parâmetros do pedido."""
    d = client.post("/api/receitas", json=pedido()).get_json()
    assert d["id"] and d["criado_em"]
    assert d["parametros"] == {"unidade": "ambas", "pizzas": [
        {"quantidade": 2, "diametro_cm": 35, "tipo_massa_id": 1, "recheio_ids": [1, 2]}]}
    assert client.get(f"/api/receitas/{d['id']}").get_json() == d
    assert client.get("/api/receitas/99999").status_code == 404


@pytest.mark.parametrize("unidade, trecho", [("gramas", " g"), ("quilogramas", " kg"), ("caseira", "xícara")])
def test_unidades(client, unidade, trecho):
    farinha = client.post("/api/receitas", json=pedido(unidade=unidade)).get_json()["pizzas"][0]["massa"][0]
    assert trecho in farinha["por_pizza"]["texto"]


def test_resposta_em_menos_de_250_ms(client):
    p = pedido()
    p["pizzas"] = [{"quantidade": 5, "diametro_cm": 40, "tipo_massa_id": m, "recheio_ids": [1, 2, 3, 4]} for m in range(1, 6)]
    inicio = time.perf_counter()
    assert client.post("/api/receitas", json=p).status_code == 200
    assert (time.perf_counter() - inicio) * 1000 < 250


# ================================================= Rate limit (EAP 1.3.1)
def test_bloqueia_a_101a_requisicao(client):
    for _ in range(100):
        assert client.get("/api/opcoes").status_code == 200
    assert client.get("/api/opcoes").status_code == 429
    assert client.get("/").status_code == 429  # o limite vale para o site todo


def test_limite_e_por_ip(visitante):
    for _ in range(101):
        visitante.get("/", environ_base={"REMOTE_ADDR": "10.0.0.1"})
    assert visitante.get("/", environ_base={"REMOTE_ADDR": "10.0.0.1"}).status_code == 429
    assert visitante.get("/", environ_base={"REMOTE_ADDR": "10.0.0.2"}).status_code == 200


# ============================================ Telas (US-01, US-02, US-03)
def test_home(client):
    html = client.get("/").get_data(as_text=True)
    assert "quantidade certa de cada ingrediente" in html


def test_formulario_valido_mostra_a_receita(client):
    form = {"unidade": "ambas", "pizzas[0][quantidade]": "2", "pizzas[0][diametro_cm]": "35",
            "pizzas[0][tipo_massa_id]": "1", "pizzas[0][recheio_ids]": ["1", "2"]}
    r = client.post("/receita/nova", data=form)
    assert r.status_code == 303
    html = client.get(r.headers["Location"]).get_data(as_text=True)
    assert "2 pizzas na medida certa" in html
    assert "Lista de compras" in html and "Calabresa fatiada" in html


def test_formulario_com_erro_volta_com_a_mensagem(client):
    form = {"unidade": "ambas", "pizzas[0][quantidade]": "-2", "pizzas[0][diametro_cm]": "35",
            "pizzas[0][tipo_massa_id]": "1"}
    r = client.post("/receita/nova", data=form)
    html = r.get_data(as_text=True)
    assert r.status_code == 400
    assert "A quantidade deve ser um número inteiro maior que zero." in html
    assert "Escolha pelo menos um recheio." in html


def test_api_aceita_o_formulario_com_os_mesmos_nomes(client):
    """EAP 1.1.2: os nomes dos campos do formulário são os mesmos do payload da API."""
    form = {"unidade": "gramas", "pizzas[0][quantidade]": "1", "pizzas[0][diametro_cm]": "30",
            "pizzas[0][tipo_massa_id]": "3", "pizzas[0][recheio_ids]": ["3", "9"],
            "pizzas[5][quantidade]": "2", "pizzas[5][diametro_cm]": "25",
            "pizzas[5][tipo_massa_id]": "2", "pizzas[5][recheio_ids]": ["1"]}
    r = client.post("/api/receitas", data=form)
    assert r.status_code == 200
    assert r.get_json()["resumo"]["total_pizzas"] == 3
    r = client.post("/api/receitas", data={"unidade": "gramas", "pizzas[0][quantidade]": "0"})
    assert r.status_code == 400 and "pizzas[0].quantidade" in r.get_json()["campos"]


def test_formulario_html_usa_os_nomes_do_payload(client):
    html = client.get("/receita/nova").get_data(as_text=True)
    for nome in ("pizzas[0][quantidade]", "pizzas[0][diametro_cm]", "pizzas[0][tipo_massa_id]", "pizzas[0][recheio_ids]", 'name="unidade"'):
        assert nome in html


def test_status_e_tempo_de_resposta(client):
    r = client.post("/api/receitas", json=pedido())
    assert float(r.headers["X-Tempo-Resposta-ms"]) < 250
    d = client.get("/api/status").get_json()
    assert d["status"] == "ok" and d["requisicoes"] >= 1
    assert d["banco"].startswith("desligado")


def test_pagina_da_api(client):
    html = client.get("/api").get_data(as_text=True)
    assert "/api/banco/ingredientes" in html and "/api/banco/medidas" in html and "/api/receitas/1" in html


# ===================================== API só para a equipe (CHAVE_API)
@pytest.mark.parametrize("url", ["/api", "/api/receitas/1", "/api/opcoes", "/api/status", "/api/banco/ingredientes"])
def test_sem_chave_a_api_nao_existe(visitante, url):
    assert visitante.get(url).status_code == 404
    assert visitante.get(url, headers={"X-Chave-API": "chave-errada"}).status_code == 404


def test_post_sem_chave_e_recusado(visitante):
    assert visitante.post("/api/receitas", json=pedido()).status_code == 404
    assert visitante.post("/api/banco/ingredientes", json={"ingrediente": "X"}).status_code == 404


def test_entrar_pela_url_e_sair(visitante):
    r = visitante.get(f"/api?chave={CHAVE}")
    assert r.status_code == 302 and r.headers["Location"].endswith("/api")  # tira a chave da URL
    assert visitante.get("/api").status_code == 200            # a sessão lembra
    assert visitante.get("/api/opcoes").status_code == 200
    visitante.get("/api/sair")
    assert visitante.get("/api").status_code == 404


def test_chave_vazia_desliga_a_api(visitante, monkeypatch):
    monkeypatch.setattr(config, "CHAVE_API", "")
    assert visitante.get("/api?chave=").status_code == 404


def test_site_continua_publico(visitante):
    assert visitante.get("/").status_code == 200
    assert visitante.get("/receita/nova").status_code == 200
    assert 'href="/api"' not in visitante.get("/").get_data(as_text=True)  # sem link no menu


def test_api_do_banco_sem_mysql_avisa(client):
    r = client.get("/api/banco/ingredientes")
    assert r.status_code == 503 and "USAR_MYSQL" in r.get_json()["erro"]


def test_pagina_inexistente(client):
    assert client.get("/receita/99999").status_code == 404
