"""Verificação automática do PizZap (EAP 1.5.3 - monitoramento de uptime).

A cada minuto chama /api/status e grava uma linha em ferramentas/monitoramento.csv:
    data/hora, se respondeu, tempo da chamada, uptime, requisições, tempo médio, erros 5xx, memória do processo e CPU/memória da máquina.

    python ferramentas/monitorar.py                 roda por 48 horas (padrão)
    python ferramentas/monitorar.py --horas 1       roda por 1 hora

O /api/status só responde com a CHAVE_API (sem ela a API devolve 404). O monitor lê a chave do config.py sozinho e a envia no cabeçalho X-Chave-API.

Uma "queda" é qualquer linha com respondeu = nao. Se o uptime diminuir de uma verificação para a outra, o servidor foi reiniciado (também conta como queda).
Ctrl+C para parar.
"""
import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

PASTA = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(PASTA))  # para importar o config.py da pasta do projeto
try:
    import config

    CHAVE_PADRAO = getattr(config, "CHAVE_API", "")
except ImportError:
    CHAVE_PADRAO = ""

ARQUIVO = os.path.join(PASTA, "monitoramento.csv")
COLUNAS = ["data_hora", "respondeu", "http", "tempo_chamada_ms", "uptime_segundos", "requisicoes", "tempo_medio_ms", "erros_5xx", "banco", "memoria_processo_mb", "cpu_maquina_pct", "memoria_maquina_pct"]


def _json_ou_vazio(resposta):
    try:
        return json.load(resposta)
    except ValueError:  # corpo vazio ou não é JSON
        return {}


def verificar(url, chave):
    linha = {"data_hora": datetime.now().isoformat(timespec="seconds"), "respondeu": "nao"}
    pedido = urllib.request.Request(url + "/api/status", headers={"X-Chave-API": chave})
    inicio = time.perf_counter()
    try:
        with urllib.request.urlopen(pedido, timeout=10) as r:
            d = _json_ou_vazio(r)
            linha.update(respondeu="sim", http=r.status)
    except urllib.error.HTTPError as e:
        # 503 = servidor no ar, mas com o banco fora; 404 = chave errada (não é queda, é erro de configuração)
        d = _json_ou_vazio(e)
        linha.update(respondeu="sim", http=e.code)
    except (urllib.error.URLError, OSError) as e:
        linha["http"] = f"erro: {e}"
        return linha
    finally:
        linha["tempo_chamada_ms"] = round((time.perf_counter() - inicio) * 1000, 1)
    servidor = d.get("servidor", {})
    linha.update(
        uptime_segundos=d.get("uptime_segundos"), requisicoes=d.get("requisicoes"),
        tempo_medio_ms=d.get("tempo_medio_ms"), erros_5xx=d.get("erros_5xx"), banco=d.get("banco"),
        memoria_processo_mb=servidor.get("memoria_processo_mb"),
        cpu_maquina_pct=servidor.get("cpu_maquina_percentual"),
        memoria_maquina_pct=servidor.get("memoria_maquina_percentual"),
    )
    return linha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:5000")
    parser.add_argument("--chave", default=CHAVE_PADRAO, help="chave da API (padrão: CHAVE_API do config.py)")
    parser.add_argument("--horas", type=float, default=48)
    parser.add_argument("--intervalo", type=int, default=60, help="segundos entre verificações")
    args = parser.parse_args()

    if not args.chave:
        sys.exit("ERRO: sem chave. Defina CHAVE_API no config.py ou use --chave.")

    novo = not os.path.exists(ARQUIVO)
    fim = time.time() + args.horas * 3600
    verificacoes = quedas = 0
    uptime_anterior = None
    print(f"Monitorando {args.url} por {args.horas} h. Gravando em {ARQUIVO}")
    with open(ARQUIVO, "a", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";")
        if novo:
            escritor.writeheader()
        try:
            while time.time() < fim:
                linha = verificar(args.url.rstrip("/"), args.chave)
                escritor.writerow(linha)
                f.flush()
                verificacoes += 1

                if linha.get("http") == 404:  # a chave não bateu: os dados seriam todos vazios
                    sys.exit("\nERRO: o servidor respondeu 404. A chave não confere com o CHAVE_API do "
                            "config.py do servidor (ou o servidor é de uma versão sem /api/status).")

                reiniciou = False
                uptime = linha.get("uptime_segundos")
                if uptime is not None and uptime_anterior is not None and uptime < uptime_anterior:
                    reiniciou = True
                if uptime is not None:
                    uptime_anterior = uptime

                if linha["respondeu"] == "nao" or reiniciou:
                    quedas += 1
                print(f"{linha['data_hora']}  respondeu={linha['respondeu']}  "
                    f"{linha.get('tempo_chamada_ms')} ms  quedas={quedas}" + ("  (servidor foi reiniciado)" if reiniciou else ""))
                time.sleep(args.intervalo)
        except KeyboardInterrupt:
            pass
    disponibilidade = 100 * (verificacoes - quedas) / verificacoes if verificacoes else 0
    print(f"Fim. Verificações: {verificacoes} | Quedas: {quedas} | Disponibilidade: {disponibilidade:.2f}%")


if __name__ == "__main__":
    main()
