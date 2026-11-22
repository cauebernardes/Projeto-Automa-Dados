"""Testes com bancos temporários. Nenhuma credencial é impressa."""
import base64
import csv
import gc
import io
import secrets
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from contextlib import closing
from pathlib import Path

from argon2 import extract_parameters, Type
from streamlit.testing.v1 import AppTest

from auth import COMPANIES, audit_csv, audit_report, login, migrate_passwords

ROOT = Path(__file__).resolve().parent


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(gc.collect)
        self.root = Path(self.temp.name)
        for file in ("app.py", "auth.py", "empresas.py", "administracao.py", "ai_sql.py", "gemini_sql.py", "chamados.py", "sla.toml"):
            shutil.copyfile(ROOT / file, self.root / file)
        shutil.copytree(ROOT / "dados_empresas", self.root / "dados_empresas")
        self.credentials = {}
        for company in COMPANIES:
            with closing(self.connect(company)) as db:
                cols = {r[1] for r in db.execute("PRAGMA table_info(usuarios)")}
                if "senha_hash" in cols:
                    # Em instalações já migradas, recria o formato legado só na cópia.
                    db.execute("ALTER TABLE usuarios RENAME COLUMN senha_hash TO senha")
                    for uid, in db.execute("SELECT id FROM usuarios").fetchall():
                        db.execute("UPDATE usuarios SET senha=? WHERE id=?", (secrets.token_urlsafe(), uid))
                    db.commit()
                self.credentials[company] = db.execute("SELECT username,senha,role FROM usuarios WHERE ativo=1 ORDER BY id").fetchall()

    def connect(self, company):
        return sqlite3.connect(self.root / "dados_empresas" / f"{company}.sqlite")

    def test_migration_access_and_history(self):
        for company, name in COMPANIES.items():
            with self.subTest(company=company), closing(self.connect(company)) as db:
                db.execute("INSERT INTO audit_log(empresa,acao) VALUES (?,NULL)", (name,))
                db.execute("INSERT INTO audit_log(empresa,acao) VALUES (?,NULL)", ("",))
                db.execute("INSERT INTO audit_log(empresa,acao) VALUES ('outra','externa')")
                db.commit()
                history = db.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
                accounts = db.execute("SELECT id,username,nome,role,ativo,created_at FROM usuarios ORDER BY id").fetchall()
                migrate_passwords(db)
                hashes = db.execute("SELECT senha_hash FROM usuarios ORDER BY id").fetchall()
                self.assertTrue(all(extract_parameters(h).type == Type.ID for h, in hashes))
                migrate_passwords(db)
                self.assertTrue(hashes == db.execute("SELECT senha_hash FROM usuarios ORDER BY id").fetchall())
                self.assertTrue(accounts == db.execute("SELECT id,username,nome,role,ativo,created_at FROM usuarios ORDER BY id").fetchall())
                self.assertTrue(history == db.execute("SELECT * FROM audit_log ORDER BY id").fetchall())
                for username, password, role in self.credentials[company]:
                    user = login(db, company, username, password)
                    self.assertTrue(user is not None and user["role"] == role)
                    self.assertIsNone(login(db, company, username, secrets.token_urlsafe()))
                    if role == "viewer":
                        for method in (audit_report, audit_csv):
                            with self.assertRaises(PermissionError):
                                method(db, company, user)
                        continue
                    report = audit_report(db, company, user)
                    self.assertEqual(set(report.empresa), {name})
                    self.assertIn("sql_gerado", report.columns)
                    self.assertTrue(report.acao.isna().any())
                    exported = list(csv.DictReader(io.StringIO(base64.b64decode(audit_csv(db, company, user)).decode("utf-8-sig"))))
                    self.assertEqual([str(i) for i in report.id], [r["id"] for r in exported])
                    with db:
                        db.execute("INSERT INTO audit_log(empresa,username,status,acao) VALUES (?,?,?,?)",
                                   (name,"filtro.demo","BLOCKED","CONSULTA_IA"))
                    matched = audit_report(db,company,user,"filtro.demo","BLOCKED")
                    self.assertEqual(matched.username.tolist(), ["filtro.demo"])
                    self.assertEqual(base64.b64decode(audit_csv(db,company,user,"filtro.demo","BLOCKED")),
                                     matched.to_csv(index=False).encode("utf-8-sig"))
                    filtered = audit_report(db, company, user, username="inexistente", status="BLOCKED")
                    self.assertTrue(filtered.empty)
                    csv_filtered = base64.b64decode(audit_csv(db, company, user, username="inexistente", status="BLOCKED"))
                    self.assertEqual(csv_filtered, filtered.to_csv(index=False).encode("utf-8-sig"))
                    other = next(key for key in COMPANIES if key != company)
                    with closing(self.connect(other)) as other_db:
                        with self.assertRaises(PermissionError):
                            audit_csv(other_db, company, user)
                        with self.assertRaises(PermissionError):
                            audit_report(other_db, other, user)
                    with db:
                        db.execute("UPDATE usuarios SET ativo=0 WHERE username=?", (username,))
                    with self.assertRaises(PermissionError):
                        audit_csv(db, company, user)

    def test_app(self):
        # O AppTest mant?m refer?ncias ao ?ltimo script. Libera seus bancos
        # antes de o Windows tentar remover o diret?rio de teste.
        connections = []
        connect = sqlite3.connect
        def track(*args, **kwargs):
            db = connect(*args, **kwargs)
            if kwargs.get('check_same_thread') is False:
                connections.append(db)
            return db
        self.addCleanup(lambda: [db.close() for db in connections])
        with patch.object(sqlite3, "connect", track):
            self.check_app_sessions()

    def check_app_sessions(self):
        for company in COMPANIES:
            for role in ("admin", "viewer"):
                with self.subTest(company=company, role=role):
                    username, password, _ = next(c for c in self.credentials[company] if c[2] == role)
                    app = AppTest.from_file(str(self.root / "app.py"), default_timeout=45)
                    app.session_state["empresa_id"] = company
                    app.run()
                    self.assertFalse(app.exception)
                    self.assertFalse(any(password in c.value for c in app.caption))
                    app.text_input[0].set_value(username)
                    app.text_input[1].set_value(password)
                    next(b for b in app.button if b.label == "Entrar").click().run()
                    self.assertFalse(app.exception)
                    self.assertEqual(app.session_state["user"]["role"], role)
                    self.assertEqual(app.metric[0].value, "3" if company == "servifacil" else "15.000")
                    self.assertEqual("Usuários" in [t.label for t in app.tabs], role == "admin")
                    self.assertEqual("Auditoria" in [t.label for t in app.tabs], role == "admin")
                    self.assertEqual(bool(app.get("iframe")), role == "admin")
                    self.assertEqual("Chamados & SLA" in [t.label for t in app.tabs], company == "servifacil")
                    self.assertEqual(any(b.label == "Registrar chamado" for b in app.button), company == "servifacil" and role == "admin")
                    if company == "servifacil":
                        self.assertEqual(len(app.tabs[2].dataframe[0].value), 3)
                    # Após o rerun interno do login, o AppTest pode manter widgets
                    # removidos na árvore. Envia apenas o evento do seletor real.
                    other = next(k for k in COMPANIES if k != company)
                    from streamlit.proto.WidgetStates_pb2 import WidgetStates
                    event = app.radio[0].set_value(other)._widget_state
                    app._run(WidgetStates(widgets=[event]))
                    self.assertFalse(app.exception)
                    self.assertIsNone(app.session_state["user"])
                    self.assertEqual(app.session_state["empresa_id"], other)
                    self.assertFalse(app.tabs)


if __name__ == "__main__":
    unittest.main()
