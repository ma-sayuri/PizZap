"""Testes da API do banco (/api/banco): consultas às tabelas.

Usam o MySQL do config.py e são pulados (skipped) se ele não estiver acessível.
Rodar:  python -m pytest tests/test_api_banco.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config  # noqa: E402
import models  # noqa: E402
from app import app, limiter  # noqa: E402

PEDIDO = {"unidade": "gramas", "pizzas": [
    {"quantidade": 2, "diametro_cm": 35, "tipo_massa_id": 1, "recheio_ids": [1, 2]}]}


@pytest.fixture()
def banco(monkeypatch):
    monkeypatch.setattr(config, "USAR_MYSQL", True)
    monkeypatch.setattr(config, "CHAVE_API", "chave-de-teste")
    models.limpar_cache()
    try:
        models.catalogo()
    except models.ErroBanco as e:
        pytest.skip(f"MySQL indisponível: {e}")
    limiter.reset()
    cliente = app.test_client()
    cliente.environ_base["HTTP_X_CHAVE_API"] = "chave-de-teste"
    yield cliente
    models.aguardar_gravacoes()
    con = models.conectar()  # apaga o que os testes cadastraram
    with con.cursor() as cur:
        cur.execute("DELETE FROM Recheios WHERE recheio LIKE 'TESTE%%'")  # antes dos ingredientes (FK)
        cur.execute("DELETE FROM Ingredientes WHERE ingrediente LIKE 'TESTE%%'")
        cur.execute("DELETE FROM MedidasCaseiras WHERE medida_caseira LIKE 'TESTE%%'")
    con.commit()
    con.close()
    models._receitas.clear()
    models.limpar_cache()


def test_medidas(banco):
    d = banco.get("/api/banco/medidas").get_json()
    assert d["total"] == 3
    assert d["itens"][0] == {"id": 1, "medida_caseira": "xícara de chá", "volume_ml": 200.0}


def test_ingredientes(banco):
    d = banco.get("/api/banco/ingredientes").get_json()
    assert d["total"] == len(d["itens"]) >= 39
    assert banco.get("/api/banco/ingredientes/3").get_json() == {"id": 3, "ingrediente": "Água", "densidade_g_ml": 1.0}
    assert banco.get("/api/banco/ingredientes/16").get_json()["densidade_g_ml"] is None
    assert banco.get("/api/banco/ingredientes/99999").status_code == 404


def test_templates(banco):
    itens = banco.get("/api/banco/templates").get_json()["itens"]
    napolitana = next(t for t in itens if t["id"] == 2)
    assert napolitana["tipo_massa"] == "Napolitana tradicional"
    assert len(napolitana["modo_de_preparo"]) >= 5


def test_receitas_geradas(banco):
    receita = banco.post("/api/receitas", json=PEDIDO).get_json()
    assert models.aguardar_gravacoes()

    lista = banco.get("/api/banco/receitas?limite=5").get_json()["itens"]
    assert lista[0]["id"] == receita["id"]
    assert lista[0]["total_pizzas"] == 2 and lista[0]["unidade"] == "gramas"

    d = banco.get(f"/api/banco/receitas/{receita['id']}").get_json()
    assert d["parametros"] == PEDIDO
    assert {i["ingrediente"] for i in d["ingredientes_usados"]} == {i["ingrediente"] for i in receita["lista_de_compras"]}
    assert banco.get("/api/banco/receitas/99999999").status_code == 404


@pytest.mark.parametrize("limite", ["0", "abc", "500"])
def test_limite_invalido(banco, limite):
    assert banco.get(f"/api/banco/receitas?limite={limite}").status_code == 400


def test_cadastrar_ingrediente(banco):
    r = banco.post("/api/banco/ingredientes", json={"ingrediente": "TESTE Atum", "densidade": None})
    assert r.status_code == 201
    novo = r.get_json()
    assert novo["ingrediente"] == "TESTE Atum" and novo["densidade_g_ml"] is None
    assert banco.get(f"/api/banco/ingredientes/{novo['id']}").get_json()["ingrediente"] == "TESTE Atum"
    assert models.catalogo()["ingredientes"][novo["id"]]["nome"] == "TESTE Atum"  # já vale, sem reiniciar
    # nome repetido
    assert banco.post("/api/banco/ingredientes", json={"ingrediente": "TESTE Atum"}).status_code == 409


def test_cadastrar_medida_entra_na_conversao(banco):
    r = banco.post("/api/banco/medidas", json={"medida_caseira": "TESTE concha", "volume": 50})
    assert r.status_code == 201 and r.get_json()["volume_ml"] == 50.0
    medida = next(m for m in models.catalogo()["medidas"] if m["nome"] == "TESTE concha")
    assert medida["plural"] == "TESTE conchas"
    assert banco.post("/api/banco/medidas", json={"medida_caseira": "TESTE concha", "volume": 60}).status_code == 409


@pytest.mark.parametrize("url, corpo, campo", [
    ("/api/banco/ingredientes", {"ingrediente": "", "densidade": -1}, "ingrediente"),
    ("/api/banco/ingredientes", {"ingrediente": "TESTE X", "densidade": "leve"}, "densidade"),
    ("/api/banco/medidas", {"medida_caseira": "TESTE copo", "volume": 0}, "volume"),
    ("/api/banco/medidas", {"volume": 10}, "medida_caseira"),
])
def test_cadastro_invalido_indica_o_campo(banco, url, corpo, campo):
    r = banco.post(url, json=corpo)
    assert r.status_code == 400 and campo in r.get_json()["campos"]


def test_cadastro_sem_json(banco):
    assert banco.post("/api/banco/ingredientes", data="texto").status_code == 400


def test_sabores_vem_do_banco(banco):
    d = banco.get("/api/banco/recheios").get_json()
    assert d["total"] == 11
    margherita = banco.get("/api/banco/recheios/3").get_json()
    assert margherita["recheio"] == "Margherita (ETG)" and margherita["doce"] is False
    assert margherita["ingredientes"][0] == {"id_ingrediente": 37, "ingrediente": "Tomate pelado triturado",
                                            "gramas_por_cm2": 0.0728}
    assert banco.get("/api/banco/recheios/9999").status_code == 404


def test_sabor_novo_com_ingrediente_novo(banco):
    """Fluxo completo: cadastra um ingrediente, um sabor com ele e gera a receita."""
    atum = banco.post("/api/banco/ingredientes", json={"ingrediente": "TESTE Atum", "densidade": None}).get_json()
    r = banco.post("/api/banco/recheios", json={
        "recheio": "TESTE Atum", "descricao": "Molho, atum e cebola.", "ingredientes": [
            {"id_ingrediente": 9, "gramas_por_cm2": 0.08},
            {"id_ingrediente": atum["id"], "gramas_por_cm2": 0.1},
            {"id_ingrediente": 17, "gramas_por_cm2": 0.04}]})
    assert r.status_code == 201, r.get_json()
    sabor = r.get_json()
    assert [i["ingrediente"] for i in sabor["ingredientes"]] == ["Molho de tomate", "TESTE Atum", "Cebola fatiada"]
    assert sabor["doce"] is False

    # já aparece no formulário e entra no cálculo, sem reiniciar
    assert "TESTE Atum" in [s["nome"] for s in banco.get("/api/opcoes").get_json()["recheios"]]
    pedido = {"unidade": "gramas", "pizzas": [
        {"quantidade": 1, "diametro_cm": 35, "tipo_massa_id": 1, "recheio_ids": [sabor["id"]]}]}
    receita = banco.post("/api/receitas", json=pedido).get_json()
    atum_usado = next(i for i in receita["pizzas"][0]["cobertura"] if i["ingrediente"] == "TESTE Atum")
    assert atum_usado["por_pizza"]["gramas"] == pytest.approx(962.11 * 0.1, abs=0.1)
    assert models.aguardar_gravacoes()
    con = models.conectar()  # a receita de teste usa o ingrediente; apaga antes da limpeza
    with con.cursor() as cur:
        cur.execute("DELETE FROM Receitas_Geradas WHERE id = %s", (receita["id"],))
    con.commit()
    con.close()

    assert banco.post("/api/banco/recheios", json={
        "recheio": "TESTE Atum", "descricao": "x", "ingredientes": [{"id_ingrediente": 9, "gramas_por_cm2": 0.1}]
    }).status_code == 409


@pytest.mark.parametrize("corpo, campo", [
    ({"descricao": "x", "ingredientes": [{"id_ingrediente": 9, "gramas_por_cm2": 0.1}]}, "recheio"),
    ({"recheio": "TESTE Y", "descricao": "x", "ingredientes": []}, "ingredientes"),
    ({"recheio": "TESTE Y", "descricao": "x", "ingredientes": [{"id_ingrediente": 9}]}, "ingredientes[0].gramas_por_cm2"),
    ({"recheio": "TESTE Y", "descricao": "x", "doce": "sim", "ingredientes": [{"id_ingrediente": 9, "gramas_por_cm2": 0.1}]}, "doce"),
    ({"recheio": "TESTE Y", "descricao": "x", "ingredientes": [
        {"id_ingrediente": 9, "gramas_por_cm2": 0.1}, {"id_ingrediente": 9, "gramas_por_cm2": 0.1}]}, "ingredientes[1].id_ingrediente"),
])
def test_sabor_invalido_indica_o_campo(banco, corpo, campo):
    r = banco.post("/api/banco/recheios", json=corpo)
    assert r.status_code == 400 and campo in r.get_json()["campos"]


def test_sabor_com_ingrediente_inexistente(banco):
    r = banco.post("/api/banco/recheios", json={
        "recheio": "TESTE Z", "descricao": "x", "ingredientes": [{"id_ingrediente": 99999, "gramas_por_cm2": 0.1}]})
    assert r.status_code == 400
    assert not models._consultar("SELECT id FROM Recheios WHERE recheio = 'TESTE Z'")  # nada ficou pela metade


def test_apagar_nao_existe_na_api(banco):
    """Correções e exclusões são feitas no MySQL Workbench."""
    assert banco.delete("/api/banco/ingredientes/1").status_code == 405
