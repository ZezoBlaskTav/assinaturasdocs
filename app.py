import os
import io
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, flash, redirect, url_for
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from supabase import create_client, Client

# Inicialização do aplicativo Flask
app = Flask(__name__)

# Chave de segurança para o sistema
app.secret_key = "seguranca_sim_camaqua_2026_oficial"

# Configuração para o fuso horário de Camaquã/RS (UTC-3)
FUSO_CAMAQUA = timezone(timedelta(hours=-3))

# URL OFICIAL DO SISTEMA NO RENDER
URL_BASE_SISTEMA = "https://assinaturasdocs.onrender.com"

# --- CONFIGURAÇÃO DO BANCO DE DADOS SUPABASE ---
SUPABASE_URL = "https://zlnwqdozhskxoypbznnx.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpsbndxZG96aHNreG95cGJ6bm54Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM3Nzg2MzgsImV4cCI6MjA4OTM1NDYzOH0.2_vycSKILISiHvqhQmHn7m6ikabtdmhB2jWN0jFmbfo"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- CONFIGURAÇÃO DE E-MAIL (GMAIL - PORTA 465 SSL) ---
# Mudamos para a porta 465 para evitar o travamento (SIGKILL) que vimos nos logs
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'zezoblaskowskitavares@gmail.com' 
app.config['MAIL_PASSWORD'] = 'nfnctuftkozvvhyb' 
app.config['MAIL_DEFAULT_SENDER'] = ('SIM Camaquã', 'zezoblaskowskitavares@gmail.com')

mail = Mail(app)

# Pasta temporária para processamento de arquivos no Render
UPLOAD_FOLDER = '/tmp'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- ROTAS DO SISTEMA ---

@app.route('/')
def index():
    """
    Exibe o Dashboard com o histórico de documentos vindos do Supabase.
    """
    try:
        resultado = supabase.table("assinaturas").select("*").order("data_envio", desc=True).execute()
        documentos = resultado.data
    except Exception as erro:
        print(f"Erro ao buscar dados: {erro}")
        documentos = []
        
    return render_template('index.html', documentos=documentos)

@app.route('/visualizar/<id_doc>')
def visualizar_documento(id_doc):
    """
    Marca o documento como 'Lido' e exibe instruções ao produtor.
    """
    agora_camaqua = datetime.now(FUSO_CAMAQUA).strftime("%d/%m/%Y %H:%M")
    
    try:
        # Atualiza status no banco de dados
        supabase.table("assinaturas").update({
            "status": "Lido",
            "data_leitura": agora_camaqua
        }).eq("id", id_doc).execute()
        
        # Busca detalhes para exibir na página
        res = supabase.table("assinaturas").select("*").eq("id", id_doc).execute()
        if not res.data:
            return "Documento não encontrado.", 404
            
        return render_template('documento.html', documento=res.data[0])
        
    except Exception as erro:
        return f"Erro ao processar visualização: {str(erro)}", 500

@app.route('/enviar', methods=['POST'])
def enviar():
    """
    Rota que estava dando erro 500. Agora com logs para rastreio.
    """
    email_destinatario = request.form.get('email')
    arquivo_pdf = request.files.get('documento')

    if not email_destinatario or not arquivo_pdf:
        flash("Preencha todos os campos corretamente.", "warning")
        return redirect(url_for('index'))

    nome_arquivo = secure_filename(arquivo_pdf.filename)
    caminho_arquivo = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
    
    try:
        # 1. Salva o arquivo temporariamente
        arquivo_pdf.save(caminho_arquivo)
        print(f"DEBUG: Arquivo {nome_arquivo} salvo em /tmp")

        # 2. Registra no Supabase
        dados_db = {
            "arquivo": nome_arquivo,
            "destinatario": email_destinatario,
            "status": "Aguardando leitura"
        }
        res_db = supabase.table("assinaturas").insert(dados_db).execute()
        id_gerado = res_db.data[0]['id']
        print(f"DEBUG: Registro criado no Supabase com ID: {id_gerado}")

        # 3. Prepara o Link de Acesso
        link_acesso = f"{URL_BASE_SISTEMA}/visualizar/{id_gerado}"

        # 4. Envio do E-mail (A parte que estava travando)
        msg = Message(f"Assinatura Digital - {nome_arquivo}",
                      recipients=[email_destinatario])
        
        msg.html = f"""
        <div style="font-family: Arial; border: 1px solid #004a99; padding: 20px; border-radius: 10px;">
            <h2 style="color: #004a99;">SIM - Camaquã/RS</h2>
            <p>Um documento oficial aguarda sua assinatura digital.</p>
            <div style="text-align: center; margin: 25px 0;">
                <a href="{link_acesso}" style="background-color: #004a99; color: white; padding: 15px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                    VISUALIZAR DOCUMENTO
                </a>
            </div>
        </div>
        """
        
        with app.open_resource(caminho_arquivo) as anexo:
            msg.attach(nome_arquivo, "application/pdf", anexo.read())

        print("DEBUG: Tentando enviar e-mail via porta 465...")
        mail.send(msg)
        print("DEBUG: E-mail enviado com sucesso!")

        flash("Documento enviado e monitorado com sucesso!", "success")
        
    except Exception as erro:
        print(f"ERRO CRÍTICO NO PROCESSO: {erro}")
        flash(f"Erro técnico no envio: {str(erro)}", "danger")
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)git add .