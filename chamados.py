"""Chamados da ServiFácil. Datas operacionais em America/Sao_Paulo."""
import json
import tomllib
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from auth import valid_session

ZONE = ZoneInfo("America/Sao_Paulo")
STATES = ("Aberto", "Em triagem", "Em atendimento", "Aguardando usuário", "Resolvido", "Fechado")
HOURS = {"Urgente": 4, "Alta": 8, "Média": 16, "Baixa": 24}
FORMAT = "%Y-%m-%d %H:%M:%S"


def calendar():
    with Path(__file__).with_name("sla.toml").open("rb") as file:
        config = tomllib.load(file)
    start = time.fromisoformat(config["inicio"])
    if start.tzinfo or start.second or start.microsecond or start.hour >= 16:
        raise ValueError("Configure início entre 00:00 e 15:59.")
    return start, {date.fromisoformat(d) for d in config["feriados"]}


def local(value=None):
    if value is None:
        return datetime.now(ZONE)
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.replace(tzinfo=ZONE) if value.tzinfo is None else value.astimezone(ZONE)


def deadline(opened, priority, schedule):
    start, holidays = schedule
    current = local(opened)
    remaining = timedelta(hours=HOURS[priority])
    while True:
        opening = datetime.combine(current.date(), start, ZONE)
        closing = opening + timedelta(hours=8)
        if current.weekday() < 5 and current.date() not in holidays:
            current = max(current, opening)
            available = max(timedelta(), closing - current)
            if remaining <= available:
                return current + remaining
            remaining -= available
        current = datetime.combine(current.date() + timedelta(days=1), start, ZONE)


def service_db(db):
    path = next(row[2] for row in db.execute("PRAGMA database_list") if row[1] == "main")
    return Path(path).name == "servifacil.sqlite"


def authorize(db, user, write=False):
    if not service_db(db) or not user or user.get("empresa_id") != "servifacil":
        raise PermissionError("Acesso restrito à ServiFácil.")
    role = user.get("role")
    if role not in (("admin",) if write else ("admin", "viewer")) or not valid_session(db, "servifacil", user):
        raise PermissionError("Permissão insuficiente.")


def _migrate_history(db, schedule):
    if not service_db(db):
        raise PermissionError("Banco incompatível.")
    def migrated():
        return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='chamado_historico'").fetchone()
    if migrated():
        return
    with db:
        db.execute("BEGIN IMMEDIATE")
        if migrated():
            return
        db.execute("ALTER TABLE chamados ADD COLUMN categoria TEXT NOT NULL DEFAULT 'Geral'")
        db.execute("ALTER TABLE chamados ADD COLUMN versao INTEGER NOT NULL DEFAULT 1")
        db.execute("""CREATE TABLE chamado_historico (
            id INTEGER PRIMARY KEY, chamado_id INTEGER NOT NULL REFERENCES chamados(id),
            data_local TEXT NOT NULL, usuario TEXT NOT NULL, acao TEXT NOT NULL, detalhes TEXT NOT NULL)""")
        db.execute("CREATE INDEX historico_por_chamado ON chamado_historico(chamado_id,id)")
        for ticket, priority, opened, old_due, old_state in db.execute(
            "SELECT id,prioridade,aberto_em,prazo_sla,status FROM chamados"
        ).fetchall():
            state = "Fechado" if old_state == "Concluído" else old_state
            if state not in STATES or priority not in HOURS:
                raise ValueError("Estado ou prioridade legada desconhecida. Migração cancelada.")
            due = deadline(opened, priority, schedule).strftime(FORMAT)
            db.execute("UPDATE chamados SET prazo_sla=?,status=? WHERE id=?", (due, state, ticket))
            details = {"status": [old_state, state], "prazo_sla": [old_due, due], "categoria": "Geral"}
            db.execute("INSERT INTO chamado_historico(chamado_id,data_local,usuario,acao,detalhes) VALUES (?,?,?,?,?)",
                       (ticket, local().strftime(FORMAT), "sistema", "MIGRACAO", json.dumps(details, ensure_ascii=False)))


def migrate(db, schedule):
    _migrate_history(db, schedule)
    if "resposta_legada" in {r[1] for r in db.execute("PRAGMA table_info(chamados)")}:
        return
    with db:
        db.execute("BEGIN IMMEDIATE")
        if "primeira_resposta_em" not in {r[1] for r in db.execute("PRAGMA table_info(chamados)")}:
            db.execute("ALTER TABLE chamados ADD COLUMN primeira_resposta_em TEXT")
            db.execute("ALTER TABLE chamados ADD COLUMN prazo_primeira_resposta TEXT")
        if "resposta_legada" not in {r[1] for r in db.execute("PRAGMA table_info(chamados)")}:
            db.execute("ALTER TABLE chamados ADD COLUMN resposta_legada INTEGER NOT NULL DEFAULT 0")
            db.execute("UPDATE chamados SET resposta_legada=1 WHERE primeira_resposta_em IS NULL")


def first_response(db, user, ticket, version, message):
    with db:
        db.execute("BEGIN IMMEDIATE")
        authorize(db, user, write=True)
        if not message.strip():
            raise ValueError("Informe a resposta comunicada ao solicitante.")
        stamp = local().strftime(FORMAT)
        cursor = db.execute("""UPDATE chamados SET primeira_resposta_em=?, prazo_primeira_resposta=prazo_sla,
            versao=versao+1 WHERE id=? AND versao=? AND primeira_resposta_em IS NULL AND status!='Fechado'""",
            (stamp, ticket, version))
        if cursor.rowcount != 1:
            raise ValueError("Chamado fechado, já respondido ou alterado. Recarregue a tela.")
        record(db, ticket, user, "PRIMEIRA_RESPOSTA", {"resposta": message.strip(), "data_local": stamp})


