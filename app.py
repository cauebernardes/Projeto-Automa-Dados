import os
import re
import sqlite3
import base64
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
import google.generativeai as genai

# =========================
# Config inicial
# =========================
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DB_PATH = os.getenv(
    "DB_PATH", r"C:\Users\doido\OneDrive\Desktop\Automa_Dados_Demo_Streamlit\projeto.sqlite"
)

st.set_page_config(page_title="Automa Dados - IA Auditável", layout="wide")

# Tema escuro (preto + azul)
st.markdown(
    """
    <style>
    .stApp { background-color: #0B0F19; color: #E6EDF7; }
    .stTextInput > div > div > input,
    .stTextArea textarea {
        background-color: #111827 !important;
        color: #E6EDF7 !important;
        border: 1px solid #1E3A8A !important;
    }
    .stButton > button {
        background-color: #1D4ED8 !important;
        color: #FFFFFF !important;
        border: 1px solid #2563EB !important;
    }
    .stButton > button:hover {
        background-color: #1E40AF !important;
        border-color: #3B82F6 !important;
    }

    .stDownloadButton > button {
        background-color: #1D4ED8 !important;
        color: #FFFFFF !important;
        border: 1px solid #2563EB !important;
    }
    .stDownloadButton > button:hover {
        background-color: #1E40AF !important;
        border-color: #3B82F6 !important;
    }
    .stAlert { background-color: #111827 !important; }
    div[data-testid="stCodeBlock"] pre,
    div[data-testid="stCode"] pre,
    pre {
        background-color: #111827 !important;
        color: #E5E7EB !important;
        border: 1px solid #374151 !important;
        border-radius: 8px !important;
    }
    div[data-testid="stDataFrame"] {
        background: #0B0F19 !important;
        border: 1px solid #1F2937 !important;
        border-radius: 8px !important;
    }
    div[data-testid="stDataFrame"] [data-testid="stTable"],
    div[data-testid="stDataFrame"] [data-testid="stTableStyled"],
    div[data-testid="stDataFrame"] [data-testid="stDataFrameResizable"],
    div[data-testid="stDataFrame"] [data-testid="stDataFrameGlideDataEditor"],
    div[data-testid="stDataFrame"] section,
    div[data-testid="stDataFrame"] canvas {
        background: #0B0F19 !important;
    }
    div[data-testid="stDataFrame"] * {
        color: #E5E7EB !important;
    }
    div[data-testid="stDataFrame"] div[role="columnheader"],
    div[data-testid="stDataFrame"] [class*="header"],
    div[data-testid="stDataFrame"] [class*="Header"] {
        background: #0B1220 !important;
        color: #BFDBFE !important;
        border-color: #1F2937 !important;
    }
    div[data-testid="stDataFrame"] div[role="gridcell"],
    div[data-testid="stDataFrame"] [class*="cell"],
    div[data-testid="stDataFrame"] [class*="Cell"] {
        background: #111827 !important;
        border-color: #1F2937 !important;
    }
    details[data-testid="stExpander"],
    div[data-testid="stExpander"] {
        background: #0F172A !important;
        border: 1px solid #1F2937 !important;
        border-radius: 8px !important;
    }
    details[data-testid="stExpander"] summary,
    div[data-testid="stExpander"] summary,
    div[data-testid="stExpander"] > div:first-child {
        background: #0B1220 !important;
        color: #BFDBFE !important;
        border-radius: 8px !important;
    }
    details[data-testid="stExpander"] > div,
    div[data-testid="stExpander"] > div {
        background: #0F172A !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

BASE_DIR = Path(__file__).parent
DASH_PDF = BASE_DIR / "dashboard automa.pdf"
DASH_PNG = BASE_DIR / "dashboard_automa.png"
LOGO_PNG = BASE_DIR / "logo_automata.png"


def render_brand_header():
    c_logo, c_title = st.columns([1, 4], gap="small")
    with c_logo:
        if LOGO_PNG.exists():
            st.image(str(LOGO_PNG), width=120)
    with c_title:
        st.title("Automa Dados — IA Auditável (MVP)")


render_brand_header()

if not GEMINI_API_KEY:
    st.error("GEMINI_API_KEY não encontrada no .env")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")


def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


conn = get_conn()
cur = conn.cursor()

cur.execute(
    """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    role TEXT,
    pergunta TEXT,
    sql_gerado TEXT,
    tabelas_alvo TEXT,
    status TEXT,
    motivo TEXT,
    created_at TEXT DEFAULT (datetime('now'))
)
"""
)
conn.commit()

# migração leve para quem já tinha tabela antiga
for col, ddl in [
    ("role", "ALTER TABLE audit_log ADD COLUMN role TEXT"),
    ("tabelas_alvo", "ALTER TABLE audit_log ADD COLUMN tabelas_alvo TEXT"),
]:
    try:
        conn.execute(ddl)
        conn.commit()
    except Exception:
        pass


def login(username, senha):
    q = """
    SELECT username, nome, role
    FROM usuarios
    WHERE username = ? AND senha = ? AND ativo = 1
    LIMIT 1
    """
    row = conn.execute(q, (username, senha)).fetchone()
    return row


if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.subheader("Login")
    u = st.text_input("Usuário")
    s = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        row = login(u, s)
        if row:
            st.session_state.user = {"username": row[0], "nome": row[1], "role": row[2]}
            st.success(f"Bem-vindo, {row[1]} ({row[2]})")
            st.rerun()
        else:
            st.error("Usuário/senha inválidos.")
    st.stop()

user = st.session_state.user
audit_actor = (user.get("nome") or user.get("username") or "usuario_desconhecido").strip()
st.caption(f"Logado como: **{user['nome']}** | perfil: **{user['role']}**")

if st.button("Sair"):
    st.session_state.user = None
    st.rerun()

FORBIDDEN = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "ATTACH", "DETACH", "PRAGMA"]


def is_sql_safe(sql: str):
    if not sql:
        return False, "SQL vazio"
    clean = sql.strip().upper()
    if not clean.startswith("SELECT"):
        return False, "Apenas SELECT é permitido"
    for word in FORBIDDEN:
        if re.search(rf"\b{word}\b", clean):
            return False, f"Comando proibido detectado: {word}"
    if ";" in clean[:-1]:
        return False, "Múltiplas instruções não permitidas"
    return True, "OK"


def extract_target_tables(sql: str):
    found = re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)", sql, flags=re.IGNORECASE)
    return sorted(set([t.lower() for t in found]))


# Whitelist explícita por perfil (RBAC)
VIEWER_ALLOWED_TABLES = {
    "dim_tempo",
    "dim_produto",
    "dim_cliente",
    "dim_fornecedor",
    "fato_vendas",
    "fato_compras",
    "fato_logistica",
}

def can_role_access_tables(role: str, tables: list[str]):
    role = (role or "").lower().strip()
    if role == "admin":
        return True, "OK"

    if role == "viewer":
        for t in tables:
            if t not in VIEWER_ALLOWED_TABLES:
                return False, f"Perfil viewer sem acesso à tabela: {t}"
        return True, "OK"

    return False, f"Perfil não reconhecido: {role}"


def log_audit(username, role, pergunta, sql_gerado, tabelas_alvo, status, motivo):
    conn.execute(
        "INSERT INTO audit_log (username, role, pergunta, sql_gerado, tabelas_alvo, status, motivo) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (username, role, pergunta, sql_gerado, tabelas_alvo, status, motivo),
    )
    conn.commit()


def get_schema_text():
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    schema_lines = []
    allowed_tables = [t for t in tables if t.startswith("dim_") or t.startswith("fato_")]
    for t in allowed_tables:
        cols = conn.execute(f"PRAGMA table_info({t})").fetchall()
        col_names = ", ".join([c[1] for c in cols])
        schema_lines.append(f"{t}({col_names})")
    return "\n".join(schema_lines), allowed_tables


def _fmt_num_br(x):
    try:
        return f"{float(x):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    except Exception:
        return x


def style_df(df: pd.DataFrame):
    styler = df.style.set_properties(**{"background-color": "#111827", "color": "#E5E7EB"})
    try:
        styler = styler.hide(axis="index")
    except Exception:
        pass
    return styler


def render_dark_table(df: pd.DataFrame):
    df_view = df.copy()
    for col in df_view.select_dtypes(include="number").columns:
        df_view[col] = df_view[col].map(_fmt_num_br)
    st.markdown("<div style='background:#0B0F19;padding:4px;border:1px solid #1F2937;border-radius:8px;overflow:auto;'>" + style_df(df_view).to_html() + "</div>", unsafe_allow_html=True)


schema_text, allowed_tables = get_schema_text()

SYSTEM_PROMPT = f"""
Você é um gerador de SQL para SQLite.
REGRAS OBRIGATÓRIAS:
- Gere SOMENTE uma query SQL válida.
- A query deve começar com SELECT.
- Nunca gere INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, PRAGMA.
- Use apenas tabelas permitidas abaixo:
{", ".join(allowed_tables)}

