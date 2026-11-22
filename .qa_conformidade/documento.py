from docx import Document
from docx.shared import Cm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from PIL import Image
from pathlib import Path
root=Path.cwd()
src=Path.home()/'Downloads/Automa_Dados_UNINOVE_Documentacao_Consolidada_Para_Prints.docx'
dest=root/'entrega_final/Automa_Dados_UNINOVE_Documentacao_Revisada.docx'
d=Document(src)
def revise(p,text):
 if p.runs:
  p.runs[0].text=text
  for r in p.runs[1:]:r.text=''
 else:p.add_run(text)
def cell(t,row,col,text): revise(d.tables[t].cell(row,col).paragraphs[0],text)
cell(2,2,1,'O operador implanta a empresa por comando local em terminal Windows elevado, com banco comercial vazio e administrador inicial. O administrador cadastra e gerencia os usuários da própria empresa no Streamlit.')
cell(2,3,2,'O administrador seleciona a empresa ao entrar e filtra os eventos por login e status. A tela e o CSV usam os mesmos filtros. O motivo acompanha bloqueios e erros.')
cell(6,5,2,'Os painéis exibem indicadores gerenciais. Os resultados das consultas e os registros de auditoria autorizados podem ser exportados em CSV.')
cell(11,1,0,'Crítica (Urgente na tela)')
p=d.paragraphs
revise(p[136],'O SLA de primeira resposta mede se o atendimento inicial foi comunicado ao solicitante até o prazo da prioridade. O administrador registra a comunicação no chamado e o sistema guarda o horário e o prazo vigente. Uma mudança posterior de prioridade não altera essa comparação. O horário de referência é o de São Paulo e a janela padrão vai das 9h às 17h em dias úteis. Sábados, domingos e feriados cadastrados ficam fora da contagem.')
revise(p[138],'O chamado passa pelos estados Aberto, Em triagem, Em atendimento, Aguardando usuário, Resolvido e Fechado. A categoria, a descrição, o solicitante, o responsável, as datas e o histórico pertencem ao ambiente autenticado da ServiFácil. Os prazos são quatro horas úteis para Urgente (nível crítico), oito para Alta, dezesseis para Média e vinte e quatro para Baixa. O painel conta os chamados em aberto após o prazo. Na central, a situação da primeira resposta é mostrada separadamente. Registros antigos sem horário comprovado não recebem uma resposta retroativa.')
cell(13,0,1,'Indicadores disponíveis e propostos')
cell(13,1,1,'Disponíveis no painel: vendas, faturamento, ticket médio, clientes e oito produtos por faturamento. Propostos: giro de estoque, itens abaixo do mínimo e vendas por canal.')
cell(13,2,1,'Disponíveis: chamados em aberto, vencidos, por prioridade e receita mensal de contratos ativos. A central exibe a situação da primeira resposta. Propostos: produtividade técnica, renovação de contratos e inadimplência.')
cell(13,3,1,'A auditoria mostra consultas de IA permitidas, bloqueadas e com erro entre os últimos 200 eventos selecionados. Há filtros por login e status na empresa ativa.')
revise(p[148],'Os números dos painéis vêm dos bancos demonstrativos da empresa selecionada. Na VarejMais, o ranking do painel ordena produtos por faturamento; uma consulta sobre os mais vendidos pode ordená-los por unidades. Na ServiFácil, um chamado pode ter recebido resposta no prazo e continuar aberto após seu vencimento. Na auditoria, o administrador confere os contadores no recorte exibido e pode exportar os eventos filtrados.')
revise(p[165],'As figuras foram capturadas na versão de entrega em uma cópia isolada dos bancos demonstrativos. Contas e um chamado de demonstração foram criados nessa cópia. A sequência A.2 a A.4 e o CSV da figura A.7 correspondem à mesma consulta real ao modelo Gemini 3.1 Flash-Lite, selecionado para esta demonstração após indisponibilidade do modelo padrão Gemini 3.6 Flash. Nenhuma senha ou chave de API integra as capturas.')
oldrels=[]
for para in p[166:]:
 oldrels.extend(el.get(qn('r:embed')) for el in para._p.xpath('.//a:blip'))
 para._element.getparent().remove(para._element)
for rel in oldrels:d.part.drop_rel(rel)
groups={1:'Acesso por empresa',2:'Consulta e resultado',5:'Auditoria de consultas',6:'Bloqueio e exportação',8:'Painel comercial',9:'Painel de atendimento',10:'Histórico de atendimento e administração'}
caps=['Acesso à VarejMais com os campos de credenciais vazios.','Pergunta sobre o faturamento total no ambiente VarejMais.','SQL proposto pelo Gemini para a pergunta da figura A.2.','Resultado da leitura autorizada no banco de vendas.','Auditoria da VarejMais filtrada pelo login de demonstração e pelo status permitido.','Bloqueio de acesso à auditoria pelo leitor e justificativa do evento.','Conteúdo do arquivo CSV baixado após a consulta da figura A.2, aberto como texto.','Indicadores da VarejMais e ranking por faturamento.','Indicadores da ServiFácil na cópia utilizada para a demonstração.','Histórico com abertura, primeira resposta e movimentações do chamado.','Administração de contas do ambiente ServiFácil.']
for i,title in enumerate(caps,1):
 if i in groups:
  h=d.add_paragraph(groups[i],style='Heading 2')
  h.paragraph_format.page_break_before=i!=1
 if i==1: desc=None
 elif i==5: desc='A empresa delimita o banco consultado. O login e o status refinam a lista de eventos da auditoria.'
 elif i==8: desc='O ranking deste painel usa o valor das vendas. A quantidade de unidades é outra medida e pode produzir outra ordem.'
 elif i==9: desc='O total inclui o chamado de demonstração criado para registrar as movimentações da figura A.10.'
 else:desc=None
 if desc:d.add_paragraph(desc)
 im=root/'.qa_conformidade/imagens'/f'A{i}.png'
 with Image.open(im) as pic: w,h=pic.size
 para=d.add_paragraph();para.alignment=WD_ALIGN_PARAGRAPH.CENTER
 para.paragraph_format.keep_with_next=True;para.paragraph_format.first_line_indent=Cm(0)
 para.add_run().add_picture(str(im),width=Cm(min(15.7,14*w/h)))
 cap=d.add_paragraph(f'Figura A.{i} — {title}',style='CaptionPlain');cap.paragraph_format.keep_with_next=True
 d.add_paragraph('Fonte: elaboração própria (2026).',style='CaptionPlain')
for row in d.tables[2].rows:
 for c in row.cells:
  for para in c.paragraphs:
   para.paragraph_format.space_after=Pt(2)
   para.paragraph_format.space_before=Pt(0)
   para.paragraph_format.line_spacing=1.0
for para in d.paragraphs[:164]:
 if para._p.xpath('.//w:drawing'):
  para.paragraph_format.keep_with_next=True
for shape in list(d.inline_shapes)[:3]:
 ratio=.82
 shape.width=int(shape.width*ratio);shape.height=int(shape.height*ratio)
d.save(dest)
print(dest)

