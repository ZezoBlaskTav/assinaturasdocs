import os
import io
import resend
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, flash, redirect, url_for
from werkzeug.utils import secure_filename
from supabase import create_client, Client

# Inicialização do aplicativo Flask
app = Flask(__name__)
app.secret_key = "seguranca_sim_camaqua_2026_resend"

# Configuração para o fuso horário de Camaquã/RS (UTC-3)
FUSO_CAMAQUA = timezone(timedelta(hours=-3))

# --- CONFIGURAÇÃO DO RESEND ---
# Substitua 're_seu_codigo_aqui' pela chave que você copiou do site do Resend
resend.api_key = "re_GsXiyW8k_5VJaL7dwKcL9ax6kACES8PPe"

# --- CONFIGURAÇÃO DO BANCO DE DADOS SUPABASE ---
SUPABASE_URL = "https://zlnwqdozhskxoypbznnx.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpsbndxZG96aHNreG95cGJ6bm54Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM3Nzg2MzgsImV4cCI6MjA4OTM1NDYzOH0.2_vycSKILISiHvqhQmHn7m6ikabtdmhB2jWN0jFmbfo"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Pasta temporária para arquivos (compatível com Render/Railway)
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
        print(f"Erro ao buscar histórico: {erro}")
        documentos = []
        
    return render_template('index.html', documentos=documentos)

@app.route('/visualizar/<id_doc>')
def visualizar_documento(id_doc):
    """
    Magic Link: Marca como 'Lido' e mostra as instruções ao produtor rural.
    """
    agora_camaqua = datetime.now(FUSO_CAMAQUA).strftime("%d/%m/%Y %H:%M")
    
    try:
        # Atualiza o status de visualização no banco de dados
        supabase.table("assinaturas").update({
            "status": "Lido",
            "data_leitura": agora_camaqua
        }).eq("id", id_doc).execute()
        
        # Recupera os dados para exibir na tela
        res = supabase.table("assinaturas").select("*").eq("id", id_doc).execute()
        if not res.data:
            return "Erro: Documento não localizado.", 404
            
        return render_template('documento.html', documento=res.data[0])
        
    except Exception as erro:
        return f"Erro técnico ao visualizar: {str(erro)}", 500

@app.route('/enviar', methods=['POST'])
def enviar():
    """
    Processa o formulário de envio e dispara o e-mail através da API do Resend.
    """
    email_destinatario = request.form.get('email')
    arquivo_pdf = request.files.get('documento')

    if not email_destinatario or not arquivo_pdf:
        flash("Preencha todos os campos do formulário.", "warning")
        return redirect(url_for('index'))

    nome_arquivo = secure_filename(arquivo_pdf.filename)
    caminho_local = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
    
    try:
        # 1. Salva o arquivo temporariamente no servidor
        arquivo_pdf.save(caminho_local)

        # 2. Registra a operação no Supabase
        dados_db = {
            "arquivo": nome_arquivo,
            "destinatario": email_destinatario,
            "status": "Aguardando leitura"
        }
        registro = supabase.table("assinaturas").insert(dados_db).execute()
        id_unico = registro.data[0]['id']

        # 3. Gera o link de acesso (URL dinâmica)
        link_acesso = f"{request.host_url.rstrip('/')}/visualizar/{id_unico}"

        # 4. Envio do E-mail oficial via API do Resend
        # Por padrão, o Resend envia de 'onboarding@resend.dev' até você validar seu domínio.
        params = {
            "from": "SIM Camaquã <onboarding@resend.dev>",
            "to": [email_destinatario],
            "subject": f"Assinatura Digital SIM: {nome_arquivo}",
            "html": f"""
            <div style="font-family: Arial; border: 2px solid #004a99; padding: 25px; border-radius: 10px;">
                <h2 style="color: #004a99;">Serviço de Inspeção Municipal</h2>
                <p>Olá, um documento oficial aguarda sua assinatura via <strong>Gov.br</strong>.</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{link_acesso}" style="background-color: #004a99; color: white; padding: 15px 25px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                        VISUALIZAR DOCUMENTO
                    </a>
                </div>
            </div>
            """,
            "attachments": [
                {
                    "filename": nome_arquivo,
                    "content": list(open(caminho_local, "rb").read()),
                }
            ],
        }

        resend.Emails.send(params)
        flash("Documento enviado e registrado com sucesso!", "success")
        
    except Exception as erro:
        print(f"ERRO NO ENVIO: {erro}")
        flash(f"Falha técnica no envio: {str(erro)}", "danger")
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)