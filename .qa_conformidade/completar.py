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
folder=qa/'ambiente_c'
folder.mkdir(exist_ok=True)
img=qa/'imagens';img.mkdir(exist_ok=True)
for f in root.glob('*.py'):
 if not f.name.startswith('test_'):shutil.copyfile(f,folder/f.name)
for f in ['sla.toml','.streamlit/config.toml']:
 (folder/f).parent.mkdir(exist_ok=True);shutil.copyfile(root/f,folder/f)
pwd=secrets.token_urlsafe(25)
with closing(sqlite3.connect(folder/'dados_empresas/varejmais.sqlite')) as db:
 db.execute("UPDATE usuarios SET senha_hash=? WHERE username='admin.demo'",(HASHER.hash(pwd),));db.commit()
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
  data=(qa/'resultado_consulta.csv').read_bytes()
  assert abs(Decimal(list(csv.reader(io.StringIO(data.decode('utf-8-sig'))))[1][0])-Decimal('735290983.60'))<Decimal('.005')
  csv_tab=browser.new_page(viewport={'width':1000,'height':400},device_scale_factor=1.3)
  csv_tab.route('**/resultado_consulta.csv',lambda route:route.fulfill(body=data,content_type='text/plain; charset=utf-8'))
  csv_tab.goto(url+'/resultado_consulta.csv')
  csv_tab.locator('pre').evaluate("(el)=>{el.style.fontSize='26px';el.style.padding='20px'}")
  csv_tab.locator('pre').screenshot(path=str(img/'A7.png'));csv_tab.close()
  login('admin.demo');panel=tab('Auditoria')
  page.get_by_label('Filtrar por login').fill('leitor.demo');page.get_by_label('Filtrar por login').press('Enter')
  def setstatus(status):
   page.get_by_role('combobox',name='Status do evento').click()
   page.get_by_role('option',name=status,exact=True).click()
   page.wait_for_timeout(500)
  setstatus('ALLOWED');shot(5,panel)
finally:
 process.terminate();process.wait(timeout=20)

