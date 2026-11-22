"""Regressão de chamados usando apenas bancos descartáveis."""
import json
import shutil
import sqlite3
import tempfile
import unittest
from datetime import date, time
from pathlib import Path

import chamados as c
from auth import prepare_sessions

ROOT = Path(__file__).resolve().parent
SCHEDULE = (time(9), set())


class TestSLA(unittest.TestCase):
    def test_prazos(self):
        for opened, priority, due in (
            ("2026-11-20 15:00", "Urgente", "2026-11-23 11:00"),
            ("2026-11-20 09:00", "Alta", "2026-11-20 17:00"),
            ("2026-11-20 17:00", "Média", "2026-11-24 17:00"),
            ("2026-11-21 13:00", "Baixa", "2026-11-25 17:00"),
            ("2026-11-23 08:00", "Urgente", "2026-11-23 13:00"),
            ("2026-11-20T18:00:00+00:00", "Urgente", "2026-11-23 11:00"),
        ):
            with self.subTest(opened=opened, priority=priority):
                self.assertEqual(c.deadline(opened, priority, SCHEDULE), c.local(due))
        self.assertEqual(c.deadline("2026-11-20 15:00", "Urgente", (time(8), {date(2026,11,23)})), c.local("2026-11-24 11:00"))


class TestChamados(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        for company in ("servifacil", "varejmais"):
            shutil.copyfile(ROOT/"dados_empresas"/f"{company}.sqlite", self.folder/f"{company}.sqlite")
        self.db = sqlite3.connect(self.folder/"servifacil.sqlite")
        self.addCleanup(self.db.close)
        prepare_sessions(self.db)
        self.users = {r:dict(username=u, role=r, empresa_id="servifacil", sessao_versao=v) for u,r,v in self.db.execute("SELECT username,role,sessao_versao FROM usuarios WHERE ativo=1")}

    def test_primeira_resposta(self):
        db = self.db
        c.migrate(db,SCHEDULE)
        user = self.users["admin"]
        ticket = c.create(db,user,"Teste","Descrição","Pessoa","Rede","Alta",SCHEDULE)
        with self.assertRaises(PermissionError):
            c.first_response(db,self.users["viewer"],ticket,1,"Recebido")
        c.first_response(db,user,ticket,1,"Recebido")
        with self.assertRaises(ValueError):
            c.first_response(db,user,ticket,2,"Segunda")
        row = c.tickets(db,user).set_index("id").loc[ticket]
        self.assertEqual(row.sla_primeira_resposta,"Dentro do prazo")
        self.assertEqual(c.history(db,user,ticket).iloc[-1].acao,"PRIMEIRA_RESPOSTA")
        self.assertEqual(db.execute("SELECT acao FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()[0],"PRIMEIRA_RESPOSTA")

    def test_migracao(self):
        # Recria o formato anterior em uma cópia para poder repetir o teste após a implantação.
        db = self.db
        db.execute("DROP TABLE IF EXISTS chamado_historico")
        db.execute("DROP TABLE chamados")
        db.execute("""CREATE TABLE chamados (id INTEGER PRIMARY KEY,titulo TEXT,descricao TEXT,solicitante TEXT,
                    prioridade TEXT,status TEXT,responsavel TEXT,aberto_em TEXT,prazo_sla TEXT,concluido_em TEXT)""")
        db.execute("""INSERT INTO chamados VALUES(1,'Teste','D','S','Urgente','Aberto',NULL,
            '2026-11-21 10:00:00','2026-11-21 18:00:00',NULL)""")
        db.execute("""INSERT INTO chamados VALUES(2,'Legado','D','S','Média','Concluído','R',
            '2026-11-19 10:00:00','2026-11-21 10:00:00','2026-11-20 12:00:00')""")
        db.commit()
        c.migrate(db,SCHEDULE)
        c.migrate(db,SCHEDULE)
        self.assertEqual(db.execute("SELECT status,concluido_em FROM chamados WHERE id=2").fetchone(),("Fechado","2026-11-20 12:00:00"))
        self.assertEqual(db.execute("SELECT count(*) FROM chamado_historico").fetchone()[0],2)
        self.assertEqual(c.counts(db,"2026-11-23T16:00:00+00:00"),(2,1,0))
        self.assertEqual(c.counts(db,"2026-11-23T16:00:01+00:00"),(2,1,1))

    def test_fluxo_e_permissoes(self):
        db=self.db
        c.migrate(db,SCHEDULE)
        admin=self.users["admin"]
        viewer=self.users["viewer"]
        ticket=c.create(db,admin,"Teste","Descrição","Solicitante","Rede","Alta",SCHEDULE)
        for version,state in enumerate(c.STATES[1:],start=1):
            c.update(db,admin,ticket,version,state,"Técnico","Urgente","Rede",SCHEDULE)
        row=db.execute("SELECT status,responsavel,prioridade,aberto_em,prazo_sla,concluido_em FROM chamados WHERE id=?",(ticket,)).fetchone()
        self.assertEqual(row[:3],("Fechado","Técnico","Urgente"))
        self.assertEqual(c.local(row[4]),c.deadline(row[3],"Urgente",SCHEDULE))
        self.assertIsNotNone(row[5])
        events=c.history(db,admin,ticket)
        actions=events.acao.tolist()
        logged=[r[0] for r in db.execute("SELECT acao FROM audit_log WHERE pergunta=? AND empresa='ServiFácil' AND username=? ORDER BY id",(f"Chamado #{ticket}",admin["username"]))]
        self.assertEqual(actions,logged)
        self.assertEqual(actions[-1],"ENCERRAMENTO_CHAMADO")
        self.assertIn("ATRIBUICAO_CHAMADO",actions)
        states=[json.loads(d)["status"][1] for d in events.detalhes[1:] if "status" in json.loads(d)]
        self.assertEqual(states,list(c.STATES[1:]))
        self.assertNotIn("descricao",c.tickets(db,viewer))
        self.assertNotIn("detalhes",c.history(db,viewer,ticket))
        for user in (viewer,dict(admin,empresa_id="varejmais"),dict(viewer,role="admin")):
            with self.assertRaises(PermissionError):
                c.create(db,user,"Teste","D","S","Geral","Alta",SCHEDULE)
            with self.assertRaises(PermissionError):
                c.update(db,user,ticket,6,"Aberto","","Baixa","Geral",SCHEDULE)
        with self.assertRaises(ValueError):
            c.update(db,admin,ticket,6,"Aberto","","Alta","Geral",SCHEDULE)
        other=sqlite3.connect(self.folder/"varejmais.sqlite")
        self.addCleanup(other.close)
        with self.assertRaises(PermissionError):
            c.create(other,admin,"Teste","D","S","Geral","Alta",SCHEDULE)
        self.assertFalse(other.execute("SELECT 1 FROM sqlite_master WHERE name='chamados'").fetchone())

    def test_edicao_concorrente_e_atomicidade(self):
        db=self.db
        c.migrate(db,SCHEDULE)
        admin=self.users["admin"]
        ticket=c.create(db,admin,"Teste","D","S","Geral","Alta",SCHEDULE)
        c.update(db,admin,ticket,1,"Em triagem","","Alta","Geral",SCHEDULE)
        with self.assertRaises(ValueError):
            c.update(db,admin,ticket,1,"Fechado","","Alta","Geral",SCHEDULE)
        db.execute("CREATE TRIGGER rejeita BEFORE INSERT ON audit_log BEGIN SELECT RAISE(ABORT,'teste'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            c.update(db,admin,ticket,2,"Fechado","","Alta","Geral",SCHEDULE)
        self.assertEqual(db.execute("SELECT status,versao FROM chamados WHERE id=?",(ticket,)).fetchone(),("Em triagem",2))
        self.assertEqual(len(c.history(db,admin,ticket)),2)
