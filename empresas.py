"""Ambientes empresariais e implantação local pelo operador do Windows."""
import argparse
import ctypes
import getpass
import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

BUILTINS = {"varejmais": "VarejMais", "servifacil": "ServiFácil"}
DATA_DIR = Path(__file__).resolve().parent / "dados_empresas"


def valid_id(value):
    return bool(re.fullmatch(r"[a-z][a-z0-9_-]{1,39}", value)) and not Path(value).is_reserved()


def db_path(conn):
    return Path(next(row[2] for row in conn.execute("PRAGMA database_list") if row[1] == "main")).resolve()


def company_name(conn, company):
    if not valid_id(company) or db_path(conn).name != f"{company}.sqlite":
        return None
    if company in BUILTINS:
        return BUILTINS[company]
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='empresa_config'").fetchone():
        return None
    row = conn.execute("SELECT nome FROM empresa_config WHERE codigo=? AND modelo='comercial'", (company,)).fetchone()
    return row[0] if row else None


def discover(folder):
    companies = {}
    for path in sorted(folder.glob("*.sqlite")):
        key = path.stem
        if key in BUILTINS or not valid_id(key) or path.resolve().parent != folder.resolve():
            continue
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            name = company_name(db, key)
            if name:
                sector = db.execute("SELECT ramo FROM empresa_config WHERE codigo=?", (key,)).fetchone()[0]
                companies[key] = dict(nome=name, ramo=sector, descricao="Ambiente comercial", db=path)
    return companies


def is_operator():
    return os.name == "nt" and bool(ctypes.windll.shell32.IsUserAnAdmin())


def provision(folder, code, name, sector, username, fullname, password):
    from administracao import insert_user, audit_change
    from ai_sql import POLICY
    from auth import prepare_sessions

    if not is_operator():
        raise PermissionError("Implantação restrita ao operador local elevado.")
    if not valid_id(code) or code in BUILTINS or not name.strip() or not sector.strip():
        raise ValueError("Código reservado ou dados da empresa inválidos.")
    target = folder / f"{code}.sqlite"
    if target.exists():
        raise FileExistsError("Código de empresa já utilizado.")
    schema_tables = sorted(set(POLICY["varejmais"]["admin"]) | {"usuarios", "audit_log"})
    # Somente o esquema das tabelas autorizadas sai do modelo. A publicação
    # por hard link no mesmo volume é atômica e nunca substitui um cliente.
    with TemporaryDirectory(dir=folder) as stage:
        new = Path(stage) / target.name
        source = (folder / "varejmais.sqlite").resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(source, uri=True)) as template, closing(sqlite3.connect(new)) as db:
            for table in schema_tables:
                ddl = template.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
                if not ddl:
                    raise ValueError("Modelo comercial incompleto.")
                db.execute(ddl[0])
            prepare_sessions(db)
            with db:
                db.execute("CREATE TABLE empresa_config(codigo TEXT PRIMARY KEY,nome TEXT NOT NULL,ramo TEXT NOT NULL,modelo TEXT NOT NULL)")
                db.execute("INSERT INTO empresa_config VALUES(?,?,?,'comercial')", (code,name.strip(),sector.strip()))
                insert_user(db, username, fullname, "admin", password)
                actor = {"username": getpass.getuser(), "role": "operador_local"}
                audit_change(db, name.strip(), actor, "IMPLANTACAO_EMPRESA", code)
                audit_change(db, name.strip(), actor, "CADASTRO_ADMIN_INICIAL", username.strip())
        os.link(new, target)
    return target


def main():
    parser = argparse.ArgumentParser(description="Implantar ambiente comercial vazio.")
    for field in ("codigo", "nome", "ramo", "usuario", "nome-admin"):
        parser.add_argument("--" + field, required=True)
    args = parser.parse_args()
    if not is_operator():
        parser.exit(1, "A implantação exige um terminal Windows elevado.\n")
    import sys
    if not sys.stdin.isatty():
        parser.exit(1, "Use um terminal interativo para informar a senha em sigilo.\n")
    password = getpass.getpass("Senha inicial: ")
    if password != getpass.getpass("Confirme a senha: "):
        parser.exit(1, "As senhas não conferem.\n")
    try:
        provision(DATA_DIR, args.codigo, args.nome, args.ramo, args.usuario, args.nome_admin, password)
    except (OSError, ValueError, sqlite3.Error):
        parser.exit(1, "Empresa não implantada. Verifique código, campos, senha e permissões.\n")
    print("Empresa implantada. Atualize o seletor de ambientes no Streamlit.")


if __name__ == "__main__":
    main()
