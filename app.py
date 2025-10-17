import os
from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from functools import wraps  # ### ADICIONADO ### - Para criar nosso "guardião"

# --- CONFIGURAÇÃO DA APLICAÇÃO ---
basedir = os.path.abspath(os.path.dirname(__file__))
instance_path = os.path.join(basedir, 'instance')
os.makedirs(instance_path, exist_ok=True)

app = Flask(__name__)

# ### ADICIONADO ### - CONFIGURAÇÃO DE USUÁRIO E SENHA DO ADMIN
# Use variáveis de ambiente para segurança. Se não encontrar, usa os valores padrão 'admin' e 'senha'.
ADMIN_USERNAME = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASS', 'sua_senha_forte') # <-- TROQUE PELA SUA SENHA!

app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-segura'
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'uploads')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "site.db")}'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# --- CONFIGURAÇÃO DO E-MAIL ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'rwestruturas@gmail.com'
app.config['MAIL_PASSWORD'] = 'ixmv viaa wuhq kwlo'

mail = Mail(app)
db = SQLAlchemy(app)

# ### ADICIONADO ### - LÓGICA DO GUARDIÃO DE SENHA
def check_auth(username, password):
    """Verifica se o usuário e senha estão corretos."""
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD

def authenticate():
    """Envia a resposta 401 para pedir autenticação."""
    return Response(
    'Acesso negado. Você precisa se autenticar para acessar esta página.', 401,
    {'WWW-Authenticate': 'Basic realm="Login Obrigatório"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated
# -----------------------------------------------------------

# --- MODELO DO BANCO DE DADOS ---
class Foto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    categoria = db.Column(db.String(50), nullable=False)
    filename = db.Column(db.String(100), nullable=False)


# --- ROTAS DO SITE (PÁGINAS) ---

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/quem-somos')
def quem_somos():
    return render_template('quem_somos.html')


@app.route('/portfolios')
def portfolios():
    return render_template('portfolios.html')


@app.route('/portfolio/<categoria>')
def portfolio_categoria(categoria):
    fotos = Foto.query.filter_by(categoria=categoria).all()
    titulo_pagina = categoria.replace('-', ' ').title()
    return render_template('portfolio_categoria.html', fotos=fotos, titulo=titulo_pagina)


@app.route('/orcamento', methods=['GET', 'POST'])
def orcamento():
    if request.method == 'POST':
        try:
            # Coleta todos os dados do formulário
            nome = request.form.get('nome')
            email = request.form.get('email')
            telefone = request.form.get('telefone')
            empresa = request.form.get('empresa')
            tipo_servico = request.form.get('tipo_servico')
            descricao = request.form.get('descricao')
            quantidade = request.form.get('quantidade')
            orcamento_estimado = request.form.get('orcamento_estimado')

            # Monta o corpo do e-mail
            corpo_email = f"""
            Novo Pedido de Orçamento Recebido pelo Site!
            --------------------------------------------------
            Nome: {nome}
            Email: {email}
            Telefone: {telefone}
            Empresa: {empresa or 'Não informado'}
            Tipo de Serviço: {tipo_servico}
            Descrição do Projeto:
            {descricao}
            --------------------------------------------------
            Quantidade/Escopo: {quantidade or 'Não informado'}
            Orçamento Estimado: {orcamento_estimado or 'Não informado'}
            """

            # Cria a mensagem de e-mail
            msg = Message(
                subject=f"Novo Orçamento de {nome}",
                sender=app.config['MAIL_USERNAME'],
                recipients=[app.config['MAIL_USERNAME']],
                body=corpo_email
            )

            # Anexa o arquivo, se o cliente enviou um
            if 'anexos' in request.files and request.files['anexos'].filename != '':
                anexo = request.files['anexos']
                msg.attach(anexo.filename, anexo.content_type, anexo.read())

            mail.send(msg)
            flash('Seu pedido de orçamento foi enviado com sucesso! Entraremos em contato em breve.', 'success')

        except Exception as e:
            print(f"Ocorreu um erro ao enviar o e-mail: {e}")
            flash('Ocorreu um erro ao enviar seu pedido. Por favor, tente novamente mais tarde.', 'danger')

        return redirect(url_for('orcamento'))

    return render_template('orcamento.html')


# --- PAINEL DE ADMINISTRADOR ---

@app.route('/admin', methods=['GET', 'POST'])
@requires_auth  # ### ADICIONADO ### - Protege esta rota
def admin():
    if request.method == 'POST':
        if 'foto' not in request.files:
            flash('Nenhum arquivo selecionado!', 'danger')
            return redirect(request.url)

        file = request.files['foto']
        categoria = request.form.get('categoria')

        if file.filename == '':
            flash('Nenhum arquivo selecionado!', 'danger')
            return redirect(request.url)

        if file and categoria:
            filename = secure_filename(file.filename)
            categoria_path = os.path.join(app.config['UPLOAD_FOLDER'], categoria)
            os.makedirs(categoria_path, exist_ok=True)

            save_path = os.path.join(categoria_path, filename)
            file.save(save_path)

            db_path = f"{categoria}/{filename}"
            nova_foto = Foto(categoria=categoria, filename=db_path)
            db.session.add(nova_foto)
            db.session.commit()
            flash('Foto adicionada com sucesso!', 'success')
            return redirect(url_for('admin'))

    fotos = Foto.query.all()
    return render_template('admin.html', fotos=fotos)


@app.route('/admin/delete/<int:foto_id>', methods=['POST'])
@requires_auth  # ### ADICIONADO ### - Protege esta rota também
def delete_foto(foto_id):
    foto_para_deletar = Foto.query.get_or_404(foto_id)

    try:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], foto_para_deletar.filename))
    except OSError as e:
        print(f"Erro ao deletar arquivo: {e}")
        flash('Erro ao deletar arquivo do servidor.', 'danger')

    db.session.delete(foto_para_deletar)
    db.session.commit()
    flash('Foto deletada com sucesso.', 'success')
    return redirect(url_for('admin'))


if __name__ == '__main__':
    with app.app_context():
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        db.create_all()
    app.run(debug=True)