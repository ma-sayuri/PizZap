"""Teste de carga do PizZap (EAP 1.5.3, RNF07) com o Locust.

Instalar (só na máquina que gera a carga):  pip install locust

1. Ligue o servidor SEM o rate limit (todas as requisições saem do mesmo IP):
    python iniciar.py --sem-limite --rede
2. Meça a BASE com 1 usuário durante 1 minuto:
    locust -f ferramentas/locustfile.py --host http://127.0.0.1:5000 --headless -u 1 -r 1 -t 1m --csv ferramentas/carga_base
3. Rode com 1.000 usuários simultâneos (entrando 50 por segundo) durante 5 minutos:
    locust -f ferramentas/locustfile.py --host http://127.0.0.1:5000 --headless -u 1000 -r 50 -t 5m --csv ferramentas/carga_1000
4. Compare a coluna "Average Response Time" de carga_base_stats.csv e carga_1000_stats.csv.
    Critério (RNF07): o tempo médio com 1.000 usuários pode ser no máximo 50% maior que a base
    (ex.: base 200 ms -> máximo 300 ms) e sem falhas.

O que cada usuário virtual faz (com pausa de 1 a 3 s entre as ações, como uma pessoa):
    - abre a home (peso 1) e o formulário (peso 1);
    - gera uma receita pela API e, em seguida, abre a tela dessa receita (peso 3).

A API só responde com a CHAVE_API. O Locust lê a chave do config.py sozinho e a envia no
cabeçalho X-Chave-API; se o config.py não for encontrado, use a variável de ambiente PIZZAP_CHAVE_API.

Dica: se der, gere a carga de OUTRA máquina da rede (troque 127.0.0.1 pelo IP do servidor),
para o próprio Locust não disputar CPU com o PizZap.
Sem --headless, o Locust abre um painel com gráficos em http://localhost:8089
"""
import os
import random
import sys

from locust import HttpUser, between, task

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # pasta do projeto
try:
    import config

    CHAVE_API = os.environ.get("PIZZAP_CHAVE_API") or getattr(config, "CHAVE_API", "")
except ImportError:
    CHAVE_API = os.environ.get("PIZZAP_CHAVE_API", "")


class Visitante(HttpUser):
    # cada usuário espera de 1 a 3 segundos entre uma ação e outra, como uma pessoa real
    wait_time = between(1, 3)

    def on_start(self):
        # vale para todas as requisições deste usuário (a home e o formulário ignoram o cabeçalho)
        self.client.headers.update({"X-Chave-API": CHAVE_API})

    @task(1)
    def home(self):
        self.client.get("/", name="GET /")

    @task(1)
    def formulario(self):
        self.client.get("/receita/nova", name="GET /receita/nova")

    @task(3)
    def gerar_receita(self):
        pedido = {
            "unidade": random.choice(["gramas", "quilogramas", "caseira", "ambas"]),
            "pizzas": [
                {
                    "quantidade": random.randint(1, 5),
                    "diametro_cm": random.choice([25, 30, 35, 40]),
                    "tipo_massa_id": random.randint(1, 5),
                    "recheio_ids": random.sample(range(1, 12), random.randint(1, 4)),
                }
                for _ in range(random.randint(1, 3))
            ],
        }
        receita_id = None
        with self.client.post("/api/receitas", json=pedido, name="POST /api/receitas", catch_response=True) as r:
            if r.status_code != 200:
                r.failure(f"HTTP {r.status_code}")
            else:
                try:
                    receita_id = r.json()["id"]
                except (ValueError, KeyError, TypeError):
                    r.failure("resposta sem o id da receita")

        # depois de gerar, o usuário real vê a tela da receita (todas as outras estatísticas agrupadas em um nome só)
        if receita_id is not None:
            self.client.get(f"/receita/{receita_id}", name="GET /receita/[id]")