from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

from functools import wraps
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'develop_secret')

# Configuração do banco SQLite
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] =  os.getenv('DATABASE_URL','sqlite:///' + os.path.join(basedir, 'users.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Modelo de usuário
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_approved = db.Column(db.Boolean, default=False) 
    is_admin = db.Column(db.Boolean, default=False)
    content = db.Column(db.Text)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    content = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('documents', lazy=True))


# Cria o banco e a tabela se não existirem
with app.app_context():
    db.create_all()

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)  # Proibido
        return f(*args, **kwargs)
    return decorated_function 

@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403   

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        content = request.form['markdown']
        current_user.content = content
        db.session.commit()
        flash('Texto salvo com sucesso.', 'success')
        return redirect(url_for('index'))

    return render_template('index.html', username=current_user.username, saved_content=current_user.content or "")

@app.route('/documents/new', methods=['GET', 'POST'])
@login_required
def new_document():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        doc = Document(title=title, content=content, user=current_user)
        db.session.add(doc)
        db.session.commit()
        flash('Documento criado com sucesso.', 'success')
        return redirect(url_for('list_documents'))
    return render_template('new_document.html')

@app.route('/documents/<int:doc_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_document(doc_id):
    doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first_or_404()
    if request.method == 'POST':
        doc.title = request.form['title']
        doc.content = request.form['content']
        db.session.commit()
        flash('Documento atualizado.', 'success')
        return redirect(url_for('list_documents'))
    return render_template('edit_document.html', doc=doc)

@app.route('/documents')
@login_required
def list_documents():
    docs = Document.query.filter_by(user_id=current_user.id).order_by(Document.updated_at.desc()).all()
    return render_template('documents.html', documents=docs)

@app.route('/documents/<int:doc_id>/delete', methods=['POST'])
@login_required
def delete_document(doc_id):
    doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first_or_404()
    db.session.delete(doc)
    db.session.commit()
    flash('Documento excluído.', 'info')
    return redirect(url_for('list_documents'))

@app.route('/admin/users')
@admin_required
@login_required
def manage_users():
    if current_user.username != 'admin':  # ou use is_admin=True
        flash('Acesso negado.')
        return redirect(url_for('index'))
    
    users = User.query.all()
    return render_template('manage_users.html', users=users)

@app.route('/admin/approve/<int:user_id>')
@admin_required
@login_required
def approve_user(user_id):
    if current_user.username != 'admin':
        flash('Acesso negado.')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    user.is_approved = True
    db.session.commit()
    flash(f'Usuário {user.username} aprovado.')
    return redirect(url_for('manage_users'))

@app.route('/admin/revoke/<int:user_id>')
@admin_required
@login_required
def revoke_user(user_id):
    if current_user.username != 'admin':
        flash('Acesso negado.')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    user.is_approved = False
    db.session.commit()
    flash(f'Aprovação do usuário {user.username} foi revogada.')
    return redirect(url_for('manage_users'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            if not user.is_approved:
                flash('Seu cadastro ainda não foi aprovado pelo administrador.', 'warning')
                return redirect(url_for('login'))
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Usuário ou senha incorretos.')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash('Usuário já existe.')
        elif User.query.filter_by(email=email).first():
            flash('E-mail já cadastrado.')
        else:
            hashed = generate_password_hash(password)
            new_user = User(username=username, email=email, password_hash=hashed, is_approved=False)
            db.session.add(new_user)
            db.session.commit()
            flash('Cadastro realizado! Aguarde a aprovação do administrador.')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
