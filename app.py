import os
import io
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, flash, redirect, url_for
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from supabase import create_client, Client

# Inicialização do aplicativo Flask
app = Flask(__name__)

# Chave de segurança para sessões e mensagens flash
app.secret_key = "seguranca_sim_camaqua_2026_oficial"

# Configuração para o fuso horário de Camaquã/RS (UTC-3)
FUSO_CAMAQUA = timezone(timedelta(hours=-3))

# --- CONFIGURAÇÃO DO BANCO DE DADOS SUPABASE ---
# Utilizando as credenciais fornecidas para persistência de dados
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

# Configuração da pasta de uploads para armazenamento temporário de PDFs
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- ROTAS DO SISTEMA ---

@app.route('/')
def index():
    """
    Rota principal que exibe o Dashboard com o histórico de documentos.
    Busca os dados diretamente do Supabase ordenados por data de envio.
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
    Rota de destino do 'Magic Link'. Ao ser acessada, o sistema marca 
    automaticamente o documento como 'Lido' no banco de dados.
    """
    agora_camaqua = datetime.now(FUSO_CAMAQUA).strftime("%d/%m/%Y %H:%M")
    
    try:
        # Atualiza o status de leitura de forma permanente no Supabase
        supabase.table("assinaturas").update({
            "status": "Lido",
            "data_leitura": agora_camaqua
        }).eq("id", id_doc).execute()
        
        # Busca os detalhes do documento para exibir na página de instruções
        resposta = supabase.table("assinaturas").select("*").eq("id", id_doc).execute()
        
        if not resposta.data:
            return "Documento não encontrado no sistema.", 404
            
        documento_dados = resposta.data[0]
        return render_template('documento.html', documento=documento_dados)
        
    except Exception as erro:
        print(f"Erro ao processar visualização: {erro}")
        return f"Erro técnico: {str(erro)}", 500

@app.route('/enviar', methods=['POST'])
def enviar():
    """
    Processa o formulário de envio, registra no banco de dados 
    e dispara o e-mail com o link de acesso monitorado.
    """
    email_destinatario = request.form.get('email')
    arquivo_upload = request.files.get('documento')

    if not email_destinatario or not arquivo_upload:
        flash("Por favor, preencha o e-mail e selecione um arquivo PDF.", "warning")
        return redirect(url_for('index'))

    # Limpeza do nome do arquivo para segurança do servidor
    nome_arquivo = secure_filename(arquivo_upload.filename)
    caminho_arquivo = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
    arquivo_upload.save(caminho_arquivo)

    try:
        # 1. Registro inicial no banco de dados para gerar o ID único (UUID)
        dados_registro = {
            "arquivo": nome_arquivo,
            "destinatario": email_destinatario,
            "status": "Aguardando leitura"
        }
        resultado_banco = supabase.table("assinaturas").insert(dados_registro).execute()
        id_gerado = resultado_banco.data[0]['id']

        # 2. Geração da URL pública para o link de acesso.
        # IMPORTANTE: No Codespaces, a porta 5000 deve estar como "Public" na aba Ports.
        url_base = request.host_url.rstrip('/')
        link_acesso = f"{url_base}/visualizar/{id_gerado}"

        # 3. Construção e envio da mensagem de e-mail
        mensagem = Message("SIM Camaquã - Documento para Assinatura Digital",
                          sender=("SIM Camaquã", app.config['MAIL_USERNAME']),
                          recipients=[email_destinatario])
        
        mensagem.html = f"""
        <div style="font-family: Arial, sans-serif; border: 1px solid #004a99; padding: 25px; border-radius: 10px; max-width: 600px;">
            <h2 style="color: #004a99;">Serviço de Inspeção Municipal - Camaquã</h2>
            <p>Olá, foi disponibilizado um documento oficial para a sua assinatura digital via <strong>Gov.br</strong>.</p>
            <p>Para visualizar as instruções de assinatura e baixar o arquivo, clique no botão abaixo:</p>
            <div style="text-align: center; margin: 35px 0;">
                <a href="{link_acesso}" style="background-color: #004a99; color: white; padding: 18px 30px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                    VISUALIZAR DOCUMENTO AGORA
                </a>
            </div>
            <p style="font-size: 11px; color: #777; border-top: 1px solid #eee; pt: 10px;">
                Se o botão acima não funcionar, copie este endereço no seu navegador: <br>
                {link_acesso}
            </p>
        </div>
        """
        
        # Anexa o arquivo PDF original ao e-mail
        with app.open_resource(caminho_arquivo) as arquivo_anexo:
            mensagem.attach(nome_arquivo, "application/pdf", arquivo_anexo.read())

        mail.send(mensagem)
        flash("Documento enviado e link de monitoramento gerado com sucesso!", "success")
        
    except Exception as erro:
        flash(f"Falha técnica no processo de envio: {str(erro)}", "danger")
        print(f"Erro completo: {erro}")
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    # O modo debug permite ver erros detalhados durante o desenvolvimento no Codespaces
    app.run(debug=True)