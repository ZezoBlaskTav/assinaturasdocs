import os
from flask import Flask, render_template, request, flash, redirect
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename

app = Flask(__name__)
# A chave secreta é necessária para as mensagens de alerta (flash)
app.secret_key = "uma_chave_muito_segura_e_secreta"

# Configuração da pasta de upload
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Cria a pasta 'uploads' se ela não existir
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- CONFIGURAÇÃO DE E-MAIL (GMAIL) ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'zezoblaskowskitavares@gmail.com' # Troque pelo seu e-mail
app.config['MAIL_PASSWORD'] = 'nfnctuftkozvvhyb'    # Troque pela senha de app do Google

mail = Mail(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/enviar', methods=['POST'])
def enviar():
    email_destinatario = request.form.get('email')
    arquivo = request.files.get('documento')

    # Validação simples
    if not email_destinatario or not arquivo:
        flash("Por favor, preencha o e-mail e selecione um arquivo PDF.", "warning")
        return redirect('/')

    if arquivo.filename == '':
        flash("Nenhum arquivo selecionado.", "warning")
        return redirect('/')

    # Salva o arquivo com segurança
    filename = secure_filename(arquivo.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    arquivo.save(filepath)

    # Montagem do e-mail
    try:
        msg = Message("Solicitação de Assinatura Digital (Gov.br)",
                      sender=app.config['MAIL_USERNAME'],
                      recipients=[email_destinatario])
        
        msg.body = f"""
        Olá,
        
        Você recebeu um documento para assinatura digital via Gov.br.
        
        Instruções:
        1. Baixe o arquivo PDF em anexo neste e-mail.
        2. Acesse o portal: https://assinador.iti.br/
        3. Entre com sua conta Gov.br (deve ser nível Prata ou Ouro).
        4. Faça o upload do arquivo anexado e realize a assinatura.
        5. Após concluir, baixe o arquivo assinado e envie de volta para este e-mail.
        
        Atenciosamente,
        Seu App de Assinaturas
        """

        # Anexa o arquivo PDF ao e-mail
        with app.open_resource(filepath) as fp:
            msg.attach(filename, "application/pdf", fp.read())

        mail.send(msg)
        flash(f"Sucesso! Documento enviado para {email_destinatario}", "success")
        
    except Exception as e:
        flash(f"Erro ao enviar e-mail: {str(e)}", "danger")
    
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)