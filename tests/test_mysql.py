"""Testes da integração com o MySQL.

Usam o usuário e a senha do config.py e o banco criado por database/schema.sql.
Se o MySQL não estiver acessível, os testes são pulados (aparecem como "skipped").
Rodar:  python -m pytest tests/test_mysql.py -v
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config  # noqa: E402
import models  # noqa: E402
from app import app, limiter  # noqa: E402

PEDIDO = {"unidade": "ambas", "pizzas": [
    {"quantidade": 2, "diametro_cm": 35, "tipo_massa_id": 1, "recheio_ids": [1, 2]},
    {"quantidade": 1, "diametro_cm": 30, "tipo_massa_id": 2, "recheio_ids": [3, 11, 9]},
]}


@pytest.fixture()
def banco(monkeypatch):
    monkeypatch.setattr(config, "USAR_MYSQL", True)
    monkeypatch.setattr(models, "_catalogo_mysql", None)
    try:
        models.catalogo()
    except models.ErroBanco as e:
        pytest.skip(f"MySQL indisponível: {e}")
    monkeypatch.setattr(config, "CHAVE_API", "chave-de-teste")
    limiter.reset()
    cliente = app.test_client()
    cliente.environ_base["HTTP_X_CHAVE_API"] = "chave-de-teste"  # a API é só da equipe
    yield cliente
    models.aguardar_gravacoes()
    models._receitas.clear()


def test_tabelas_com_dados(banco):
    for tabela in ("MedidasCaseiras", "Ingredientes", "TemplatesReceitas", "Receitas_Geradas", "ReceitasXIngredientes"):
        assert models._consultar(f"SELECT COUNT(*) AS n FROM {tabela}")[0]["n"] >= 0
    cat = models.catalogo()
    assert [m["ml"] for m in cat["medidas"]] == [200, 10, 5]    # Anvisa
    assert cat["ingredientes"][3]["nome"] == "Água"             # acentos vindos do banco
    assert cat["ingredientes"][1]["densidade"] == 0.521         # farinha (FAO/INFOODS)
    assert cat["ingredientes"][16]["densidade"] is None         # calabresa sem densidade
    assert cat["massas"][1]["preparo"][0].startswith("Dissolva")


def test_banco_igual_ao_dados_py(banco):
    """O schema.sql e o dados.py têm os mesmos ids, nomes, densidades e modos de preparo."""
    import dados

    for m in models._consultar("SELECT * FROM MedidasCaseiras"):
        assert (m["medida_caseira"], float(m["volume"])) == (
            dados.MEDIDAS_CASEIRAS[m["id"]]["nome"], dados.MEDIDAS_CASEIRAS[m["id"]]["ml"])
    linhas = models._consultar("SELECT * FROM Ingredientes")
    assert len(linhas) == len(dados.INGREDIENTES)
    for i in linhas:
        d = dados.INGREDIENTES[i["id"]]
        assert i["ingrediente"] == d["nome"]
        assert (float(i["densidade"]) if i["densidade"] is not None else None) == d["densidade"]
    for t in models._consultar("SELECT * FROM TemplatesReceitas"):
        assert t["modo_de_preparo"].splitlines() == dados.MASSAS[t["id"]]["preparo"]
    # sabores: o banco é a fonte; dados.RECHEIOS é a cópia para rodar sem banco
    assert models.catalogo()["recheios"] == dados.RECHEIOS


def test_receita_e_registrada_com_os_parametros(banco):
    r = banco.post("/api/receitas", json=PEDIDO)
    assert r.status_code == 200
    receita = r.get_json()
    assert models.aguardar_gravacoes()  # a gravação roda em segundo plano

    reg = models._consultar("SELECT parametros FROM Receitas_Geradas WHERE id = %s", (receita["id"],))
    assert json.loads(reg[0]["parametros"]) == PEDIDO  # qtd, diâmetro, massa e sabores

    itens = models._consultar(
        "SELECT id_ingrediente, quantidade_usada_gramas FROM ReceitasXIngredientes "
        "WHERE id_receita_gerada = %s", (receita["id"],))
    esperado = {i["ingrediente_id"]: i["total"]["gramas"] for i in receita["lista_de_compras"]}
    assert {i["id_ingrediente"]: float(i["quantidade_usada_gramas"]) for i in itens} == pytest.approx(esperado, abs=0.01)


def test_pedido_invalido_nao_grava(banco):
    antes = models._consultar("SELECT COUNT(*) AS n FROM Receitas_Geradas")[0]["n"]
    assert banco.post("/api/receitas", json={"unidade": "x", "pizzas": []}).status_code == 400
    assert models._consultar("SELECT COUNT(*) AS n FROM Receitas_Geradas")[0]["n"] == antes


def test_receita_antiga_volta_do_banco(banco):
    receita = banco.post("/api/receitas", json=PEDIDO).get_json()
    assert models.aguardar_gravacoes()
    models._receitas.clear()  # simula o servidor reiniciado

    r = banco.get(f"/api/receitas/{receita['id']}")
    assert r.status_code == 200
    d = r.get_json()
    assert d["reconstruida"] is True                         # recalculada com os parâmetros gravados
    assert d["lista_de_compras"] == receita["lista_de_compras"]

    html = banco.get(f"/receita/{receita['id']}").get_data(as_text=True)
    assert "remontada a partir dos parâmetros" in html and "Marinara (ETG)" in html
    assert banco.get("/receita/99999999").status_code == 404


def test_gravacao_nao_bloqueia_a_resposta(banco, monkeypatch):
    """EAP 1.2.1/1.2.4: mesmo com o banco lento, a resposta não espera a gravação."""
    import time

    original = models._gravar_no_mysql

    def gravacao_lenta(lote):
        time.sleep(0.4)
        return original(lote)

    monkeypatch.setattr(models, "_gravar_no_mysql", gravacao_lenta)
    inicio = time.perf_counter()
    receita = banco.post("/api/receitas", json=PEDIDO).get_json()
    assert (time.perf_counter() - inicio) < 0.25           # respondeu antes de gravar
    assert banco.get(f"/receita/{receita['id']}").status_code == 200  # tela abre na hora
    assert models.aguardar_gravacoes()
    reg = models._consultar("SELECT id FROM Receitas_Geradas WHERE id = %s", (receita["id"],))
    assert len(reg) == 1                                    # e foi gravada depois


def test_insercao_em_receitas_geradas_abaixo_de_10ms(banco):
    """EAP 1.4.1: tempo da query de inserção em Receitas_Geradas < 10 ms."""
    import time
    from datetime import datetime

    con = models.conectar()
    try:
        with con.cursor() as cur:
            tempos = []
            for _ in range(20):
                inicio = time.perf_counter()
                cur.execute("INSERT INTO Receitas_Geradas (`timestamp`, parametros) VALUES (%s, %s)",
                            (datetime.now(), json.dumps(PEDIDO)))
                tempos.append((time.perf_counter() - inicio) * 1000)
        con.rollback()  # não deixa lixo no banco
    finally:
        con.close()
    assert sorted(tempos)[len(tempos) // 2] < 10  # mediana


def test_status_com_banco(banco):
    d = banco.get("/api/status").get_json()
    assert d["banco"] == "conectado"
    assert d["gravacao_receitas"]["falhas"] == 0


def test_senha_errada_mostra_erro_amigavel(monkeypatch):
    monkeypatch.setattr(config, "USAR_MYSQL", True)
    monkeypatch.setattr(models, "_catalogo_mysql", None)
    monkeypatch.setitem(config.MYSQL, "password", "senha-errada-de-proposito")
    limiter.reset()
    r = app.test_client().get("/receita/nova")
    assert r.status_code == 503
    assert "Banco de dados indisponível" in r.get_data(as_text=True)
