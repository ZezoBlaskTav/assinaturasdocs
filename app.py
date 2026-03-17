import os
import io
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, flash, redirect, url_for, send_file
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from supabase import create_client, Client

# Inicialização do aplicativo Flask para o SIM Camaquã
app = Flask(__name__)

# Chave de segurança para as mensagens flash e sessões do sistema
app.secret_key = "seguranca_sim_camaqua_2026_oficial"

# Configuração para o fuso horário de Camaquã, Rio Grande do Sul (UTC-3)
FUSO_CAMAQUA = timezone(timedelta(hours=-3))

# --- CONFIGURAÇÃO DA URL OFICIAL DO SISTEMA ---
# Esta URL é essencial para que os links enviados por e-mail funcionem em qualquer lugar
URL_BASE_SISTEMA = "https://assinaturasdocs.onrender.com"

# --- CONFIGURAÇÃO DO BANCO DE DADOS SUPABASE ---
SUPABASE_URL = "https://zlnwqdozhskxoypbznnx.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpsbndxZG96aHNreG95cGJ6bm54Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM3Nzg2MzgsImV4cCI6MjA4OTM1NDYzOH0.2_vycSKILISiHvqhQmHn7m6ikabtdmhB2jWN0jFmbfo"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- CONFIGURAÇÃO DO SERVIDOR DE E-MAIL (SMTP GMAIL) ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'zezoblaskowskitavares@gmail.com' 
app.config['MAIL_PASSWORD'] = 'nfnctuftkozvvhyb' 

mail = Mail(app)

# Configuração da pasta de uploads para armazenamento temporário de documentos PDF
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- ROTAS DO SISTEMA ---

@app.route('/')
def index():
    """
    Exibe o Dashboard principal com o histórico de documentos do SIM.
    Busca os dados diretamente do Supabase ordenados pelos mais recentes.
    """
    try:
        resposta = supabase.table("assinaturas").select("*").order("data_envio", desc=True).execute()
        documentos = resposta.data
    except Exception as erro:
        print(f"Erro ao buscar dados no Supabase: {erro}")
        documentos = []
        
    return render_template('index.html', documentos=documentos)

@app.route('/visualizar/<id_doc>')
def visualizar_documento(id_doc):
    """
    Gatilho de rastreio: Ao abrir este link, o sistema marca 
    automaticamente o status como 'Lido' no banco de dados.
    """
    agora_camaqua = datetime.now(FUSO_CAMAQUA).strftime("%d/%m/%Y %H:%M")
    
    try:
        # Atualiza o status de visualização no Supabase de forma permanente
        supabase.table("assinaturas").update({
            "status": "Lido",
            "data_leitura": agora_camaqua
        }).eq("id", id_doc).execute()
        
        # Recupera os dados do documento para exibir na página de instruções
        resposta = supabase.table("assinaturas").select("*").eq("id", id_doc).execute()
        
        if not resposta.data:
            return "Erro: Documento não localizado.", 404
            
        dados_documento = resposta.data[0]
        return render_template('documento.html', documento=dados_documento)
        
    except Exception as erro:
        print(f"Erro no rastreamento de leitura: {erro}")
        return f"Erro técnico ao processar: {str(erro)}", 500

@app.route('/enviar', methods=['POST'])
def enviar():
    """
    Processa o formulário de envio, grava no banco e dispara o e-mail
    com o link oficial de acesso e o arquivo em anexo.
    """
    email_destinatario = request.form.get('email')
    arquivo_upload = request.files.get('documento')

    if not email_destinatario or not arquivo_upload:
        flash("Preencha o e-mail do destinatário e selecione o PDF.", "warning")
        return redirect(url_for('index'))

    # Salva o arquivo com nome seguro na pasta temporária
    nome_seguro = secure_filename(arquivo_upload.filename)
    caminho_local = os.path.join(app.config['UPLOAD_FOLDER'], nome_seguro)
    arquivo_upload.save(caminho_local)

    try:
        # 1. Registro inicial no banco de dados Supabase para gerar o ID (UUID)
        dados_db = {
            "arquivo": nome_seguro,
            "destinatario": email_destinatario,
            "status": "Aguardando leitura"
        }
        res_db = supabase.table("assinaturas").insert(dados_db).execute()
        id_gerado = res_db.data[0]['id']

        # 2. Gera o Link Oficial de acesso (Magic Link) apontando para o Render
        link_acesso = f"{URL_BASE_SISTEMA}/visualizar/{id_gerado}"

        # 3. Construção do e-mail oficial do SIM Camaquã
        assunto = f"SIM Camaquã - Solicitação de Assinatura: {nome_seguro}"
        msg = Message(assunto,
                      sender=("SIM Camaquã", app.config['MAIL_USERNAME']),
                      recipients=[email_destinatario])
        
        msg.html = f"""
        <div style="font-family: Arial, sans-serif; border: 2px solid #004a99; padding: 30px; border-radius: 12px; max-width: 600px;">
            <h2 style="color: #004a99;">Serviço de Inspeção Municipal - Camaquã/RS</h2>
            <p>Prezado(a), um documento oficial foi disponibilizado para sua assinatura digital via <strong>Gov.br</strong>.</p>
            <p><strong>Documento:</strong> {nome_seguro}</p>
            <div style="text-align: center; margin: 35px 0;">
                <a href="{link_acesso}" style="background-color: #004a99; color: white; padding: 20px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block; font-size: 16px;">
                    VISUALIZAR E BAIXAR DOCUMENTO
                </a>
            </div>
            <p style="font-size: 11px; color: #888; border-top: 1px solid #ddd; padding-top: 15px;">
                Link de segurança: {link_acesso}
            </p>
        </div>
        """
        
        # Anexa o arquivo PDF ao e-mail
        with app.open_resource(caminho_local) as anexo:
            msg.attach(nome_seguro, "application/pdf", anexo.read())

        mail.send(msg)
        flash("Documento enviado e registrado no servidor oficial!", "success")
        
    except Exception as erro:
        flash(f"Erro ao processar envio: {str(erro)}", "danger")
        print(f"Erro técnico detalhado: {erro}")
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    # No Render, este bloco é substituído pelo Gunicorn conforme o Procfile
    app.run(debug=True)