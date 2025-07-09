
markdown_editor/
│
├── app.py
├── templates/
│   ├── login.html
│   └── index.html
└── static/
    └── style.css



pip install flask flask-login flask-sqlalchemy Flask-Migrate

docker build -t meu-flask-app .


docker run -e SECRET_KEY=valor -e DATABASE_URL=sqlite:///app.db -p 5000:5000 meu-flask-app

flask shell
>>> from app import db, User
>>> from werkzeug.security import generate_password_hash
>>> admin = User(username="admin", password_hash=generate_password_hash("senha123"), is_admin=True, is_approved=True)
>>> db.session.add(admin)
>>> db.session.commit()
