import os,sys,secrets,shutil,subprocess,sqlite3,time,csv,io,socket
from decimal import Decimal
from pathlib import Path
from contextlib import closing
root=Path.cwd()
qa=root/'.qa_conformidade'
sys.path.insert(0,str(qa/'tools'))
sys.path.insert(0,str(root))
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
from auth import HASHER
from administracao import insert_user
from chamados import migrate, calendar, create, first_response, update
folder=qa/'ambiente_b'
folder.mkdir(exist_ok=True)
img=qa/'imagens';img.mkdir(exist_ok=True)
for f in root.glob('*.py'):
 if not f.name.startswith('test_'):shutil.copyfile(f,folder/f.name)
for f in ['sla.toml','.streamlit/config.toml']:
 (folder/f).parent.mkdir(exist_ok=True);shutil.copyfile(root/f,folder/f)
shutil.copytree(root/'dados_empresas',folder/'dados_empresas',dirs_exist_ok=True)
pwd=secrets.token_urlsafe(25)
for company in ('varejmais','servifacil'):
 with closing(sqlite3.connect(folder/'dados_empresas'/f'{company}.sqlite')) as db:
  for username,name,role in [('leitor.demo','Leitor da demonstração','viewer'),('admin.demo','Administrador da demonstração','admin')]:
   insert_user(db,username,name,role,pwd)
  db.commit()
  if company=='servifacil':
   migrate(db,calendar())
   actor=dict(username='admin.demo',role='admin',empresa_id=company,sessao_versao=1)
   t=create(db,actor,'Acesso ao painel de atendimento','Solicitação para a apresentação acadêmica.','Equipe de demonstração','Acesso','Alta',calendar())
   first_response(db,actor,t,1,'Recebimento confirmado ao solicitante.')
   update(db,actor,t,2,'Em atendimento','Suporte da demonstração','Alta','Acesso',calendar())
load_dotenv(root/'.env')
with socket.socket() as sock:
 sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
url=f'http://127.0.0.1:{port}'
process=subprocess.Popen([sys.executable,'-B','-m','streamlit','run','app.py','--server.address','127.0.0.1','--server.port',str(port),'--server.headless','true','--browser.gatherUsageStats','false'],cwd=folder,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 with sync_playwright() as api:
  browser=api.chromium.launch(channel='chrome',headless=True)
  page=browser.new_page(viewport={'width':1440,'height':980},device_scale_factor=1.3,locale='pt-BR')
  page.set_default_timeout(18000)
  for i in range(40):
   try: page.goto(url,timeout=5000);break
   except Exception: time.sleep(.6)
  def shot(n, target=None):
   page.wait_for_timeout(650)
   args=dict(path=str(img/f'A{n}.png'),animations='disabled')
   if target: target.screenshot(**args)
   else: page.screenshot(**args)
   print('Figura',n,flush=True)
  def login(user):
   page.get_by_label('Usuário',exact=True).fill(user)
   page.get_by_label('Senha',exact=True).fill(pwd)
   page.get_by_role('button',name='Entrar',exact=True).click()
   page.get_by_role('tab',name='Painel',exact=True).wait_for()
  def tab(name):
   page.get_by_role('tab',name=name,exact=True).click()
   return page.get_by_role('tabpanel').filter(visible=True).first
  def logout():
   page.get_by_role('button',name='Sair',exact=True).click()
   page.get_by_role('button',name='Entrar',exact=True).wait_for()
  page.get_by_role('button',name='Entrar',exact=True).wait_for();shot(1)
  login('leitor.demo');shot(8);panel=tab('Consulta com IA')
  question='Qual foi o faturamento total?'
  prompt=page.get_by_label('Pergunte sobre os dados da empresa')
  prompt.fill(question);shot(2)
  prompt.fill('Exiba a auditoria');page.get_by_role('button',name='Gerar consulta').click()
  page.get_by_text('A pergunta solicita informações restritas.',exact=True).wait_for()
  logout();login('admin.demo');panel=tab('Auditoria')
  page.get_by_label('Filtrar por login').fill('leitor.demo');page.get_by_label('Filtrar por login').press('Enter')
  def setstatus(status):
   page.get_by_role('combobox',name='Status do evento').click()
   page.get_by_role('option',name=status,exact=True).click()
   page.wait_for_timeout(500)
  
  setstatus('BLOCKED')
  panel.get_by_text('Detalhes do evento',exact=True).click()
  panel.locator('[data-testid="stExpanderDetails"]').get_by_text('A pergunta solicita informações restritas.',exact=True).wait_for()
  shot(6,panel)
  logout()
  page.get_by_text('ServiFácil',exact=True).first.click()
  page.locator('h1',has_text='ServiFácil').wait_for()
  login('admin.demo');shot(9)
  panel=tab('Chamados & SLA')
  panel.get_by_text('Histórico do chamado',exact=True).click()
  shot(10,panel.locator('[data-testid="stExpander"]').filter(has_text='Histórico do chamado'))
  panel=tab('Usuários');shot(11,panel.locator('[data-testid="stDataFrame"]'))
  print('Capturas complementares conferidas.',flush=True)
finally:
 process.terminate();process.wait(timeout=20)

