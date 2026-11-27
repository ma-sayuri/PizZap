"""Acesso aos dados (EAP 1.4.1 - Schema Principal e 1.2.4 - Registro).

USAR_MYSQL = False  ->  tudo vem de dados.py e as receitas ficam na memória.
USAR_MYSQL = True   ->  lê e grava nas tabelas do MySQL (database/schema.sql):

    MedidasCaseiras        nome e volume das medidas
    Ingredientes           nome e densidade dos ingredientes
    TemplatesReceitas      modo de preparo de cada tipo de massa
    Recheios               sabores (nome, descrição, doce ou salgado)
    RecheiosXIngredientes  gramas por cm² de cada ingrediente de cada sabor
    Receitas_Geradas       uma linha por receita gerada: id, data/hora e os parâmetros do pedido (qtd, diâmetro, massa e sabores de cada pizza)
    ReceitasXIngredientes  gramas de cada ingrediente usado em cada receita

O que não tem tabela no banco (tamanhos, proporções das massas, categoria dos ingredientes, plural das medidas) vem de dados.py, ligado pelo mesmo id.
"""
import atexit
import json
import logging
import queue
import threading
import time
from collections import OrderedDict
from datetime import datetime

import config
import dados

# Receitas completas geradas desde que o servidor ligou, para mostrar a
# tela de resposta. Guarda as últimas 500; as mais antigas continuam no banco.
_receitas = OrderedDict()
_MAX_EM_MEMORIA = 500
_proximo_id = 1         # usado só no modo sem banco
_catalogo_mysql = None  # tabelas de referência lidas uma vez (cache)


# =================================================================== MySQL
class ErroBanco(Exception):
    pass


def conectar():
    import pymysql  # só é necessário com USAR_MYSQL = True

    try:
        return pymysql.connect(
            charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor, **config.MYSQL
        )
    except pymysql.err.OperationalError as e:
        raise ErroBanco(
            "Não foi possível conectar ao MySQL. Confira se ele está ligado e se "
            "usuário e senha estão certos no .env. Detalhe: " + str(e)
        ) from e


def _consultar(sql, parametros=()):
    con = conectar()
    try:
        with con.cursor() as cur:
            cur.execute(sql, parametros)
            return cur.fetchall()
    finally:
        con.close()


def _ler_catalogo_mysql():
    """Lê as tabelas de referência (uma consulta por tabela) e junta com dados.py."""
    medidas = {}
    for m in _consultar("SELECT id, medida_caseira, volume FROM MedidasCaseiras"):
        extra = dados.MEDIDAS_CASEIRAS.get(m["id"], {})
        medidas[m["id"]] = {
            "nome": m["medida_caseira"],
            "plural": extra.get("plural") or plural(m["medida_caseira"]),
            "ml": float(m["volume"]),
            "fracao": extra.get("fracao", 0.25),
        }

    ingredientes = {}
    for i in _consultar("SELECT id, ingrediente, densidade FROM Ingredientes"):
        extra = dados.INGREDIENTES.get(i["id"], {})
        ingredientes[i["id"]] = {
            "nome": i["ingrediente"],
            "categoria": extra.get("categoria", "cobertura"),
            "densidade": float(i["densidade"]) if i["densidade"] is not None else None,
        }

    massas = {k: dict(v) for k, v in dados.MASSAS.items()}
    for t in _consultar("SELECT id, modo_de_preparo FROM TemplatesReceitas"):
        if t["id"] in massas:
            massas[t["id"]]["preparo"] = [
                passo.strip() for passo in t["modo_de_preparo"].splitlines() if passo.strip()
            ]

    # sabores: Recheios + RecheiosXIngredientes (gramas por cm² de cada ingrediente)
    recheios = {
        r["id"]: {"nome": r["recheio"], "descricao": r["descricao"], "doce": bool(r["doce"]), "ingredientes": {}}
        for r in _consultar("SELECT id, recheio, descricao, doce FROM Recheios ORDER BY id")
    }
    for x in _consultar("SELECT id_recheio, id_ingrediente, gramas_por_cm2 FROM RecheiosXIngredientes ORDER BY id"):
        if x["id_recheio"] in recheios:
            recheios[x["id_recheio"]]["ingredientes"][x["id_ingrediente"]] = float(x["gramas_por_cm2"])
    recheios = {i: r for i, r in recheios.items() if r["ingredientes"]}  # sabor sem ingrediente fica de fora

    return {"medidas": medidas, "ingredientes": ingredientes, "massas": massas, "recheios": recheios}


