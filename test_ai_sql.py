"""Regressão do executor de IA, usando cópias descartáveis dos bancos."""
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_sql
from auth import prepare_sessions


class QueryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ai_sql.DATA_DIR.parent)
        self.addCleanup(self.temp.cleanup)
        folder = Path(self.temp.name)
        for file in ai_sql.DATA_DIR.glob("*.sqlite"):
            shutil.copyfile(file, folder / file.name)
        override = patch.object(ai_sql, "DATA_DIR", folder)
        override.start()
        self.addCleanup(override.stop)

    def check_query(self, company, sql, status, role="viewer"):
        name = {"varejmais": "VarejMais", "servifacil": "ServiFácil"}[company]
        db = sqlite3.connect(ai_sql.DATA_DIR / f"{company}.sqlite")
        try:
            prepare_sessions(db)
            row = db.execute("SELECT username,sessao_versao FROM usuarios WHERE role=? AND ativo=1 LIMIT 1",(role,)).fetchone()
            username, version = row or ("teste-local", 0)
            user = dict(username=username, role=role, empresa_id=company, sessao_versao=version)
            def run():
                return ai_sql.execute_ai_query(db, company, name, user, "Teste local", sql)
            if status == "ALLOWED":
                result = run()
            else:
                with self.assertRaises(ai_sql.QueryBlocked if status == "BLOCKED" else sqlite3.Error):
                    run()
                result = None
            record = db.execute("""SELECT empresa, username, role, status, sql_gerado, acao
                FROM audit_log ORDER BY id DESC LIMIT 1""").fetchone()
            self.assertEqual(record, (name, user["username"], role, status, sql, "CONSULTA_IA"))
            return result
        finally:
            db.close()

    def test_authorized(self):
        for company, sql, expected in [
            ("varejmais", "SELECT COUNT(*) FROM fato_vendas", 15000),
            ("servifacil", "WITH c AS (SELECT id FROM chamados) SELECT COUNT(id) FROM c", 3),
        ]:
            with self.subTest(company=company):
                frame, truncated = self.check_query(company, sql, "ALLOWED")
                self.assertEqual(frame.iloc[0, 0], expected)
                self.assertFalse(truncated)
        frame, truncated = self.check_query("varejmais", "SELECT id_venda FROM fato_vendas", "ALLOWED")
        self.assertEqual(len(frame), ai_sql.MAX_ROWS)
        self.assertTrue(truncated)

    def test_denials(self):
        for sql in [
            "SELECT COUNT(*) FROM usuarios", "SELECT * FROM audit_log",
            "SELECT salario_atual FROM dim_funcionario", "SELECT salario_base FROM dim_cargo",
            "SELECT * FROM chamados", "SELECT * FROM servifacil.chamados",
            "UPDATE fato_vendas SET valor_total=0", "DELETE FROM fato_vendas",
            "INSERT INTO fato_vendas(id_venda) VALUES (0)", "DROP TABLE fato_vendas",
            "SELECT id_venda FROM fato_vendas; SELECT id_venda FROM fato_vendas",
            "SELECT id_venda FROM fato_vendas WHERE EXISTS (SELECT 1 FROM usuarios)",
            "SELECT v.id_venda FROM fato_vendas v JOIN usuarios u ON u.id=v.id_venda",
            "WITH x AS (SELECT username FROM usuarios) SELECT * FROM x",
            "WITH x AS (SELECT 1) DELETE FROM fato_vendas",
            "SELECT nome_cliente FROM dim_cliente",
        ]:
            with self.subTest(sql=sql):
                self.check_query("varejmais", sql, "BLOCKED")
        self.check_query("servifacil", "SELECT * FROM fato_vendas", "BLOCKED")
        self.check_query("servifacil", "SELECT valor_mensal FROM contratos", "BLOCKED")
        self.check_query("servifacil", "SELECT valor_mensal FROM contratos", "ALLOWED", "admin")
        self.check_query("varejmais", "SELECT salario_atual FROM dim_funcionario", "BLOCKED", "admin")
        self.check_query("varejmais", "SELECT id_venda FROM fato_vendas", "BLOCKED", "desconhecido")
        self.check_query("servifacil", "SELECT id + FROM chamados", "ERROR")


if __name__ == "__main__":
    unittest.main()
