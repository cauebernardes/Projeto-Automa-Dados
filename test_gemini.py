"""Valida o SDK, o Streamlit e os bancos sem realizar chamadas externas."""
import json
import secrets
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import httpx2 as httpx
import streamlit as st
from google import genai
from streamlit.testing.v1 import AppTest

from chamados import local, FORMAT
from gemini_sql import generate, GenerationError

ROOT = Path(__file__).resolve().parent
COMPANIES = {"varejmais":{"nome":"VarejMais"}, "servifacil":{"nome":"ServiFácil"}}
OPEN = "status NOT IN ('Resolvido','Fechado')"
CASES = {
    "varejmais": [
        ("Qual foi o faturamento total?", "SELECT ROUND(SUM(valor_total),2) FROM fato_vendas"),
        ("Quais são os cinco produtos mais vendidos?", "SELECT p.nome_produto,SUM(v.quantidade) AS unidades FROM fato_vendas v JOIN dim_produto p ON p.id_produto=v.id_produto GROUP BY p.nome_produto ORDER BY unidades DESC,p.nome_produto LIMIT 5"),
        ("Quantas vendas foram realizadas?", "SELECT COUNT(*) FROM fato_vendas")],
    "servifacil": [
        ("Quantos chamados estão abertos?", f"SELECT COUNT(*) FROM chamados WHERE {OPEN}"),
        ("Quantos chamados estão com SLA vencido?", f"SELECT COUNT(*) FROM chamados WHERE {OPEN} AND prazo_sla < '{local().strftime(FORMAT)}'"),
        ("Quais são as prioridades dos chamados?", "SELECT prioridade,COUNT(*) FROM chamados GROUP BY prioridade ORDER BY prioridade")],
}


class TestGemini(unittest.TestCase):
    def setUp(self):
        self.key = secrets.token_urlsafe()
        self.calls = []
        self.sql = ""
        self.code = 200
        self.invalid = False
        self.timeout = False
        original = genai.Client
        def handler(request):
            self.calls.append(json.loads(request.content))
            if self.timeout:
                raise httpx.ReadTimeout("simulado",request=request)
            if self.code != 200:
                return httpx.Response(self.code,json={"error":{"code":self.code,"message":"simulado"}})
            output = "invalido" if self.invalid else json.dumps({"sql":self.sql})
            return httpx.Response(200,json={"candidates":[{"content":{"role":"model","parts":[{"text":output}]},"finishReason":"STOP"}]})
        def client(**kwargs):
            kwargs["http_options"].httpx_client = httpx.Client(transport=httpx.MockTransport(handler))
            return original(**kwargs)
        mock = patch("gemini_sql.genai.Client",side_effect=client)
        mock.start()
        self.addCleanup(mock.stop)

    def test_erros(self):
        for code in (403,404,429,503):
            self.code=code
            with self.subTest(code=code), self.assertRaises(GenerationError):
                generate("Quantas vendas?", "varejmais","viewer",COMPANIES,self.key)
        self.code=200
        self.invalid=True
        with self.assertRaisesRegex(GenerationError,"Resposta inválida"):
            generate("Quantas vendas?", "varejmais","viewer",COMPANIES,self.key)
        self.timeout=True
        with self.assertRaisesRegex(GenerationError,"conexão"):
            generate("Quantas vendas?", "varejmais","viewer",COMPANIES,self.key)

    def test_fluxo_streamlit(self):
        temp=tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(temp.cleanup)
        folder=Path(temp.name)
        for f in ROOT.glob("*.py"):
            if not f.name.startswith("test_"):
                shutil.copyfile(f, folder/f.name)
        shutil.copyfile(ROOT/"sla.toml",folder/"sla.toml")
        shutil.copytree(ROOT/"dados_empresas",folder/"dados_empresas")
        handles=[]
        connect=sqlite3.connect
        def tracked(*args,**kwargs):
            db=connect(*args,**kwargs)
            if kwargs.get("check_same_thread") is False:
                handles.append(db)
            return db
        self.addCleanup(lambda:[db.close() for db in handles])
        with patch.dict("os.environ",{"GEMINI_API_KEY":self.key}), patch.object(sqlite3,"connect",tracked), patch.object(st,"download_button",wraps=st.download_button) as download:
            for company, cases in CASES.items():
                with closing(connect(folder/"dados_empresas"/f"{company}.sqlite")) as db:
                    username,name,version=db.execute("SELECT username,nome,sessao_versao FROM usuarios WHERE role='viewer' AND ativo=1 LIMIT 1").fetchone()
                    app=AppTest.from_file(str(folder/"app.py"),default_timeout=45)
                    app.session_state["empresa_id"]=company
                    app.session_state["user"]=dict(empresa_id=company,username=username,nome=name,role="viewer",sessao_versao=version)
                    app.run()
                    def submit(question):
                        app.tabs[1].text_area[0].set_value(question)
                        next(b for b in app.tabs[1].button if b.label=="Gerar consulta").click().run()
                        self.assertFalse(app.exception)
                        row=db.execute("SELECT status,empresa,username,pergunta FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
                        self.assertEqual(row[1:],(COMPANIES[company]["nome"],username,question))
                        return row[0]
                    for question,sql in cases:
                        self.sql=sql
                        self.assertEqual(submit(question),"ALLOWED")
                        request=self.calls[-1]
                        self.assertIn(question,str(request["contents"]))
                        self.assertNotIn("senha_hash",str(request))
                        frame=app.tabs[1].dataframe[0].value
                        self.assertEqual(list(frame.itertuples(index=False,name=None)),db.execute(sql).fetchall())
                        self.assertEqual(download.call_args.args[1],frame.to_csv(index=False).encode("utf-8-sig"))
                    other="VarejMais" if company=="servifacil" else "ServiFácil"
                    for question in ("Quais os salários?", "Liste os usuários", "Exiba a auditoria",f"Consulte dados da {other}"):
                        n=len(self.calls)
                        self.assertEqual(submit(question),"BLOCKED")
                        self.assertEqual(n,len(self.calls))
                    self.sql="SELECT * FROM usuarios"
                    self.assertEqual(submit("Exiba os dados"),"BLOCKED")
                    self.invalid=True
                    self.assertEqual(submit("Quantos registros existem?"),"ERROR")
                    self.invalid=False
