# Automa Dados • UNINOVE

Aplicativo acadêmico em Streamlit com dados isolados por empresa em SQLite. A VarejMais demonstra vendas e produtos. A ServiFácil também oferece chamados, histórico e SLA em horário útil de São Paulo. Administradores gerenciam usuários e consultam a auditoria da própria empresa. Leitores têm acesso restrito.

## Instalação no Windows

Com Python 3.12 e o repositório clonado, abra um PowerShell na pasta que contém `app.py` e execute:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe preparar_demo.py
.\INICIAR_SISTEMA.bat
```

Se o comando `py` estiver indisponível, substitua a primeira linha por `& 'C:\caminho\para\Python312\python.exe' -m venv .venv`, usando o caminho da sua instalação Python 3.12.

O preparador pede quatro senhas locais com digitação oculta, uma para cada combinação de empresa e login (`admin` ou `viewer`). Use de 12 a 256 caracteres. Ele cria os dois bancos em `dados_empresas` e preserva uma instalação existente. Abra http://127.0.0.1:8501, selecione a empresa e entre com o respectivo login e senha.

## Demonstração

A instalação gera 15.000 vendas fictícias e três chamados. Os valores e nomes da base pública são sintéticos e podem diferir das capturas da apresentação. Para ver **Chamados & SLA** e **Auditoria**, selecione ServiFácil e entre como administrador.

Para consultas reais de IA, configure `GEMINI_API_KEY` nas variáveis de ambiente do usuário do Windows e abra um novo terminal. Opcionalmente, configure `GEMINI_MODEL` para um modelo habilitado na sua conta. O módulo `gemini_sql.py` pede o SQL e `ai_sql.py` valida e executa a consulta autorizada. Dashboards, chamados e testes locais funcionam sem chave.

## Validação e administração

Depois de preparar a demonstração, execute a regressão com bancos descartáveis:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
.\.venv\Scripts\python.exe empresas.py --help
```

O provisionamento de empresas pelo terminal exige um operador autorizado no Windows. As regras da janela de atendimento ficam em `sla.toml`. Mantenha bancos, senhas, chaves e exportações somente no ambiente local.