def _conferir_schema():
    """Avisa se o banco foi criado com um schema.sql de outra versão."""
    try:
        ok = _consultar("SHOW COLUMNS FROM Receitas_Geradas LIKE 'parametros'")
        ok = ok and _consultar("SHOW TABLES LIKE 'RecheiosXIngredientes'")
    except ErroBanco:
        raise
    except Exception:  # tabela não existe
        ok = []
    if not ok:
        raise ErroBanco(
            "O banco 'pizzap' foi criado com outra versão do schema.sql. Rode "
            "'python iniciar.py --recriar-banco' ou execute database/schema.sql no Workbench."
        )


def plural(nome):
    """Plural simples para medidas cadastradas pela API: "concha" -> "conchas",
    "colher de sobremesa" -> "colheres de sobremesa" (muda só antes do "de")."""
    antes, sep, depois = nome.partition(" de ")
    palavras = []
    for p in antes.split():
        if p[-1] in "aeiouáéíóú":
            p += "s"
        elif p[-1] in "rz":
            p += "es"
        elif p.endswith("l"):
            p = p[:-1] + "is"
        palavras.append(p)
    return " ".join(palavras) + sep + depois


# ================================================================ catálogo
def limpar_cache():
    """Faz o catálogo ser lido de novo do banco (sem reiniciar o servidor)."""
    global _catalogo_mysql
    _catalogo_mysql = None


def catalogo():
    """Medidas, ingredientes, massas e recheios usados no cálculo."""
    global _catalogo_mysql
    if config.USAR_MYSQL:
        if _catalogo_mysql is None:
            _conferir_schema()
            _catalogo_mysql = _ler_catalogo_mysql()
        cat = _catalogo_mysql
    else:
        cat = {
            "medidas": dados.MEDIDAS_CASEIRAS,
            "ingredientes": dados.INGREDIENTES,
            "massas": dados.MASSAS,
            "recheios": dados.RECHEIOS,
        }
    # a conversora espera as medidas da maior para a menor
    medidas = sorted(cat["medidas"].values(), key=lambda m: m["ml"], reverse=True)
    return dict(cat, medidas=medidas)


# =============================================== registro (EAP 1.2.4)
# A gravação no MySQL roda numa thread separada (fila), para não atrasar a resposta ao usuário (restrição da EAP 1.2.1 e risco "escrita síncrona no MySQL" da matriz de riscos).
# O id da receita é reservado na hora, então a tela de resposta abre imediatamente com o mesmo id que vai para o banco.
log = logging.getLogger("pizzap")

_fila = queue.Queue()
_trava = threading.Lock()
_ultimo_id_mysql = None
_thread_gravacao = None
_estatisticas = {"gravadas": 0, "lotes": 0, "falhas": 0, "tempo_total_ms": 0.0, "ultimo_ms": None}


def _guardar_na_memoria(receita):
    _receitas[receita["id"]] = receita
    while len(_receitas) > _MAX_EM_MEMORIA:
        _receitas.popitem(last=False)


def _reservar_id():
    """Próximo id de Receitas_Geradas (consulta o banco só na primeira vez)."""
    global _ultimo_id_mysql
    with _trava:
        if _ultimo_id_mysql is None:
            _ultimo_id_mysql = int(_consultar("SELECT COALESCE(MAX(id), 0) AS n FROM Receitas_Geradas")[0]["n"])
        _ultimo_id_mysql += 1
        return _ultimo_id_mysql


def _gravar_no_mysql(lote):
    """Grava um lote de receitas (e os ingredientes usados) numa única transação."""
    inicio = time.perf_counter()
    con = conectar()
    try:
        with con.cursor() as cur:
            cur.executemany(
                "INSERT INTO Receitas_Geradas (id, `timestamp`, parametros) VALUES (%s, %s, %s)",
                [(r["id"], r["timestamp"], r["parametros"]) for r in lote],
            )
            cur.executemany(
                "INSERT INTO ReceitasXIngredientes "
                "(id_receita_gerada, id_ingrediente, quantidade_usada_gramas) VALUES (%s, %s, %s)",
                [(r["id"], ingrediente, gramas) for r in lote for ingrediente, gramas in r["itens"]],
            )
        con.commit()  # tudo entra junto ou nada entra
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return (time.perf_counter() - inicio) * 1000


