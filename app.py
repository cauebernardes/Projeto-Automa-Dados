import os
from html import escape
import sqlite3
from pathlib import Path

import administracao
import empresas
import chamados
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from auth import audit_view, can_read_audit, login, migrate_passwords, prepare_sessions, valid_session
from dotenv import load_dotenv

from ai_sql import MAX_ROWS, QueryBlocked, execute_ai_query

from gemini_sql import GenerationError, generate


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "dados_empresas"
load_dotenv(BASE_DIR / ".env", override=False)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

EMPRESAS = {
    "varejmais": {
        "nome": "VarejMais",
        "ramo": "Varejo e distribuição",
        "db": DATA_DIR / "varejmais.sqlite",
        "descricao": "Ambiente comercial: vendas, produtos, clientes e logística.",
    },
    "servifacil": {
        "nome": "ServiFácil",
        "ramo": "Serviços e suporte técnico",
        "db": DATA_DIR / "servifacil.sqlite",
        "descricao": "Ambiente de serviços: chamados, SLA e contratos.",
    },
}

st.set_page_config(page_title="Automa Dados", page_icon="📊", layout="wide")
st.html("""<style>
:root {--ink:#122d35;--muted:#52666d;--line:#d9e3e3;--teal:#116c68}
.stApp {background:#f4f7f6;color:var(--ink)}
[data-testid="stMainBlockContainer"] {max-width:1440px;padding:3.6rem clamp(1rem,3vw,3.4rem) 3rem}
[data-testid="stHeader"] {background:transparent}
[data-testid="stSidebar"] {border-right:1px solid var(--line);background:#eaf0ef}
[data-testid="stSidebarUserContent"] {padding-top:1rem}
.ad-brand {display:flex;align-items:center;gap:.75rem;font:700 1.23rem/1.2 "Inter","Segoe UI",sans-serif;letter-spacing:-.045em;margin:0 0 2.4rem}
.ad-mark {display:inline-flex;align-items:end;gap:3px;background:#0c494b;border-radius:10px;padding:10px;width:37px;height:37px;box-sizing:border-box}
.ad-mark i {flex:1;background:#a7e4c8;height:58%;border-radius:2px}.ad-mark i:nth-child(2){height:100%}.ad-mark i:last-child{height:77%}
[data-testid="stSidebar"] [role="radiogroup"] label {background:#f9fbfa;border:1px solid var(--line);border-radius:10px;padding:.55rem .65rem}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){background:#daf1e9;border-color:#81bbaa}
.ad-hero {isolation:isolate;position:relative;overflow:hidden;background:linear-gradient(115deg,#102f39,#115851);color:#fff;border-radius:20px;padding:clamp(1.5rem,3.4vw,3.4rem);margin-bottom:.5rem}
.ad-hero:after {content:"";position:absolute;z-index:-1;right:-108px;bottom:-222px;width:470px;height:470px;border-radius:32%;transform:rotate(-35deg);border:1px solid #a7e7ca69;box-shadow:0 0 0 23px #225c59,0 0 0 24px #91c9af4a,0 0 0 47px #1b5754,0 0 0 48px #91c9af40,0 0 0 72px #18544f,0 0 0 73px #91c9af30}
.ad-hero h1 {color:white;font:650 clamp(2.05rem,4vw,4.2rem)/1.05 "Inter","Segoe UI",sans-serif;letter-spacing:-.055em;margin:0;padding:.65rem 0 .8rem;overflow-wrap:anywhere}
.ad-hero p {color:#d9ebe7;font-size:1rem;margin:0;max-width:33rem}
.ad-kicker {font-size:.74rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#a8e2cc}
.ad-access {min-height:335px;display:flex;flex-direction:column;justify-content:center}
.st-key-login_box {background:#fff;border:1px solid var(--line);padding:1.5rem;border-radius:18px}
[data-testid="stTabs"] [role="tablist"] {gap:.3rem;background:#e7eeec;border-radius:12px;padding:.3rem;height:auto}
[data-testid="stTabs"] [role="tab"] {height:2.55rem;padding:0 .9rem;border-radius:8px;color:#365056}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {background:white;color:#075852;box-shadow:0 1px 4px #152d351b}
[data-baseweb="tab-highlight"],[data-baseweb="tab-border"] {display:none}
[data-testid="stMetric"] {border:1px solid var(--line);border-radius:14px;background:white;padding:1rem 1.1rem;border-top:3px solid #62a995;min-height:102px}
[data-testid="stMetricValue"] {font-size:clamp(1.15rem,1.72vw,2.2rem);font-weight:650;letter-spacing:-.05em;font-variant-numeric:tabular-nums}
[data-testid="stMetricValue"] > div {white-space:normal;overflow-wrap:anywhere}
h2,h3 {color:var(--ink);letter-spacing:-.035em}
[data-testid="stExpander"],[data-testid="stForm"] {background:#fff;border-radius:14px}
.st-key-chart_card {background:#fff;border:1px solid var(--line);border-radius:16px;padding:1rem 1.3rem}
[data-testid="stSidebar"] hr {border-color:#cdd9d6}
@media(max-width:760px){.ad-access{min-height:180px}.ad-hero:after{opacity:.65}.ad-hero{padding:1.4rem}[data-testid="stMetric"]{min-height:82px}}
</style>""")


