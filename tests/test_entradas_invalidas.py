"""Entradas estranhas devem dar erro 400 (dados) ou 404 (chave da API), nunca 500.

Não precisam do MySQL. Rodar na pasta do projeto:
    python -m pytest tests/test_entradas_invalidas.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config  # noqa: E402
import dados  # noqa: E402
from app import app, limiter  # noqa: E402
from receita import ErroValidacao, validar_pedido  # noqa: E402

CATALOGO = {"massas": dados.MASSAS, "recheios": dados.RECHEIOS}
CHAVE = "chave-de-teste"


@pytest.fixture(autouse=True)
def sem_banco(monkeypatch):
    monkeypatch.setattr(config, "USAR_MYSQL", False)
    monkeypatch.setattr(config, "CHAVE_API", CHAVE)
    limiter.reset()


def pedido(**pizza):
    linha = {"quantidade": 2, "diametro_cm": 35, "tipo_massa_id": 1, "recheio_ids": [1, 2]}
    linha.update(pizza)
    return {"unidade": "ambas", "pizzas": [linha]}


# ---------------------------------------------------- "números" que não são números
@pytest.mark.parametrize("valor", ["²", "--5", "-", "٣", "1e3", "9" * 30])
def test_quantidade_estranha_vira_erro_de_campo(valor):
    with pytest.raises(ErroValidacao) as erro:
        validar_pedido(pedido(quantidade=valor), CATALOGO)
    assert list(erro.value.campos) == ["pizzas[0].quantidade"]


@pytest.mark.parametrize("campo", ["diametro_cm", "tipo_massa_id"])
def test_numero_estranho_nos_outros_campos(campo):
    with pytest.raises(ErroValidacao) as erro:
        validar_pedido(pedido(**{campo: "²"}), CATALOGO)
    assert list(erro.value.campos) == [f"pizzas[0].{campo}"]


def test_recheio_estranho_vira_erro_de_campo():
    with pytest.raises(ErroValidacao) as erro:
        validar_pedido(pedido(recheio_ids=["²"]), CATALOGO)
    assert list(erro.value.campos) == ["pizzas[0].recheio_ids"]


def test_api_responde_400_e_nao_500():
    cliente = app.test_client()
    cliente.environ_base["HTTP_X_CHAVE_API"] = CHAVE
    resposta = cliente.post("/api/receitas", json=pedido(quantidade="²"))
    assert resposta.status_code == 400
    assert "pizzas[0].quantidade" in resposta.get_json()["campos"]


def test_formulario_responde_400_e_nao_500():
    dados_form = {"unidade": "gramas", "pizzas[0][quantidade]": "²", "pizzas[0][diametro_cm]": "35", "pizzas[0][tipo_massa_id]": "1", "pizzas[0][recheio_ids]": "1"}
    assert app.test_client().post("/receita/nova", data=dados_form).status_code == 400


# ---------------------------------------------------- chave da API com acento
@pytest.mark.parametrize("url", ["/api?chave=é", "/api/opcoes?chave=ç", "/api/status?chave=ã"])
def test_chave_com_acento_na_url_da_404(url):
    assert app.test_client().get(url).status_code == 404


def test_chave_com_acento_no_cabecalho_da_404():
    cliente = app.test_client()
    cliente.environ_base["HTTP_X_CHAVE_API"] = "chave-ç"
    assert cliente.get("/api/opcoes").status_code == 404


def test_chave_certa_continua_funcionando():
    cliente = app.test_client()
    cliente.environ_base["HTTP_X_CHAVE_API"] = CHAVE
    assert cliente.get("/api/opcoes").status_code == 200