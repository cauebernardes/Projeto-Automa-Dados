AUTOMA DADOS | Demonstração local da UNINOVE

Instalação no Windows
Extraia o ZIP inteiro para uma pasta gravável e abra o PowerShell nessa pasta.
Use Python 3.12 de 64 bits com venv e pip. Para criar o ambiente e instalar as dependências uma vez:

    py -3.12 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    .\.venv\Scripts\python.exe -m pip check

Caso o iniciador py não esteja disponível, use o caminho do python.exe 3.12 no primeiro comando. Dê duplo clique em INICIAR_SISTEMA.bat e acesse http://127.0.0.1:8501. Para encerrar, pressione Ctrl+C na janela do servidor. Cada instalação usa seus próprios arquivos SQLite em dados_empresas. projeto.sqlite é o modelo legado da VarejMais.

Configuração do Gemini
Os painéis e demais módulos funcionam sem chave. Para habilitar as consultas em linguagem natural, defina GEMINI_API_KEY nas variáveis de ambiente do usuário do Windows, ou crie um arquivo local chamado .env ao lado de app.py com uma linha GEMINI_API_KEY= seguida do valor privado. Abra um novo terminal e reinicie o aplicativo. A variável do processo tem precedência sobre o arquivo. Guarde a chave no notebook e exclua o .env de qualquer distribuição.
O SDK é google-genai. O modelo padrão é gemini-3.6-flash. Se a conta usar outro modelo compatível com generateContent e JSON estruturado, configure GEMINI_MODEL localmente. O serviço recebe a pergunta, as regras de cálculo e o esquema autorizado. Os resultados e as linhas dos bancos são processados no notebook.

Roteiro de apresentação
1. Entre com as credenciais de demonstração fornecidas em canal privado. Os bancos contêm hashes Argon2id.
2. Na VarejMais, mostre vendas, faturamento e produtos. Com Gemini configurado, pergunte pelo faturamento total, pelos cinco produtos mais vendidos e pela quantidade de vendas. Confira a tabela e exporte o CSV.
3. Troque para ServiFácil e faça novo login. Pergunte pelos chamados em aberto, pelo SLA vencido e pelas prioridades. Abertos excluem resolvidos e fechados. Os prazos seguem a hora local de São Paulo.
4. Demonstre o histórico de um chamado. Compare a visão de leitor e de administrador. Na conta administrativa, confira a auditoria de uma consulta permitida e uma bloqueada e mostre a aba Usuários. Use cópias descartáveis para ensaiar alterações.
5. Para implantar uma nova empresa, siga entrega_final/README_ENTREGA_FINAL.md. O comando exige PowerShell elevado e entrada interativa da senha.
6. Para repetir os testes locais, execute .\.venv\Scripts\python.exe -B -m unittest discover -v. O teste Gemini usa transporte HTTP simulado e não requer chave. A confirmação do serviço externo exige executar as perguntas na aba Consulta com IA com uma chave habilitada.