Esquema disponível:
{schema_text}

Responda APENAS com SQL puro, sem markdown e sem explicações.
"""

col_main, col_dash = st.columns([1.9, 1.1], gap="large")

with col_main:
    st.subheader("Consulta com IA (Gemini)")
    pergunta = st.text_area("Pergunte sobre os dados (ex.: faturamento por mês, top produtos...)")

    if st.button("Consultar"):
        if not pergunta.strip():
            st.warning("Digite uma pergunta.")
        else:
            try:
                prompt = f"{SYSTEM_PROMPT}\nPergunta do usuário: {pergunta}"
                resp = model.generate_content(prompt)
                sql = resp.text.strip().replace("```sql", "").replace("```", "").strip()

                st.markdown("**SQL gerado:**")
                st.code(sql, language="sql")

                safe, motivo = is_sql_safe(sql)
                tables = extract_target_tables(sql)
                tables_txt = ", ".join(tables) if tables else "(nenhuma identificada)"

                if safe:
                    role_ok, role_motivo = can_role_access_tables(user.get("role", ""), tables)
                    if not role_ok:
                        safe, motivo = False, role_motivo

                if not safe:
                    log_audit(audit_actor, user.get("role", ""), pergunta, sql, tables_txt, "BLOCKED", motivo)
                    st.error(f"Bloqueado: {motivo}")
                else:
                    df = pd.read_sql_query(sql, conn)
                    log_audit(audit_actor, user.get("role", ""), pergunta, sql, tables_txt, "ALLOWED", "OK")
                    st.success("Consulta executada com sucesso.")
                    st.session_state["last_df"] = df
                    render_dark_table(df)

            except Exception as e:
                log_audit(audit_actor, user.get("role", ""), pergunta, "", "", "ERROR", str(e))
                st.error(f"Erro: {e}")

    with st.expander("Ver últimos logs de auditoria"):
        c1, c2, c3 = st.columns([1,1,1])
        with c1:
            status_f = st.selectbox("Status", ["TODOS","ALLOWED","BLOCKED","ERROR"], index=0)
        with c2:
            dias = st.selectbox("Período", [1,3,7,30,9999], index=2)
        with c3:
            limite = st.selectbox("Limite", [30,50,100,300], index=1)

        where = []
        params = []
        if status_f != "TODOS":
            where.append("status = ?")
            params.append(status_f)
        if dias != 9999:
            dt = (datetime.now() - timedelta(days=int(dias))).strftime("%Y-%m-%d %H:%M:%S")
            where.append("created_at >= ?")
            params.append(dt)

        sql_logs = "SELECT id, username, role, pergunta, sql_gerado, tabelas_alvo, status, motivo, created_at FROM audit_log"
        if where:
            sql_logs += " WHERE " + " AND ".join(where)
        sql_logs += f" ORDER BY id DESC LIMIT {int(limite)}"

        logs = pd.read_sql_query(sql_logs, conn, params=params)
        render_dark_table(logs)
        st.download_button("Exportar logs CSV", data=logs.to_csv(index=False).encode("utf-8-sig"), file_name="audit_log_filtrado.csv", mime="text/csv", use_container_width=True)

    if "last_df" in st.session_state and isinstance(st.session_state["last_df"], pd.DataFrame):
        st.download_button("Exportar resultado da consulta CSV", data=st.session_state["last_df"].to_csv(index=False).encode("utf-8-sig"), file_name="resultado_consulta.csv", mime="text/csv", use_container_width=True)

with col_dash:
    st.subheader("Dashboard Gerencial")
    st.caption("Power BI — Faturamento, evolução temporal e top produtos")

    if DASH_PNG.exists():
        st.image(str(DASH_PNG), use_container_width=True)
    elif DASH_PDF.exists():
        pdf_bytes = DASH_PDF.read_bytes()
        b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
        st.markdown(f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="620" type="application/pdf"></iframe>', unsafe_allow_html=True)
        st.download_button("Baixar dashboard (PDF)", data=pdf_bytes, file_name="dashboard_automa.pdf", mime="application/pdf", use_container_width=True)
    else:
        st.info("Arquivo da dashboard não encontrado na pasta do projeto.")
