from flask import Flask, render_template, request, redirect, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
from flask import send_from_directory
ALLOWED_EXTENSIONS = {"mp4", "mov", "avi", "mkv"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB



app = Flask(__name__)
app.secret_key = "super_secret"
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def criar_banco():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        senha TEXT,
        creditos INTEGER DEFAULT 5
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cursos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        descricao TEXT,
        criador_id INTEGER,
        video TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inscricoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        curso_id INTEGER,
        UNIQUE(usuario_id, curso_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS avaliacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        curso_id INTEGER,
        usuario_id INTEGER,
        nota INTEGER,
        UNIQUE(usuario_id, curso_id)
    )
    """)

    conn.commit()
    conn.close()



@app.route("/")
def home():
    return render_template("home.html")

@app.route("/inscrever/<int:curso_id>")
def inscrever(curso_id):

    if "user_id" not in session:
        return redirect("/login")

    usuario_id = session["user_id"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Pega curso
    cursor.execute("SELECT criador_id FROM cursos WHERE id=?", (curso_id,))
    curso = cursor.fetchone()

    if not curso:
        conn.close()
        return redirect("/cursos")

    criador_id = curso[0]

    # Impede se inscrever no próprio curso
    if criador_id == usuario_id:
        conn.close()
        return "Você não pode se inscrever no próprio curso!"

    # Verifica créditos
    cursor.execute("SELECT creditos FROM usuarios WHERE id=?", (usuario_id,))
    creditos = cursor.fetchone()[0]

    if creditos <= 0:
        conn.close()
        return "Você não tem créditos suficientes!"

    try:
        cursor.execute("""
        INSERT INTO inscricoes (usuario_id, curso_id)
        VALUES (?, ?)
        """, (usuario_id, curso_id))

        cursor.execute("""
        UPDATE usuarios SET creditos = creditos - 1
        WHERE id=?
        """, (usuario_id,))

        conn.commit()

    except:
        conn.close()
        return "Você já está inscrito nesse curso!"

    conn.close()
    return redirect("/cursos")


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        username = request.form["username"]
        senha = generate_password_hash(request.form["senha"])

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        try:
            cursor.execute("INSERT INTO usuarios (username, senha) VALUES (?, ?)", (username, senha))
            conn.commit()
        except:
            conn.close()
            return "Usuário já existe!"

        conn.close()
        return redirect("/login")

    return render_template("cadastro.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        senha = request.form["senha"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE username=?", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[2], senha):
            session["user_id"] = user[0]
            return redirect("/cursos")

        return "Login inválido"

    return render_template("login.html")

@app.route("/criar", methods=["GET", "POST"])
def criar():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        nome = request.form["nome"]
        descricao = request.form["descricao"]
        video = request.files["video"]

        filename = None
        if video:
            filename = secure_filename(video.filename)
            video.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO cursos (nome, descricao, criador_id, video)
        VALUES (?, ?, ?, ?)
        """, (nome, descricao, session["user_id"], filename))

        conn.commit()
        conn.close()

        return redirect("/cursos")

    return render_template("criar_curso.html")

@app.route("/avaliar/<int:curso_id>/<int:nota>")
def avaliar(curso_id, nota):

    if "user_id" not in session:
        return redirect("/login")

    usuario_id = session["user_id"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Pega criador
    cursor.execute("SELECT criador_id FROM cursos WHERE id=?", (curso_id,))
    curso = cursor.fetchone()

    if not curso:
        conn.close()
        return redirect("/cursos")

    criador_id = curso[0]

    # Impede autoavaliação
    if criador_id == usuario_id:
        conn.close()
        return "Você não pode avaliar seu próprio curso!"

    try:
        cursor.execute("""
        INSERT INTO avaliacoes (curso_id, usuario_id, nota)
        VALUES (?, ?, ?)
        """, (curso_id, usuario_id, nota))
        conn.commit()

    except:
        conn.close()
        return "Você já avaliou esse curso!"

    conn.close()
    return redirect("/cursos")


@app.route("/cursos")
def cursos():

    usuario_id = session.get("user_id")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT cursos.id, cursos.nome, cursos.descricao,
           cursos.video, cursos.criador_id,
           usuarios.username,
           IFNULL(AVG(avaliacoes.nota),0)
    FROM cursos
    JOIN usuarios ON cursos.criador_id = usuarios.id
    LEFT JOIN avaliacoes ON cursos.id = avaliacoes.curso_id
    GROUP BY cursos.id
    """)
    cursos = cursor.fetchall()

    inscricoes = []
    if usuario_id:
        cursor.execute("""
        SELECT curso_id FROM inscricoes
        WHERE usuario_id=?
        """, (usuario_id,))
        inscricoes = [i[0] for i in cursor.fetchall()]

    conn.close()

    return render_template(
        "cursos.html",
        cursos=cursos,
        inscricoes=inscricoes,
        usuario_id=usuario_id
    )

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route("/logout")
def logout():
    if "user_id" in session:
        session.pop("user_id")
    return redirect("/")


@app.route("/ranking")
def ranking():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT usuarios.username, IFNULL(AVG(avaliacoes.nota),0) as media
    FROM usuarios
    JOIN cursos ON cursos.criador_id = usuarios.id
    LEFT JOIN avaliacoes ON cursos.id = avaliacoes.curso_id
    GROUP BY usuarios.id
    ORDER BY media DESC
    """)
    ranking = cursor.fetchall()
    conn.close()

    return render_template("ranking.html", ranking=ranking)

if __name__ == "__main__":
    app.run()
