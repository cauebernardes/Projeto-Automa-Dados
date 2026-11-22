"""Administração de contas da empresa autenticada."""
import re
import sqlite3

import pandas as pd

from auth import HASHER, can_read_audit
from empresas import company_name


def audit_change(db, name, actor, action, target):
    db.execute("""INSERT INTO audit_log(empresa,username,role,acao,tabelas_alvo,status,motivo)
        VALUES(?,?,?,?,?,'ALLOWED',?)""", (name, actor["username"], actor["role"], action,
        "empresa_config" if action == "IMPLANTACAO_EMPRESA" else "usuarios", target))


def password_hash(password):
    if not 12 <= len(password) <= 256 or not password.strip():
        raise ValueError("Use uma senha entre 12 e 256 caracteres.")
    return HASHER.hash(password)


def insert_user(db, username, fullname, role, password):
    username = username.strip()
    if not re.fullmatch(r"[\w.@-]{1,80}", username) or not fullname.strip() or role not in ("admin", "viewer"):
        raise ValueError("Informe usuário, nome e perfil válidos.")
    try:
        db.execute("INSERT INTO usuarios(username,nome,role,senha_hash,ativo) VALUES(?,?,?,?,1)",
                   (username, fullname.strip(), role, password_hash(password)))
    except sqlite3.IntegrityError as exc:
        raise ValueError("Usuário já cadastrado ou dados inválidos.") from exc


def authorize(db, company, actor):
    if not can_read_audit(db, company, actor):
        raise PermissionError("Administração restrita à empresa autenticada.")


def accounts(db, company, actor):
    authorize(db, company, actor)
    return pd.read_sql_query("SELECT username,nome,role,ativo FROM usuarios ORDER BY username", db)


def create_user(db, company, actor, username, fullname, role, password):
    with db:
        db.execute("BEGIN IMMEDIATE")
        authorize(db, company, actor)
        insert_user(db, username, fullname, role, password)
        audit_change(db, company_name(db, company), actor, "CADASTRO_USUARIO", f"{username.strip()} ({role})")


def change_user(db, company, actor, username, action, password=None):
    with db:
        db.execute("BEGIN IMMEDIATE")
        authorize(db, company, actor)
        row = db.execute("SELECT role,ativo FROM usuarios WHERE username=?", (username,)).fetchone()
        if row is None:
            raise ValueError("Conta não encontrada.")
        if action == "REDEFINICAO_SENHA":
            db.execute("UPDATE usuarios SET senha_hash=?,sessao_versao=sessao_versao+1 WHERE username=?",
                       (password_hash(password or ""), username))
        elif action in ("ATIVACAO_USUARIO", "DESATIVACAO_USUARIO"):
            active = int(action == "ATIVACAO_USUARIO")
            if active == row[1]:
                return
            if not active and row[0] == "admin" and db.execute(
                "SELECT COUNT(*) FROM usuarios WHERE ativo=1 AND role='admin'").fetchone()[0] <= 1:
                raise ValueError("A empresa precisa manter um administrador ativo.")
            db.execute("UPDATE usuarios SET ativo=?,sessao_versao=sessao_versao+1 WHERE username=?", (active,username))
        else:
            raise ValueError("Operação inválida.")
        audit_change(db, company_name(db, company), actor, action, username)
