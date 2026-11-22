"""Cria a demonstração com dados fictícios e senhas escolhidas localmente."""
from contextlib import closing
from getpass import getpass
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import sqlite3

import chamados
from administracao import insert_user

BASE = Path(__file__).resolve().parent


def criar(pasta, senhas):
    destino = pasta / "dados_empresas"
    if destino.exists():
        raise FileExistsError("A pasta dados_empresas já existe. Instalação preservada.")
    with TemporaryDirectory(dir=pasta) as temporaria:
        dados = Path(temporaria) / "dados_empresas"
        dados.mkdir()
        for empresa in ("varejmais", "servifacil"):
            with closing(sqlite3.connect(dados / f"{empresa}.sqlite")) as db, db:
                db.executescript((BASE / "demo" / f"{empresa}.sql").read_text(encoding="utf-8"))
                for perfil in ("admin", "viewer"):
                    insert_user(db, perfil, f"Demonstração {perfil}", perfil, senhas[empresa, perfil])
                if empresa == "varejmais":
                    db.executemany("INSERT INTO dim_cliente(id_cliente,nome_cliente) VALUES (?,?)", [(i,f"Cliente {i}") for i in range(1,13)])
                    db.executemany("INSERT INTO dim_produto(id_produto,nome_produto,categoria,preco_venda) VALUES (?,?,?,?)", [(i,f"Produto {i}","Demonstração",i*10) for i in range(1,9)])
                    db.executemany("INSERT INTO fato_vendas(id_venda,id_cliente,id_produto,quantidade,preco_unitario,valor_total) VALUES (?,?,?,?,?,?)",
                                   ((i,i%12+1,i%8+1,i%3+1,(i%8+1)*10,(i%3+1)*(i%8+1)*10) for i in range(1,15001)))
                else:
                    for i, prioridade in enumerate(("Urgente","Alta","Média"),1):
                        abertura = chamados.local()
                        prazo = chamados.deadline(abertura,prioridade,chamados.calendar())
                        db.execute("INSERT INTO chamados(titulo,solicitante,prioridade,status,aberto_em,prazo_sla) VALUES (?,?,?,?,?,?)",
                                   (f"Atendimento {i}","Solicitante demo",prioridade,"Aberto",abertura.strftime(chamados.FORMAT),prazo.strftime(chamados.FORMAT)))
                    db.execute("INSERT INTO contratos(cliente,plano,valor_mensal,status) VALUES ('Empresa demo','Básico',100,'Ativo')")
        os.rename(dados,destino)


if __name__ == "__main__":
    if (BASE / "dados_empresas").exists():
        raise SystemExit("A pasta dados_empresas já existe. Instalação preservada.")
    senhas = {}
    for empresa in ("varejmais","servifacil"):
        for perfil in ("admin","viewer"):
            while True:
                senha = getpass(f"Senha local para {empresa}/{perfil} (12 a 256 caracteres): ")
                if 12 <= len(senha) <= 256 and senha.strip() and senha == getpass("Confirme: "):
                    senhas[empresa,perfil] = senha
                    break
                print("Confira o comprimento e a confirmação.")
    criar(BASE,senhas)
    print("Demonstração pronta. Inicie pelo INICIAR_SISTEMA.bat.")
