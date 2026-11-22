"""Implantação e administração em diretórios temporários privados de teste."""
import hashlib
import secrets
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import administracao as admin
import empresas
from ai_sql import QueryBlocked, execute_ai_query
from auth import audit_report, login, valid_session


class TestAdministracao(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir=empresas.DATA_DIR.parent)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.folder = self.root / "dados_empresas"
        self.folder.mkdir()
        for name in empresas.BUILTINS:
            shutil.copyfile(empresas.DATA_DIR / f"{name}.sqlite", self.folder / f"{name}.sqlite")
        self.password = secrets.token_urlsafe()
        self.elevation = patch("empresas.is_operator", return_value=True)
        self.elevation.start()
        self.addCleanup(self.elevation.stop)

    def deploy(self, code):
        path = empresas.provision(self.folder, code, "Cliente de teste", "Comércio", "gestor", "Gestor", self.password)
        db = sqlite3.connect(path)
        self.addCleanup(db.close)
        return db, login(db, code, "gestor", self.password)

    def test_implantacao(self):
        def fingerprints():
            return [hashlib.sha256((self.folder / f"{k}.sqlite").read_bytes()).digest() for k in empresas.BUILTINS]
        before = fingerprints()
        with patch("empresas.is_operator", return_value=False), self.assertRaises(PermissionError):
            self.deploy("teste")
        db, manager = self.deploy("teste")
        for code in ("teste", "varejmais", "servifacil", "../teste", "con"):
            with self.assertRaises((ValueError, FileExistsError)):
                self.deploy(code)
        self.assertEqual(before, fingerprints())
        self.assertEqual(list(empresas.discover(self.folder)), ["teste"])
        self.assertEqual(len(admin.accounts(db, "teste", manager)), 1)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM fato_vendas").fetchone()[0], 0)
        self.assertEqual(len(audit_report(db, "teste", manager)), 2)
        self.assertEqual(set(admin.accounts(db,"teste",manager).columns), {"username","nome","role","ativo"})

    def test_ciclo_e_isolamento(self):
        db, owner = self.deploy("cliente_a")
        other, other_owner = self.deploy("cliente_b")
        company = "cliente_a"
        for role in ("admin","viewer"):
            admin.create_user(db, company, owner, role, "Teste", role, self.password)
        manager = login(db, company, "admin", self.password)
        reader = login(db, company, "viewer", self.password)
        self.assertIsNotNone(manager)
        self.assertIsNotNone(reader)
        self.assertIsNone(login(other, "cliente_b", "viewer", self.password))
        self.assertIsNone(login(db, "cliente_b", "admin", self.password))
        with self.assertRaises(PermissionError):
            admin.create_user(db, company, reader, "extra", "Teste", "admin", self.password)
        for actor in (reader, other_owner):
            with self.assertRaises(PermissionError):
                admin.change_user(db, company, actor, "admin", "DESATIVACAO_USUARIO")
            with self.assertRaises(PermissionError):
                audit_report(db, company, actor)
        name = "Cliente de teste"
        db.execute("INSERT INTO fato_vendas(valor_total) VALUES(320)")
        db.commit()
        sql = "SELECT COUNT(*) FROM fato_vendas"
        for con, key, user, count in ((db,company,reader,1),(other,"cliente_b",other_owner,0)):
            frame, _ = execute_ai_query(con,key,name,user,"Teste",sql)
            self.assertEqual(frame.iloc[0,0],count)
        with self.assertRaises(QueryBlocked):
            execute_ai_query(other,"cliente_b",name,reader,"Teste",sql)
        new = secrets.token_urlsafe()
        admin.change_user(db,company,manager,"viewer","REDEFINICAO_SENHA",new)
        self.assertFalse(valid_session(db,company,reader))
        self.assertIsNone(login(db,company,"viewer",self.password))
        reader = login(db,company,"viewer",new)
        self.assertTrue(valid_session(db,company,reader))
        admin.change_user(db,company,owner,"viewer","DESATIVACAO_USUARIO")
        self.assertIsNone(login(db,company,"viewer",new))
        with self.assertRaises(QueryBlocked):
            execute_ai_query(db,company,name,reader,"Teste",sql)
        admin.change_user(db,company,owner,"viewer","ATIVACAO_USUARIO")
        self.assertFalse(valid_session(db,company,reader))
        self.assertTrue(valid_session(db,company,login(db,company,"viewer",new)))
        admin.change_user(db,company,owner,"admin","DESATIVACAO_USUARIO")
        with self.assertRaises(PermissionError):
            admin.accounts(db,company,manager)
        with self.assertRaises(ValueError):
            admin.change_user(db,company,owner,"gestor","DESATIVACAO_USUARIO")
        report = audit_report(db,company,owner)
        self.assertTrue({"CADASTRO_USUARIO","REDEFINICAO_SENHA","ATIVACAO_USUARIO","DESATIVACAO_USUARIO"} <= set(report.acao))
        text = report.to_csv(index=False)
        self.assertTrue(all(x not in text for x in (new,self.password,"$argon2")))
        self.assertEqual(set(other.execute("SELECT username FROM usuarios").fetchone()),{"gestor"})

    def test_painel_novo(self):
        db, manager = self.deploy("loja_teste")
        for name in ("app.py","auth.py","empresas.py","administracao.py","ai_sql.py","gemini_sql.py", "chamados.py","sla.toml"):
            shutil.copyfile(empresas.DATA_DIR.parent / name, self.root / name)
        connections = []
        connect = sqlite3.connect
        def track(*args, **kwargs):
            conn = connect(*args, **kwargs)
            if kwargs.get('check_same_thread') is False:
                connections.append(conn)
            return conn
        self.addCleanup(lambda: [c.close() for c in connections])
        with patch.object(sqlite3, "connect", track):
            app = AppTest.from_file(str(self.root/"app.py"), default_timeout=45)
            app.session_state["empresa_id"] = "loja_teste"
            app.session_state["user"] = manager
            app.run()
            self.assertFalse(app.exception)
            self.assertEqual(app.metric[0].value, "0")
            self.assertIn("Usuários",[t.label for t in app.tabs])
            form = app.tabs[-1]
            for field, value in zip(form.text_input, ("novo.leitor","Nome de teste",self.password)):
                field.set_value(value)
            next(b for b in form.button if b.label == "Cadastrar usuário").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(login(db,"loja_teste","novo.leitor",self.password)["role"],"viewer")
