import os
import io
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, flash, redirect, url_for
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from supabase import create_client, Client

# Inicialização do Flask
app = Flask(__name__)
app.secret_key = "seguranca_sim_camaqua_2026_oficial"

# Fuso horário de Camaquã/RS (UTC-3)
FUSO_CAMAQUA = timezone(timedelta(hours=-3))

# URL OFICIAL DO SEU SISTEMA NO RENDER
URL_BASE_SISTEMA = "https://assinaturasdocs.onrender.com"

# --- CONFIGURAÇÃO DO BANCO DE DADOS SUPABASE ---
SUPABASE_URL = "https://zlnwqdozhskxoypbznnx.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpsbndxZG96aHNreG95cGJ6bm54Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM3Nzg2MzgsImV4cCI6MjA4OTM1NDYzOH0.2_vycSKILISiHvqhQmHn7m6ikabtdmhB2jWN0jFmbfo"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- CONFIGURAÇÃO DE E-MAIL (GMAIL - PORTA 465 SSL) ---
# Usamos a porta 465 com SSL para maior estabilidade no servidor Render
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'zezoblaskowskitavares@gmail.com' 
app.config['MAIL_PASSWORD'] = 'nfnctuftkozvvhyb' 
app.config['MAIL_DEFAULT_SENDER'] = ('SIM Camaquã', 'zezoblaskowskitavares@gmail.com')

mail = Mail(app)

# Pasta temporária para arquivos no servidor
UPLOAD_FOLDER = '/tmp'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- ROTAS ---

@app.route('/')
def index():
    try:
        resposta = supabase.table("assinaturas").select("*").order("data_envio", desc=True).execute()
        documentos = resposta.data
    except Exception as e:
        print(f"Erro ao buscar dados: {e}")
        documentos = []
    return render_template('index.html', documentos=documentos)

@app.route('/visualizar/<id_doc>')
def visualizar_documento(id_doc):
    agora = datetime.now(FUSO_CAMAQUA).strftime("%d/%m/%Y %H:%M")
    try:
        # Marca como lido no banco
        supabase.table("assinaturas").update({"status": "Lido", "data_leitura": agora}).eq("id", id_doc).execute()
        
        # Busca dados do documento
        res = supabase.table("assinaturas").select("*").eq("id", id_doc).execute()
        if not res.data:
            return "Documento não encontrado.", 404
        return render_template('documento.html', documento=res.data[0])
    except Exception as e:
        return f"Erro técnico: {str(e)}", 500

@app.route('/enviar', methods=['POST'])
def enviar():
    email_dest = request.form.get('email')
    arq = request.files.get('documento')

    if not email_dest or not arq:
        flash("Preencha todos os campos.", "warning")
        return redirect(url_for('index'))

    nome_arquivo = secure_filename(arq.filename)
    caminho_local = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
    
    try:
        # 1. Salva o PDF temporariamente
        arq.save(caminho_local)

        # 2. Registra no Supabase
        dados = {"arquivo": nome_arquivo, "destinatario": email_dest, "status": "Aguardando leitura"}
        res_db = supabase.table("assinaturas").insert(dados).execute()
        id_gerado = res_db.data[0]['id']

        # 3. Prepara o Link de Acesso Oficial
        link_acesso = f"{URL_BASE_SISTEMA}/visualizar/{id_gerado}"

        # 4. Envia o E-mail
        msg = Message(f"Assinatura Digital - {nome_arquivo}", recipients=[email_dest])
        msg.html = f"""
        <div style="font-family: Arial; border: 1px solid #004a99; padding: 20px; border-radius: 10px;">
            <h2 style="color: #004a99;">Serviço de Inspeção Municipal</h2>
            <p>Documento oficial disponível para assinatura via <strong>Gov.br</strong>.</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{link_acesso}" style="background-color: #004a99; color: white; padding: 15px 25px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
                    VISUALIZAR E BAIXAR
                </a>
            </div>
            <p style="font-size: 11px; color: #777;">Link de segurança: {link_acesso}</p>
        </div>
        """
        
        with app.open_resource(caminho_local) as anexo:
            msg.attach(nome_arquivo, "application/pdf", anexo.read())

        mail.send(msg)
        flash("Documento enviado com sucesso!", "success")
        
    except Exception as erro:
        print(f"ERRO NO ENVIO: {erro}")
        flash(f"Falha técnica: {str(erro)}", "danger")
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)