TAMANHO_LOTE = 200  # com muitos acessos ao mesmo tempo, grava até 200 receitas de uma vez


def _gravador():
    """Thread que esvazia a fila: junta o que estiver esperando e grava em lote."""
    while True:
        lote = [_fila.get()]
        while len(lote) < TAMANHO_LOTE:
            try:
                lote.append(_fila.get_nowait())
            except queue.Empty:
                break
        try:
            for tentativa in (1, 2):
                try:
                    ms = _gravar_no_mysql(lote)
                    _estatisticas["gravadas"] += len(lote)
                    _estatisticas["lotes"] += 1
                    _estatisticas["tempo_total_ms"] += ms
                    _estatisticas["ultimo_ms"] = round(ms, 1)
                    log.info("%d receita(s) gravada(s) no MySQL em %.1f ms (ids %s a %s)",
                        len(lote), ms, lote[0]["id"], lote[-1]["id"])
                    break
                except Exception:  # noqa: BLE001
                    if tentativa == 2:
                        _estatisticas["falhas"] += len(lote)
                        log.exception("falha ao gravar as receitas %s a %s no MySQL", lote[0]["id"], lote[-1]["id"])
                    else:
                        time.sleep(0.5)
        finally:
            for _ in lote:
                _fila.task_done()


def _iniciar_gravador():
    global _thread_gravacao
    with _trava:
        if _thread_gravacao is None or not _thread_gravacao.is_alive():
            _thread_gravacao = threading.Thread(target=_gravador, name="gravador-mysql", daemon=True)
            _thread_gravacao.start()


def aguardar_gravacoes(timeout=10):
    """Espera a fila esvaziar (usado nos testes e ao desligar o servidor)."""
    limite = time.monotonic() + timeout
    while _fila.unfinished_tasks and time.monotonic() < limite:
        time.sleep(0.01)
    return _fila.unfinished_tasks == 0


atexit.register(aguardar_gravacoes)


def estado_gravacao():
    lotes = _estatisticas["lotes"]
    return {
        "pendentes": _fila.unfinished_tasks,
        "gravadas": _estatisticas["gravadas"],
        "falhas": _estatisticas["falhas"],
        "ultimo_lote_ms": _estatisticas["ultimo_ms"],
        "media_por_lote_ms": round(_estatisticas["tempo_total_ms"] / lotes, 1) if lotes else None,
    }


def salvar_receita(receita):
    """Registra a receita gerada e devolve a receita com id e data/hora.

    Com MySQL, a resposta volta na hora e a gravação acontece em segundo plano.
    """
    global _proximo_id
    agora = datetime.now().replace(microsecond=0).isoformat()

    if not config.USAR_MYSQL:
        with _trava:
            receita = dict(receita, id=_proximo_id, criado_em=agora)
            _proximo_id += 1
        _guardar_na_memoria(receita)
        return receita

    receita = dict(receita, id=_reservar_id(), criado_em=agora)
    _guardar_na_memoria(receita)
    _iniciar_gravador()
    # na fila vai o que o banco guarda: id, data/hora, parâmetros do pedido e gramas de cada ingrediente
    _fila.put({
        "id": receita["id"],
        "timestamp": datetime.fromisoformat(agora),
        "parametros": json.dumps(receita["parametros"], ensure_ascii=False),
        "itens": [(i["ingrediente_id"], round(i["total"]["gramas"], 2)) for i in receita["lista_de_compras"]],
    })
    return receita


def buscar_receita(receita_id, gerar):
    """Receita completa pelo id.

    Se foi gerada desde que o servidor ligou, vem da memória. Se não, é
    remontada com os parâmetros gravados no banco: gerar(pedido) refaz o
    cálculo com os dados atuais.
    """
    if receita_id in _receitas:
        return _receitas[receita_id]
    if not config.USAR_MYSQL:
        return None
    linhas = _consultar("SELECT `timestamp`, parametros FROM Receitas_Geradas WHERE id = %s", (receita_id,))
    if not linhas or not linhas[0]["parametros"]:
        return None
    receita = gerar(json.loads(linhas[0]["parametros"]))
    if receita is None:
        return None
    return dict(receita, id=receita_id, criado_em=linhas[0]["timestamp"].isoformat(), reconstruida=True)