def record(db, ticket, user, action, changes):
    details = json.dumps(changes, ensure_ascii=False)
    db.execute("INSERT INTO chamado_historico(chamado_id,data_local,usuario,acao,detalhes) VALUES (?,?,?,?,?)",
               (ticket, local().strftime(FORMAT), user["username"], action, details))
    db.execute("""INSERT INTO audit_log(empresa,username,role,acao,pergunta,tabelas_alvo,status,motivo)
        VALUES ('ServiFácil',?,?,?,?,'chamados','ALLOWED',?)""",
        (user["username"], user["role"], action, f"Chamado #{ticket}", details))


def create(db, user, title, description, requester, category, priority, schedule):
    with db:
        db.execute("BEGIN IMMEDIATE")
        authorize(db, user, write=True)
        if not all(v.strip() for v in (title, description, requester, category)) or priority not in HOURS:
            raise ValueError("Preencha os campos e selecione uma prioridade válida.")
        now = local()
        due = deadline(now, priority, schedule).strftime(FORMAT)
        ticket = db.execute("""INSERT INTO chamados(titulo,descricao,solicitante,categoria,prioridade,status,aberto_em,prazo_sla)
            VALUES (?,?,?,?,?,'Aberto',?,?)""", (title.strip(), description.strip(), requester.strip(), category.strip(),
            priority, now.strftime(FORMAT), due)).lastrowid
        record(db, ticket, user, "ABERTURA_CHAMADO", {"status": "Aberto", "prioridade": priority, "prazo_sla": due})
        return ticket


def update(db, user, ticket, version, state, assignee, priority, category, schedule):
    with db:
        db.execute("BEGIN IMMEDIATE")
        authorize(db, user, write=True)
        row = db.execute("SELECT status,responsavel,prioridade,categoria,aberto_em,prazo_sla,concluido_em,versao FROM chamados WHERE id=?", (ticket,)).fetchone()
        if row is None or row[7] != version:
            raise ValueError("O chamado mudou. Recarregue antes de salvar.")
        if row[0] == "Fechado" or state not in STATES or priority not in HOURS or not category.strip():
            raise ValueError("Alteração inválida ou chamado fechado.")
        assignee = assignee.strip() or None
        fields = ("status", "responsavel", "prioridade", "categoria")
        changes = {k: [old, new] for k, old, new in zip(fields, row, (state, assignee, priority, category.strip())) if old != new}
        if not changes:
            return
        due = row[5]
        if "prioridade" in changes:
            due = deadline(row[4], priority, schedule).strftime(FORMAT)
            changes["prazo_sla"] = [row[5], due]
        finished = (row[6] or local().strftime(FORMAT)) if state in STATES[-2:] else None
        db.execute("""UPDATE chamados SET status=?,responsavel=?,prioridade=?,categoria=?,prazo_sla=?,
            concluido_em=?,versao=versao+1 WHERE id=?""", (state, assignee, priority, category.strip(), due, finished, ticket))
        for key, action in (("responsavel","ATRIBUICAO_CHAMADO"), ("status","ENCERRAMENTO_CHAMADO" if state == "Fechado" else "STATUS_CHAMADO")):
            if key in changes:
                record(db, ticket, user, action, {key: changes.pop(key)})
        if changes:
            record(db, ticket, user, "ATUALIZACAO_CHAMADO", changes)


def tickets(db, user):
    authorize(db, user)
    columns = "id,categoria,prioridade,status,aberto_em,prazo_sla,concluido_em"
    if user["role"] == "admin":
        columns += ",titulo,descricao,solicitante,responsavel,versao"
    columns += ",primeira_resposta_em, prazo_primeira_resposta"
    return pd.read_sql_query(f"""SELECT {columns}, CASE
        WHEN primeira_resposta_em IS NOT NULL THEN CASE WHEN primeira_resposta_em <= prazo_primeira_resposta
            THEN 'Dentro do prazo' ELSE 'Fora do prazo' END
        WHEN resposta_legada=1 THEN 'Legado sem registro'
        WHEN status IN ('Fechado','Resolvido') THEN 'Sem registro'
        WHEN prazo_sla < ? THEN 'Pendente em atraso' ELSE 'Pendente' END AS sla_primeira_resposta
        FROM chamados ORDER BY id DESC""", db, params=(local().strftime(FORMAT),))


def history(db, user, ticket):
    authorize(db, user)
    columns = "data_local,acao" + (",usuario,detalhes" if user["role"] == "admin" else "")
    return pd.read_sql_query(f"SELECT {columns} FROM chamado_historico WHERE chamado_id=? ORDER BY id", db, params=(ticket,))


def counts(db, now=None):
    return db.execute("""SELECT COUNT(*), COUNT(*) FILTER (WHERE status NOT IN ('Fechado','Resolvido')),
        COUNT(*) FILTER (WHERE status NOT IN ('Fechado','Resolvido') AND prazo_sla < ?) FROM chamados""",
        (local(now).strftime(FORMAT),)).fetchone()
