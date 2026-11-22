CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    pergunta TEXT,
    sql_gerado TEXT,
    status TEXT,          -- ALLOWED / BLOCKED / ERROR
    motivo TEXT,
    created_at TEXT DEFAULT (datetime('now'))
, role TEXT, tabelas_alvo TEXT, empresa TEXT, acao TEXT);

CREATE TABLE "dim_cargo" (
  "id_cargo" INTEGER,
  "id_departamento" INTEGER,
  "nivel_escolaridade_min" INTEGER,
  "nome_cargo" TEXT,
  "salario_base" INTEGER,
  PRIMARY KEY("id_cargo")
);

CREATE TABLE "dim_centro_custo" (
  "id_centro_custo" INTEGER,
  "id_departamento_principal" INTEGER,
  "nome_centro_custo" TEXT,
  PRIMARY KEY("id_centro_custo")
);

CREATE TABLE "dim_cliente" (
  "estado" TEXT,
  "id_cliente" INTEGER,
  "nome_cliente" TEXT,
  "setor" TEXT,
  PRIMARY KEY("id_cliente")
);

CREATE TABLE "dim_departamento" (
  "id_departamento" INTEGER,
  "nome_departamento" TEXT,
  PRIMARY KEY("id_departamento")
);

CREATE TABLE "dim_fornecedor" (
  "estado" TEXT,
  "id_fornecedor" INTEGER,
  "material_principal" TEXT,
  "nome_fornecedor" TEXT,
  PRIMARY KEY("id_fornecedor")
);

CREATE TABLE "dim_funcionario" (
  "Beneficio_VR" TEXT,
  "Beneficio_VT" TEXT,
  "Setor" TEXT,
  "data_contratacao" TEXT,
  "data_demissao" TEXT,
  "data_nascimento" TEXT,
  "escolaridade" TEXT,
  "estado_civil" TEXT,
  "estado_nascenca" TEXT,
  "id_cargo" INTEGER,
  "id_departamento" INTEGER,
  "id_funcionario" INTEGER,
  "nome" TEXT,
  "salario_atual" REAL,
  "sobrenome" TEXT,
  PRIMARY KEY("id_funcionario")
);

CREATE TABLE "dim_produto" (
  "categoria" TEXT,
  "custo_producao" REAL,
  "id_produto" INTEGER,
  "nome_produto" TEXT,
  "preco_venda" REAL,
  PRIMARY KEY("id_produto")
);

CREATE TABLE "dim_projeto" (
  "id_gerente_projeto" INTEGER,
  "id_projeto" INTEGER,
  "nome_projeto" TEXT,
  "status" TEXT,
  PRIMARY KEY("id_projeto")
);

CREATE TABLE "dim_tempo" (
  "ano" INTEGER,
  "data_completa" TEXT,
  "dia" INTEGER,
  "dia_semana" TEXT,
  "id_data" INTEGER,
  "mes" INTEGER,
  "nome_mes" TEXT,
  "trimestre" INTEGER,
  PRIMARY KEY("id_data")
);

CREATE TABLE "fato_compras" (
  "custo_total" REAL,
  "id_compra" INTEGER,
  "id_comprador" INTEGER,
  "id_data" INTEGER,
  "id_fornecedor" INTEGER
);

CREATE TABLE "fato_engenharia" (
  "horas_alocadas" INTEGER,
  "id_alocacao" INTEGER,
  "id_funcionario" INTEGER,
  "id_projeto" INTEGER,
  "mes_referencia" TEXT
);

CREATE TABLE "fato_financeiro" (
  "id_centro_custo" INTEGER,
  "id_data" INTEGER,
  "id_lancamento" INTEGER,
  "id_projeto" REAL,
  "tipo_lancamento" TEXT,
  "valor" REAL
);

CREATE TABLE "fato_logistica" (
  "custo_frete" REAL,
  "id_data_entrega_prevista" REAL,
  "id_data_saida" REAL,
  "id_venda" REAL,
  "status" TEXT
);

CREATE TABLE "fato_producao" (
  "custo_real_producao" REAL,
  "horas_parada" INTEGER,
  "horas_produzindo" INTEGER,
  "id_data_fim" INTEGER,
  "id_data_inicio" INTEGER,
  "id_operador" INTEGER,
  "id_ordem_producao" INTEGER,
  "id_produto" INTEGER,
  "ocorrencia" TEXT,
  "quantidade_produzida" INTEGER
);

CREATE TABLE "fato_rh" (
  "ano" INTEGER,
  "avaliacao_individual" REAL,
  "horas_extras_mes" INTEGER,
  "id_data" INTEGER,
  "id_fato_rh" TEXT,
  "id_funcionario" INTEGER,
  "mes" INTEGER
);

CREATE TABLE "fato_vendas" (
  "id_cliente" INTEGER,
  "id_data" INTEGER,
  "id_produto" INTEGER,
  "id_venda" INTEGER,
  "id_vendedor" INTEGER,
  "preco_unitario" REAL,
  "quantidade" INTEGER,
  "valor_total" REAL
);

CREATE TABLE usuarios (
id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT NOT NULL UNIQUE,
nome TEXT NOT NULL,
senha_hash TEXT NOT NULL,
role TEXT NOT NULL CHECK(role IN ('admin','analista','viewer')),
ativo INTEGER NOT NULL DEFAULT 1,
created_at TEXT NOT NULL DEFAULT (datetime('now'))
, sessao_versao INTEGER NOT NULL DEFAULT 1);

CREATE INDEX idx_dim_cargo_id_cargo ON "dim_cargo"("id_cargo");

CREATE INDEX idx_dim_centro_custo_id_centro_custo ON "dim_centro_custo"("id_centro_custo");

CREATE INDEX idx_dim_cliente_id_cliente ON "dim_cliente"("id_cliente");

CREATE INDEX idx_dim_departamento_id_departamento ON "dim_departamento"("id_departamento");

CREATE INDEX idx_dim_fornecedor_id_fornecedor ON "dim_fornecedor"("id_fornecedor");

CREATE INDEX idx_dim_funcionario_id_funcionario ON "dim_funcionario"("id_funcionario");

CREATE INDEX idx_dim_produto_id_produto ON "dim_produto"("id_produto");

CREATE INDEX idx_dim_projeto_id_projeto ON "dim_projeto"("id_projeto");

CREATE INDEX idx_dim_tempo_id_data ON "dim_tempo"("id_data");