def get_conn(db_path: Path):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_common_tables(conn, empresa):
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, empresa TEXT NOT NULL, username TEXT,
        role TEXT, acao TEXT, pergunta TEXT, sql_gerado TEXT, tabelas_alvo TEXT,
        status TEXT, motivo TEXT, created_at TEXT DEFAULT (datetime('now'))
    )""")
    # Migração segura do banco legado da VarejMais.
    cols = {row[1] for row in conn.execute("PRAGMA table_info(audit_log)")}
    for col, ddl in [("empresa", "TEXT"), ("role", "TEXT"), ("acao", "TEXT"), ("tabelas_alvo", "TEXT")]:
        if col not in cols:
            conn.execute(f"ALTER TABLE audit_log ADD COLUMN {col} {ddl}")
    # Registros legados sem empresa permanecem intactos no banco isolado.
    conn.commit()
    migrate_passwords(conn)
    prepare_sessions(conn)
    if empresa == "ServiFácil":
        chamados.migrate(conn, chamados.calendar())


def bootstrap_databases():
    for empresa in EMPRESAS.values():
        if not empresa["db"].is_file():
            st.error("Prepare os bancos locais com preparar_demo.py antes de iniciar o sistema.")
            st.stop()
        conn = get_conn(empresa["db"])
        try:
            ensure_common_tables(conn, empresa["nome"])
        finally:
            conn.close()


bootstrap_databases()
EMPRESAS.update(empresas.discover(DATA_DIR))

if "empresa_id" not in st.session_state:
    st.session_state.empresa_id = "varejmais"
if "user" not in st.session_state:
    st.session_state.user = None


def empresa_atual():
    return EMPRESAS[st.session_state.empresa_id]


def log_audit(conn, empresa, user, acao, pergunta="", sql="", tables="", status="ALLOWED", motivo="OK"):
    conn.execute("""INSERT INTO audit_log(empresa,username,role,acao,pergunta,sql_gerado,tabelas_alvo,status,motivo)
                    VALUES(?,?,?,?,?,?,?,?,?)""", (empresa, user.get("username", "sistema"), user.get("role", ""), acao, pergunta, sql, tables, status, motivo))
    conn.commit()


def header(emp, access=False):
    mode = " ad-access" if access else ""
    title = escape(emp["nome"])
    subtitle = escape(emp["ramo"])
    label = "Acesso ao ambiente" if access else "Painel da empresa"
    st.html(f'<section class="ad-hero{mode}"><span class="ad-kicker">{label}</span>'
            f'<h1>{title}</h1><p>{subtitle}</p></section>')


with st.sidebar:
    st.html('<div class="ad-brand"><span class="ad-mark" aria-hidden="true"><i></i><i></i><i></i></span>Automa Dados</div>')
    labels = {k: v["nome"] if k in empresas.BUILTINS else f"{v['nome']} ({k})" for k, v in EMPRESAS.items()}
    chosen = st.radio("Selecione o cliente", list(labels), format_func=lambda x: labels[x], index=list(labels).index(st.session_state.empresa_id))
    if chosen != st.session_state.empresa_id:
        st.session_state.empresa_id = chosen
        st.session_state.user = None
        st.rerun()
    st.divider()
    st.caption(empresa_atual()["descricao"])

emp = empresa_atual()
conn = get_conn(emp["db"])

if st.session_state.user and not valid_session(conn, st.session_state.empresa_id, st.session_state.user):
    st.session_state.user = None

if st.session_state.user is None:
    intro, form = st.columns([1.2, 1], gap="large", vertical_alignment="center")
    with intro:
        header(emp, access=True)
    with form.container(key="login_box"):
        st.subheader("Entrar")
        st.caption("Use sua conta da empresa selecionada.")
        username = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar", type="primary", use_container_width=True):
            row = login(conn, st.session_state.empresa_id, username, senha)
            if row:
                st.session_state.user = dict(row)
                log_audit(conn, emp["nome"], st.session_state.user, "LOGIN")
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos para esta empresa.")
    st.stop()

user = st.session_state.user
header(emp)
with st.sidebar:
    st.divider()
    st.text(user["nome"])
    st.caption("Administrador" if user["role"] == "admin" else "Leitor")
    if st.button("Sair"):
        log_audit(conn, emp["nome"], user, "LOGOUT")
        st.session_state.user = None
        st.rerun()

company = st.session_state.empresa_id
show_audit = can_read_audit(conn, company, user)
service = company == "servifacil"
tabs = st.tabs(["Painel", "Consulta com IA"] + (["Chamados & SLA"] if service else []) + (["Auditoria", "Usuários"] if show_audit else []))

with tabs[0]:
    if not service:
        vendas = conn.execute("SELECT COUNT(*), COALESCE(SUM(valor_total),0), COALESCE(AVG(valor_total),0) FROM fato_vendas").fetchone()
        clientes = conn.execute("SELECT COUNT(*) FROM dim_cliente").fetchone()[0]
        a,b,c,d = st.columns(4)
        a.metric("Vendas registradas", f"{vendas[0]:,}".replace(",", "."))
        b.metric("Faturamento", f"R$ {vendas[1]:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        c.metric("Ticket médio", f"R$ {vendas[2]:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        d.metric("Clientes", clientes)
        with st.container(key="chart_card"):
            st.subheader("Top produtos por faturamento")
            sql = """SELECT p.nome_produto AS Produto, ROUND(SUM(v.valor_total),2) AS Faturamento
                     FROM fato_vendas v JOIN dim_produto p ON p.id_produto=v.id_produto
                     GROUP BY p.nome_produto ORDER BY Faturamento DESC LIMIT 8"""
            st.bar_chart(pd.read_sql_query(sql, conn), x="Produto", y="Faturamento", horizontal=True, sort="-Faturamento", color="#178276", height=320)
    else:
        total, abertos, vencidos = chamados.counts(conn)
        mrr = conn.execute("SELECT COALESCE(SUM(valor_mensal),0) FROM contratos WHERE status='Ativo'").fetchone()[0]
        a,b,c,d = st.columns(4)
        a.metric("Chamados", total); b.metric("Em aberto", abertos); c.metric("SLA vencido", vencidos); d.metric("Receita mensal", f"R$ {mrr:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        with st.container(key="chart_card"):
            st.subheader("Chamados por prioridade")
            chart = pd.read_sql_query("SELECT prioridade, COUNT(*) AS quantidade FROM chamados GROUP BY prioridade", conn)
            st.bar_chart(chart, x="prioridade", y="quantidade", x_label="Prioridade", y_label="Chamados", color="#178276", height=280)

with tabs[1]:
    st.subheader("Consulta em linguagem natural")
    if not GEMINI_API_KEY:
        st.warning("Gemini não configurado neste ambiente. Painel, chamados e auditoria seguem funcionais.")
    else:
        question = st.text_area("Pergunte sobre os dados da empresa")
        if st.button("Gerar consulta"):
            company = st.session_state.empresa_id
            try:
                sql = generate(question, company, user["role"], EMPRESAS, GEMINI_API_KEY)
            except (QueryBlocked, GenerationError) as exc:
                status = "BLOCKED" if isinstance(exc, QueryBlocked) else "ERROR"
                log_audit(conn, emp["nome"], user, "CONSULTA_IA", question, status=status, motivo=str(exc))
                st.error(str(exc))
            except Exception:
                log_audit(conn, emp["nome"], user, "CONSULTA_IA", question, status="ERROR", motivo="Falha na integração Gemini.")
                st.error("Falha na integração Gemini.")
            else:
                st.code(sql, language="sql")
                try:
                    result, truncated = execute_ai_query(conn, company, emp["nome"], user, question, sql)
                except QueryBlocked as exc:
                    st.error(str(exc))
                except sqlite3.Error:
                    st.error("Falha ao executar ou registrar a consulta.")
                else:
                    if truncated:
                        st.info(f"Resultado limitado a {MAX_ROWS} registros.")
                    st.dataframe(result, use_container_width=True)
                    st.download_button("Exportar CSV", result.to_csv(index=False).encode("utf-8-sig"), "resultado_consulta.csv", "text/csv")


if service:
    with tabs[2]:
        st.subheader("Central de chamados")
        try:
            calls = chamados.tickets(conn, user)
            if user["role"] == "admin":
                with st.expander("Abrir novo chamado"):
                    with st.form("novo_chamado", clear_on_submit=True):
                        title = st.text_input("Título")
                        description = st.text_area("Descrição")
                        requester = st.text_input("Solicitante", value=user["nome"])
                        category = st.text_input("Categoria", value="Geral")
                        priority = st.selectbox("Prioridade", list(chamados.HOURS), index=2)
                        submit = st.form_submit_button("Registrar chamado")
                    if submit:
                        chamados.create(conn, user, title, description, requester, category, priority, chamados.calendar())
                        st.rerun()
            st.dataframe(calls.drop(columns="versao", errors="ignore"), hide_index=True, use_container_width=True)
            if not calls.empty:
                selected = st.selectbox("Chamado", calls["id"].tolist())
                row = calls.loc[calls["id"] == selected].iloc[0]
                if user["role"] == "admin" and row.status != "Fechado":
                    if pd.isna(row.primeira_resposta_em):
                        with st.expander("Registrar primeira resposta"):
                            with st.form(f"responder_{selected}_{row.versao}"):
                                message = st.text_area("Resposta comunicada ao solicitante")
                                if st.form_submit_button("Registrar resposta"):
                                    chamados.first_response(conn, user, selected, int(row.versao), message)
                                    st.rerun()
                    with st.expander("Atualizar chamado"):
                        with st.form(f"editar_{selected}_{row.versao}"):
                            state = st.selectbox("Status", chamados.STATES, index=chamados.STATES.index(row.status))
                            owner = st.text_input("Responsável", value=row.responsavel or "")
                            priority = st.selectbox("Prioridade", list(chamados.HOURS), index=list(chamados.HOURS).index(row.prioridade))
                            category = st.text_input("Categoria", value=row.categoria)
                            save = st.form_submit_button("Salvar atualização")
                        if save:
                            chamados.update(conn, user, selected, int(row.versao), state, owner, priority, category, chamados.calendar())
                            st.rerun()
                with st.expander("Histórico do chamado"):
                    st.dataframe(chamados.history(conn, user, selected), hide_index=True, use_container_width=True)
        except (PermissionError, ValueError) as exc:
            st.error(str(exc))


if show_audit:
    with tabs[-2]:
        st.subheader("Auditoria do ambiente atual")
        left, right = st.columns(2)
        account_filter = left.text_input("Filtrar por login", key=f"audit_user_{company}").strip() or None
        result_filter = right.selectbox("Status do evento", [None, "ALLOWED", "BLOCKED", "ERROR"],
            format_func=lambda item: item or "Todos", key=f"audit_status_{company}")
        report, payload = audit_view(conn, company, user, account_filter, result_filter)
        st.caption("Consultas de IA entre os últimos 200 eventos que correspondem aos filtros")
        queries = report.loc[report.acao == "CONSULTA_IA", "status"]
        for column, status, label in zip(st.columns(3), ["ALLOWED", "BLOCKED", "ERROR"],
                ["Permitidas", "Bloqueadas", "Com erro"]):
            column.metric(label, int((queries == status).sum()))
        st.dataframe(report, use_container_width=True, hide_index=True)
        if not report.empty:
            with st.expander("Detalhes do evento"):
                event_id = st.selectbox("Evento", report.id.tolist(), key=f"auditoria_evento_{company}")
                event = report.loc[report.id == event_id].iloc[0]
                st.text(f"{event.status} · {event.username} · {event.created_at}")
                if event.pergunta:
                    st.write(event.pergunta)
                if event.motivo:
                    st.text(event.motivo)
                if event.sql_gerado:
                    st.code(event.sql_gerado, language="sql")
        # O arquivo segue na sessão autorizada, sem URL de mídia compartilhável.
        components.html(f'<a download="auditoria_{company}.csv" href="data:text/csv;base64,{payload}">Exportar auditoria CSV</a>', height=40)

    with tabs[-1]:
        st.subheader("Usuários da empresa")
        try:
            users = administracao.accounts(conn, company, user)
            st.dataframe(users, hide_index=True, use_container_width=True)
            with st.form("cadastrar_usuario", clear_on_submit=True):
                account = st.text_input("Novo usuário")
                fullname = st.text_input("Nome completo")
                role = st.selectbox("Perfil", ["viewer", "admin"])
                password = st.text_input("Senha inicial (mínimo 12 caracteres)", type="password")
                if st.form_submit_button("Cadastrar usuário"):
                    administracao.create_user(conn, company, user, account, fullname, role, password)
                    st.rerun()
            account = st.selectbox("Conta para administrar", users.username.tolist())
            active = bool(users.loc[users.username == account, "ativo"].iloc[0])
            if st.button("Desativar conta" if active else "Ativar conta"):
                action = "DESATIVACAO_USUARIO" if active else "ATIVACAO_USUARIO"
                administracao.change_user(conn, company, user, account, action)
                st.rerun()
            with st.form("redefinir_senha", clear_on_submit=True):
                new_password = st.text_input("Nova senha (mínimo 12 caracteres)", type="password")
                if st.form_submit_button("Redefinir senha"):
                    administracao.change_user(conn, company, user, account, "REDEFINICAO_SENHA", new_password)
                    st.rerun()
        except (ValueError, PermissionError) as exc:
            st.error(str(exc))
