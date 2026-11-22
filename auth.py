"""Autenticação e autorização de acesso ao histórico por empresa."""
import base64
import sqlite3
from empresas import BUILTINS as COMPANIES, company_name

import pandas as pd
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

HASHER = PasswordHasher()  # Argon2id, salt aleatório por conta.
def prepare_sessions(conn):
    def ready():
        return any(r[1] == "sessao_versao" for r in conn.execute("PRAGMA table_info(usuarios)"))
    if not ready():
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            if not ready():
                conn.execute("ALTER TABLE usuarios ADD COLUMN sessao_versao INTEGER NOT NULL DEFAULT 1")



def migrate_passwords(conn):
    """Renomeia a coluna e converte os valores na mesma transação."""
    def columns():
        return {r[1] for r in conn.execute("PRAGMA table_info(usuarios)")}

    if columns() >= {"senha_hash"}:
        if "senha" in columns():
            raise RuntimeError("Esquema de autenticação ambíguo.")
        return
    conn.execute("PRAGMA secure_delete=ON")
    conn.execute("BEGIN IMMEDIATE")
    try:
        current = columns()
        if "senha" in current and "senha_hash" not in current:
            rows = conn.execute("SELECT id, senha FROM usuarios").fetchall()
            for account_id, password in rows:
                conn.execute("UPDATE usuarios SET senha=? WHERE id=?", (HASHER.hash(password), account_id))
            conn.execute("ALTER TABLE usuarios RENAME COLUMN senha TO senha_hash")
        elif "senha_hash" not in current or "senha" in current:
            raise RuntimeError("Esquema de autenticação inesperado.")
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def login(conn, company, username, password):
    if not company_name(conn, company):
        return None
    prepare_sessions(conn)
    row = conn.execute("""SELECT username,nome,role,senha_hash,sessao_versao FROM usuarios
        WHERE username=? AND ativo=1""", (username,)).fetchone()
    if row is None:
        return None
    try:
        HASHER.verify(row[3], password)
    except (InvalidHashError, VerificationError):
        return None
    if HASHER.check_needs_rehash(row[3]):
        with conn:
            conn.execute("UPDATE usuarios SET senha_hash=? WHERE username=? AND senha_hash=?",
                         (HASHER.hash(password), row[0], row[3]))
    return dict(username=row[0], nome=row[1], role=row[2], empresa_id=company, sessao_versao=row[4])


def valid_session(conn, company, user):
    if not user or user.get("empresa_id") != company or not company_name(conn, company):
        return False
    return bool(conn.execute("""SELECT 1 FROM usuarios WHERE username=? AND role=? AND ativo=1
        AND sessao_versao=?""", (user["username"],user["role"],user.get("sessao_versao"))).fetchone())


def can_read_audit(conn, company, user):
    return bool(user and user.get("role") == "admin" and valid_session(conn, company, user))


def audit_report(conn, company, user, username=None, status=None):
    if not can_read_audit(conn, company, user):
        raise PermissionError("Acesso à auditoria restrito.")
    return pd.read_sql_query("""SELECT id, COALESCE(NULLIF(empresa,''), ?) AS empresa,
        username, role, acao, pergunta, sql_gerado, tabelas_alvo, status, motivo, created_at
        FROM audit_log WHERE (empresa=? OR empresa IS NULL OR empresa='')
        AND (? IS NULL OR username=?) AND (? IS NULL OR status=?)
        ORDER BY id DESC LIMIT 200""", conn, params=(company_name(conn, company),) * 2 + (username, username, status, status))


def audit_view(conn, company, user, username=None, status=None):
    report = audit_report(conn, company, user, username, status)
    return report, base64.b64encode(report.to_csv(index=False).encode("utf-8-sig")).decode("ascii")


def audit_csv(conn, company, user, username=None, status=None):
    return audit_view(conn, company, user, username, status)[1]
