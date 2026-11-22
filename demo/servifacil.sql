CREATE TABLE audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, empresa TEXT NOT NULL, username TEXT,
        role TEXT, acao TEXT, pergunta TEXT, sql_gerado TEXT, tabelas_alvo TEXT,
        status TEXT, motivo TEXT, created_at TEXT DEFAULT (datetime('now'))
    );

CREATE TABLE chamado_historico (
            id INTEGER PRIMARY KEY, chamado_id INTEGER NOT NULL REFERENCES chamados(id),
            data_local TEXT NOT NULL, usuario TEXT NOT NULL, acao TEXT NOT NULL, detalhes TEXT NOT NULL);

CREATE TABLE chamados (
      id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT NOT NULL, descricao TEXT,
      solicitante TEXT NOT NULL, prioridade TEXT NOT NULL, status TEXT NOT NULL,
      responsavel TEXT, aberto_em TEXT NOT NULL, prazo_sla TEXT NOT NULL,
      concluido_em TEXT
    , categoria TEXT NOT NULL DEFAULT 'Geral', versao INTEGER NOT NULL DEFAULT 1, primeira_resposta_em TEXT, prazo_primeira_resposta TEXT, resposta_legada INTEGER NOT NULL DEFAULT 0);

CREATE TABLE contratos (
      id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT NOT NULL, plano TEXT NOT NULL,
      valor_mensal REAL NOT NULL, status TEXT NOT NULL
    );

CREATE TABLE usuarios (
      id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
      nome TEXT NOT NULL, senha_hash TEXT NOT NULL, role TEXT NOT NULL,
      ativo INTEGER NOT NULL DEFAULT 1, created_at TEXT DEFAULT (datetime('now'))
    , sessao_versao INTEGER NOT NULL DEFAULT 1);

CREATE INDEX historico_por_chamado ON chamado_historico(chamado_id,id);
