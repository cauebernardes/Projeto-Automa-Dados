"""Política e executor das consultas geradas pela IA."""
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from time import monotonic

import pandas as pd
from auth import valid_session
from empresas import company_name as registered_name, db_path

DATA_DIR = Path(__file__).resolve().parent / "dados_empresas"
MAX_ROWS = 500

VENDAS = {
    "fato_vendas": "id_venda id_cliente id_produto id_data quantidade preco_unitario valor_total",
    "dim_produto": "id_produto nome_produto categoria preco_venda",
    "dim_cliente": "id_cliente estado setor",
    "dim_tempo": "id_data data_completa dia dia_semana mes nome_mes trimestre ano",
    "fato_logistica": "id_venda id_data_saida id_data_entrega_prevista status custo_frete",
}
SUPORTE = {
    "chamados": "id categoria prioridade status aberto_em prazo_sla concluido_em",
    "contratos": "id plano status",
}
POLICY = {
    "varejmais": {
        "viewer": VENDAS,
        "admin": {**VENDAS, "dim_cliente": VENDAS["dim_cliente"] + " nome_cliente",
                  "dim_produto": VENDAS["dim_produto"] + " custo_producao",
                  "fato_financeiro": "id_lancamento id_data id_centro_custo id_projeto tipo_lancamento valor"},
    },
    "servifacil": {
        "viewer": SUPORTE,
        "admin": {**SUPORTE, "contratos": "id plano status cliente valor_mensal",
                  "chamados": SUPORTE["chamados"] + " titulo responsavel"},
    },
}
FUNCTIONS = frozenset("abs avg coalesce count date datetime ifnull julianday length like lower max min nullif round strftime substr sum total trim upper".split())


class QueryBlocked(ValueError):
    pass


def schema_for_ai(company, role):
    tables = POLICY.get(company, {}).get(role, {})
    return "\n".join(f"{table}({', '.join(cols.split())})" for table, cols in tables.items())


def _read_query(path, company, role, sql, touched):
    policy = POLICY.get(company, {}).get(role)
    if not policy:
        raise QueryBlocked("Empresa ou perfil sem permissão.")
    if not isinstance(sql, str) or not re.match(r"^\s*(SELECT|WITH)\b", sql, re.I):
        raise QueryBlocked("Envie uma única consulta SELECT ou WITH.")
    if len(sql.encode("utf-8")) > 16000:
        raise QueryBlocked("Consulta muito longa.")

    allowed = {table: set(columns.split()) for table, columns in policy.items()}
    def authorize(action, first, second, database, source):
        if action == sqlite3.SQLITE_READ:
            touched.add(first)
            # SQLite pode omitir o banco na leitura sem coluna de COUNT(*).
            if database in ("main", None) and first in allowed and (second == "" or second in allowed[first]):
                return sqlite3.SQLITE_OK
        elif action == sqlite3.SQLITE_SELECT:
            return sqlite3.SQLITE_OK
        elif action == sqlite3.SQLITE_FUNCTION and second in FUNCTIONS:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    uri = path.as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA trusted_schema=OFF")
        db.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 65536)
        db.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, 64)
        db.setconfig(sqlite3.SQLITE_DBCONFIG_DQS_DML, False)
        db.set_authorizer(authorize)
        deadline = monotonic() + 3
        db.set_progress_handler(lambda: monotonic() >= deadline, 1000)
        try:
            cursor = db.execute(sql)
            rows = cursor.fetchmany(MAX_ROWS + 1)
        except sqlite3.ProgrammingError as exc:
            if "one statement" in str(exc) or "null character" in str(exc):
                raise QueryBlocked("Envie uma única instrução SQL válida.") from exc
            raise
        except sqlite3.DatabaseError as exc:
            code = getattr(exc, "sqlite_errorcode", None)
            if code in (sqlite3.SQLITE_AUTH, sqlite3.SQLITE_INTERRUPT, sqlite3.SQLITE_TOOBIG) or str(exc).startswith(("no such table:", "not authorized")):
                raise QueryBlocked("Acesso não autorizado ou limite de execução atingido.") from exc
            raise
        return pd.DataFrame.from_records(rows[:MAX_ROWS], columns=[item[0] for item in cursor.description]), len(rows) > MAX_ROWS


def execute_ai_query(conn, company, company_name, user, question, sql):
    # A conexão de auditoria vem da sessão autenticada; nunca é entregue ao SQL da IA.
    if registered_name(conn, company) != company_name or user.get("empresa_id") != company:
        raise QueryBlocked("Sessão e empresa incompatíveis.")
    touched = set()
    status, reason = "ERROR", "Falha na execução."
    try:
        if not valid_session(conn, company, user):
            raise QueryBlocked("Sessão inválida ou expirada.")
        template = "servifacil" if company == "servifacil" else "varejmais"
        result, truncated = _read_query(db_path(conn), template, user["role"], sql, touched)
    except QueryBlocked as exc:
        status, reason = "BLOCKED", str(exc)
        raise
    except sqlite3.Error as exc:
        reason = str(exc)
        raise
    else:
        status = "ALLOWED"
        reason = f"Resultado limitado a {MAX_ROWS} registros." if truncated else "OK"
    finally:
        conn.execute("""INSERT INTO audit_log
            (empresa,username,role,acao,pergunta,sql_gerado,tabelas_alvo,status,motivo)
            VALUES (?,?,?,'CONSULTA_IA',?,?,?,?,?)""",
            (company_name, user["username"], user["role"], question, sql, ", ".join(sorted(touched)), status, reason))
        conn.commit()
    return result, truncated
