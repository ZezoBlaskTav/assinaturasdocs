import os
import io
import socket
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, flash, redirect, url_for
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from supabase import create_client, Client

# Inicialização do aplicativo
app = Flask(__name__)
app.secret_key = "seguranca_sim_camaqua_2026_final"

# Fuso horário oficial de Camaquã/RS (UTC-3)
FUSO_CAMAQUA = timezone(timedelta(hours=-3))

# URL DEFINITIVA DO SISTEMA NO RENDER
URL_BASE_SISTEMA = "https://assinaturasdocs.onrender.com"

# --- CONFIGURAÇÃO DO BANCO DE DADOS SUPABASE ---
SUPABASE_URL = "https://zlnwqdozhskxoypbznnx.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpsbndxZG96aHNreG95cGJ6bm54Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM3Nzg2MzgsImV4cCI6MjA4OTM1NDYzOH0.2_vycSKILISiHvqhQmHn7m6ikabtdmhB2jWN0jFmbfo"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- CONFIGURAÇÃO DE E-MAIL (GMAIL - PORTA 587 COM TIMEOUT) ---
# Aumentamos a tolerância da rede para evitar o erro SIGKILL visto nos logs
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'zezoblaskowskitavares@gmail.com' 
app.config['MAIL_PASSWORD'] = 'nfnctuftkozvvhyb' 
app.config['MAIL_DEFAULT_SENDER'] = ('SIM Camaquã', 'zezoblaskowskitavares@gmail.com')

# Definimos um tempo limite de conexão de 10 segundos para não travar o worker
socket.setdefaulttimeout(10)

mail = Mail(app)

# Pasta temporária padrão para sistemas Linux (Render)
UPLOAD_FOLDER = '/tmp'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- ROTAS DO SISTEMA ---

@app.route('/')
def index():
    """
    Dashboard principal. Busca histórico no Supabase.
    """
    try:
        resultado = supabase.table("assinaturas").select("*").order("data_envio", desc=True).execute()
        documentos = resultado.data
    except Exception as erro:
        print(f"Erro de conexão com banco: {erro}")
        documentos = []
    return render_template('index.html', documentos=documentos)

@app.route('/visualizar/<id_doc>')
def visualizar_documento(id_doc):
    """
    Link de rastreio. Marca como lido e exibe instruções.
    """
    agora = datetime.now(FUSO_CAMAQUA).strftime("%d/%m/%Y %H:%M")
    try:
        supabase.table("assinaturas").update({"status": "Lido", "data_leitura": agora}).eq("id", id_doc).execute()
        res = supabase.table("assinaturas").select("*").eq("id", id_doc).execute()
        if not res.data:
            return "Documento inexistente.", 404
        return render_template('documento.html', documento=res.data[0])
    except Exception as erro:
        return f"Erro ao visualizar: {str(erro)}", 500

@app.route('/enviar', methods=['POST'])
def enviar():
    """
    Processa o envio e o e-mail. Agora com logs de progresso no terminal do Render.
    """
    email_destinatario = request.form.get('email')
    arquivo_pdf = request.files.get('documento')

    if not email_destinatario or not arquivo_pdf:
        flash("Preencha todos os campos do formulário.", "warning")
        return redirect(url_for('index'))

    nome_arquivo = secure_filename(arquivo_pdf.filename)
    caminho_local = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
    
    try:
        # 1. Salva o arquivo no diretório temporário
        arquivo_pdf.save(caminho_local)
        print(f"DEBUG: Arquivo salvo com sucesso em {caminho_local}")

        # 2. Registra no Supabase e obtém o ID
        dados_db = {
            "arquivo": nome_arquivo,
            "destinatario": email_destinatario,
            "status": "Aguardando leitura"
        }
        registro = supabase.table("assinaturas").insert(dados_db).execute()
        id_unico = registro.data[0]['id']
        print(f"DEBUG: Registro criado no banco de dados. ID: {id_unico}")

        # 3. Prepara o Magic Link
        link_acesso = f"{URL_BASE_SISTEMA}/visualizar/{id_unico}"

        # 4. Envia o e-mail com anexo
        mensagem = Message(f"Assinatura Digital SIM: {nome_arquivo}",
                          recipients=[email_destinatario])
        
        mensagem.html = f"""
        <div style="font-family: Arial; border: 1px solid #004a99; padding: 20px; border-radius: 10px;">
            <h2 style="color: #004a99;">SIM Camaquã - Notificação</h2>
            <p>Um documento oficial aguarda sua assinatura digital.</p>
            <div style="text-align: center; margin: 25px 0;">
                <a href="{link_acesso}" style="background-color: #004a99; color: white; padding: 15px 25px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
                    ACESSAR E ASSINAR
                </a>
            </div>
            <p style="font-size: 11px; color: #777;">Link direto: {link_acesso}</p>
        </div>
        """
        
        with app.open_resource(caminho_local) as anexo_fp:
            mensagem.attach(nome_arquivo, "application/pdf", anexo_fp.read())

        print("DEBUG: Iniciando tentativa de envio de e-mail...")
        mail.send(mensagem)
        print("DEBUG: E-mail enviado com sucesso!")

        flash("Enviado e registrado com sucesso!", "success")
        
    except Exception as erro:
        print(f"ERRO FATAL NO PROCESSO: {erro}")
        flash(f"Ocorreu um erro no servidor: {str(erro)}", "danger")
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Em produção, o Render utiliza o Gunicorn para rodar o app
    app.run(debug=True)