# Automa Dados — Entrega Final

## Visão geral

O Automa Dados é uma demonstração local de uma plataforma de análise de dados com IA auditável, apresentada como serviço para empresas clientes. A solução mantém os dados, usuários e registros de auditoria separados por ambiente.

## O que foi entregue

- Dois ambientes isolados: **VarejMais** (varejo) e **ServiFácil** (serviços e suporte técnico).
- Login por ambiente; ao trocar de empresa, a sessão é encerrada.
- Perfis `admin` e `viewer`.
- Painel com indicadores específicos de cada empresa.
- Consulta em linguagem natural com Gemini quando há chave configurada.
- Validação de segurança: somente `SELECT`; comandos de alteração são bloqueados.
- Registro de auditoria por empresa, usuário, perfil, ação, status e data/hora.
- Exportação de resultados e auditoria em CSV.
- Central de chamados da ServiFácil: abertura, prioridade, prazo de SLA, atualização e conclusão.

## Demonstração recomendada

1. Execute `INICIAR_SISTEMA.bat` e abra `http://localhost:8501`.
2. Entre na ServiFácil com uma conta de demonstração autorizada.
3. Mostre o painel: chamados, itens em aberto, SLA vencido e receita mensal.
4. Abra um chamado, selecionando uma prioridade; o prazo de SLA é calculado automaticamente.
5. Atualize o chamado e mostre o registro correspondente na aba Auditoria.
6. Troque para **VarejMais** para evidenciar o isolamento: a sessão é encerrada e o painel mostra somente os dados comerciais daquele cliente.
7. Se a chave Gemini estiver configurada, faça uma consulta permitida e exporte o CSV. Explique que comandos fora de `SELECT` são bloqueados e auditados.

## Acesso de demonstração

Utilize as credenciais fornecidas em canal privado. A auditoria e seu CSV exigem um administrador ativo da empresa.

## Validação realizada em 22/11/2026

- `python -m py_compile app.py`: aprovado.
- Servidor Streamlit: resposta HTTP 200 em `127.0.0.1:8501`.
- Banco da ServiFácil: 2 usuários ativos, 3 chamados e 3 contratos ativos encontrados.

## Limites assumidos

A aplicação é uma demonstração acadêmica local. Os bancos são SQLite e a separação por empresa é feita por arquivos de banco distintos; não é uma implantação em nuvem nem um SaaS de produção. A consulta com IA depende de uma `GEMINI_API_KEY` local e não deve ter a chave compartilhada.

## Chamados e SLA da ServiFácil

O administrador abre um chamado com título, descrição, solicitante, categoria e prioridade. Na central, seleciona o chamado para atribuir ou trocar o responsável, atualizar categoria e prioridade, mudar o status e consultar o histórico. Os estados são Aberto, Em triagem, Em atendimento, Aguardando usuário, Resolvido e Fechado. O fechamento é definitivo. A resolução retira o chamado dos indicadores em aberto. Se voltar ao atendimento antes do fechamento, o prazo original continua valendo.

O leitor acompanha ID, categoria, prioridade, status e datas. No histórico, vê a data e o tipo de movimento. Detalhes, identificação de pessoas e edição ficam restritos a administradores ativos da ServiFácil. A VarejMais não possui central de chamados.

O arquivo `sla.toml` define o início da janela diária de oito horas e a lista opcional de feriados no formato AAAA-MM-DD. A configuração inicial é de segunda a sexta, das 09:00 às 17:00, em America/Sao_Paulo, sem feriados cadastrados. A contagem inicia na abertura ou no próximo horário de atendimento. Urgente recebe 4 horas úteis, Alta 8, Média 16 e Baixa 24. Por exemplo, um chamado urgente aberto sexta às 15:00 vence segunda às 11:00, se segunda for dia útil.

A espera pelo usuário continua consumindo horas de atendimento. Uma mudança de prioridade recalcula o prazo desde a abertura usando o calendário vigente. Alterar o calendário por si só preserva os prazos já gravados. O painel conta como vencidos os chamados ainda em aberto cujo prazo já passou. A data de conclusão indica a resolução ou, em um fechamento direto, o fechamento. O histórico registra separadamente o instante de cada movimento.

Na migração, as datas legadas são interpretadas como hora local. Cada chamado recebe categoria Geral e tem seu prazo recalculado. O estado Concluído passa a Fechado. O histórico guarda o status e o prazo anteriores junto com os novos valores, e mantém os registros preexistentes de auditoria.

## Implantação e administração

VarejMais e ServiFácil mantêm seus arquivos e módulos. Para uma nova empresa, o operador do notebook abre o PowerShell **como administrador**, entra na pasta de trabalho e executa, por exemplo:

```powershell
.\.venv\Scripts\python.exe empresas.py --codigo minha_loja --nome "Minha Loja" --ramo "Varejo" --usuario gestor --nome-admin "Gestor da loja"
```

O terminal solicita a senha inicial duas vezes com entrada oculta. Use pelo menos 12 caracteres. O código identifica o banco e deve começar por uma letra minúscula, ter entre 2 e 40 caracteres e conter somente letras minúsculas, números, hífen ou sublinhado. Um código existente é recusado. A criação usa o esquema comercial vazio, com um administrador inicial e seus próprios registros de implantação. Atualize o Streamlit para selecionar o novo ambiente. Os indicadores comerciais começam zerados até a carga de dados autorizada.

Na aba **Usuários**, um administrador da empresa pode cadastrar contas admin ou viewer, ativar e desativar contas e redefinir senhas. A senha é informada em campo protegido. O sistema conserva o último administrador ativo e invalida as sessões anteriores após redefinição ou mudança de ativação. A auditoria registra o operador ou administrador, a ação e a conta afetada.

A implantação é uma operação local do Windows. Restrinja, pelas permissões do sistema operacional, o acesso à pasta de trabalho e aos backups aos operadores autorizados. Usuários finais acessam apenas o Streamlit. Quem pode editar diretamente um banco SQLite ou o código tem acesso fora do controle da aplicação.

## Primeira resposta e governança

Na ServiFácil, registre a primeira resposta depois de comunicá-la ao solicitante. A aplicação guarda o instante e o prazo vigente nesse momento, sem inferir respostas antigas nem enviar mensagens. A prioridade Urgente corresponde à classificação acadêmica Crítica. O indicador de chamados abertos vencidos continua independente. A auditoria administrativa filtra por login exato e status dentro da empresa ativa. Os contadores de consultas de IA e o CSV respeitam o recorte dos últimos 200 eventos filtrados.
