"""Configurações do PizZap

As credenciais (senha do MySQL, CHAVE_API e SECRET_KEY) ficam no arquivo .env, que NÃO vai para o GitHub (.gitignore).
"""
import os


def _carregar_env():
    """Lê o .env (linhas CHAVE=valor) sem precisar instalar nada."""
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(caminho):
        return
    with open(caminho, encoding="utf-8") as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                chave, valor = linha.split("=", 1)
                os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


_carregar_env()

# Chave secreta do Flask. Tem dois usos (app.py):
#   - assina o cookie de sessão que guarda o acesso à API depois de abrir /api?chave=...;
#   - é misturada ao IP antes do hash (o IP nunca é guardado em texto puro, LGPD).
SECRET_KEY = os.getenv("SECRET_KEY", "troque-esta-chave-secreta")

# True:  usa o MySQL (medidas, densidades e modos de preparo vêm do banco, e cada receita gerada é gravada nele).
# False: roda sem banco, só com dados.py; as receitas ficam na memória (somem quando o servidor reinicia).
USAR_MYSQL = True

MYSQL = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": "pizzap",
}

# Chave de acesso à API (tudo o que começa com /api). Sem ela, a API responde 404, como se não existisse.
# Para entrar pelo navegador: http://127.0.0.1:5000/api?chave=CHAVE_API
CHAVE_API = os.getenv("CHAVE_API", "troque-esta-chave-da-api")

# máximo de 100 requisições por minuto por IP
LIMITE_REQUISICOES = "100 per minute"

# Manter True
# "python iniciar.py --sem-limite", desliga o limite
LIMITE_ATIVO = True
