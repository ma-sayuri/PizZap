"""Sobe o PizZap com um único comando (EAP 1.5.1).

    python iniciar.py                   instala o que faltar, prepara o banco e liga o servidor
    python iniciar.py --recriar-banco   roda o database/schema.sql de novo (APAGA os dados)
    python iniciar.py --rede            aceita acesso de outras máquinas da rede
    python iniciar.py --porta 8000      usa outra porta (padrão: 5000)
    python iniciar.py --sem-limite      desliga o rate limit (só para o teste de carga)

Diferente de "python app.py" (modo de desenvolvimento), aqui o servidor é o Waitress, sem modo debug e atendendo várias pessoas ao mesmo tempo.
Ctrl+C desliga.
"""
import argparse
import importlib.util
import os
import socket
import subprocess
import sys
import time

PASTA = os.path.dirname(os.path.abspath(__file__))
PACOTES = {"flask": "Flask", "flask_limiter": "Flask-Limiter", "pymysql": "PyMySQL",
            "waitress": "waitress", "psutil": "psutil"}


def passo(texto):
    print(f"\n==> {texto}")


def instalar_dependencias():
    faltando = [nome for modulo, nome in PACOTES.items() if importlib.util.find_spec(modulo) is None]
    if not faltando:
        print("    Dependências já instaladas.")
        return
    print("    Instalando:", ", ".join(faltando))
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", os.path.join(PASTA, "requirements.txt")])


TOTAL_TABELAS = 7  # as 5 da EAP 1.4.1 + Recheios e RecheiosXIngredientes


def preparar_banco(recriar):
    import config

    if not config.USAR_MYSQL:
        print("    USAR_MYSQL = False: o sistema vai usar os dados de dados.py (sem banco).")
        return
    import pymysql
    from pymysql.constants import CLIENT

    dados_conexao = {k: v for k, v in config.MYSQL.items() if k != "database"}
    try:
        con = pymysql.connect(charset="utf8mb4", client_flag=CLIENT.MULTI_STATEMENTS, **dados_conexao)
    except pymysql.err.OperationalError as e:
        sys.exit(f"\n    ERRO: não conectou ao MySQL ({e}).\n"
                "    Confira se o MySQL está ligado e o usuário/senha no .env.")
    try:
        with con.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = %s",
                        (config.MYSQL["database"],))
            tabelas = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = %s "
                        "AND table_name = 'Receitas_Geradas' AND column_name = 'parametros'",
                        (config.MYSQL["database"],))
            atualizado = tabelas == TOTAL_TABELAS and cur.fetchone()[0] == 1
            if atualizado and not recriar:
                print(f"    Banco '{config.MYSQL['database']}' encontrado com as {TOTAL_TABELAS} tabelas.")
                return
            if tabelas and not recriar:  # banco criado com outra versão do schema.sql
                print(f"\n    O banco '{config.MYSQL['database']}' foi criado com outra versão do schema.sql.")
                resposta = input("    Recriar agora? Isso APAGA as receitas já registradas. Digite SIM: ")
                if resposta.strip().upper() != "SIM":
                    sys.exit("    Cancelado. Rode de novo quando quiser recriar o banco.")
            if config.MYSQL["database"] != "pizzap":
                sys.exit("    ERRO: o schema.sql cria o banco 'pizzap'. Use database = 'pizzap' no config.py.")
            print("    Criando o banco com database/schema.sql ...")
            with open(os.path.join(PASTA, "database", "schema.sql"), encoding="utf-8") as f:
                cur.execute(f.read())
            while cur.nextset():  # executa todos os comandos do arquivo
                pass
        con.commit()
        print(f"    Banco criado com as {TOTAL_TABELAS} tabelas e os dados iniciais.")
    finally:
        con.close()


def ip_da_rede():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "IP-DA-MAQUINA"


def main():
    parser = argparse.ArgumentParser(description="Sobe o PizZap com um único comando.")
    parser.add_argument("--porta", type=int, default=5000)
    parser.add_argument("--rede", action="store_true", help="aceita acesso de outras máquinas")
    parser.add_argument("--recriar-banco", action="store_true", help="roda o schema.sql de novo (apaga os dados)")
    parser.add_argument("--sem-limite", action="store_true", help="desliga o rate limit (teste de carga)")
    args = parser.parse_args()

    inicio = time.perf_counter()
    os.chdir(PASTA)
    sys.path.insert(0, PASTA)

    if sys.version_info < (3, 9):
        sys.exit("Use Python 3.9 ou mais novo.")

    passo("1/3 Conferindo as dependências")
    instalar_dependencias()

    passo("2/3 Preparando o banco de dados")
    if args.recriar_banco:
        resposta = input("    Isso APAGA todas as receitas registradas. Digite SIM para continuar: ")
        if resposta.strip().upper() != "SIM":
            sys.exit("    Cancelado.")
    preparar_banco(args.recriar_banco)

    passo("3/3 Ligando o servidor")
    import config

    if args.sem_limite:
        config.LIMITE_ATIVO = False
        print("    ATENÇÃO: rate limit DESLIGADO (use só durante o teste de carga).")

    from waitress import serve

    from app import app

    host = "0.0.0.0" if args.rede else "127.0.0.1"
    print(f"    Pronto em {time.perf_counter() - inicio:.1f} s.")
    print(f"    Abra no navegador: http://127.0.0.1:{args.porta}")
    if args.rede:
        print(f"    Outras máquinas da rede: http://{ip_da_rede()}:{args.porta}")
    print(f"    Status: http://127.0.0.1:{args.porta}/api/status  |  Logs: logs/pizzap.log")
    print("    Ctrl+C para desligar.\n")
    serve(app, host=host, port=args.porta, threads=16, connection_limit=1000, ident="PizZap")


if __name__ == "__main__":
    main()
