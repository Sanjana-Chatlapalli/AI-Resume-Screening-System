from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    Response,
    flash
)

import os
import sqlite3
import pdfplumber
from collections import Counter

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)
app.secret_key = "resume_screening_secret_key"

UPLOAD_FOLDER = "resumes"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# ---------------- DATABASE ----------------

def create_database():

    conn = sqlite3.connect("resume.db")
    cursor = conn.cursor()

    # Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )
    """)

    # Candidates Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS candidates(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        skills TEXT,
        match_score REAL,
        ats_score REAL,
        recommendations TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    conn.commit()
    conn.close()


# ---------------- CREATE ADMIN ----------------

def create_admin():

    conn = sqlite3.connect("resume.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE email=?",
        ("admin@gmail.com",)
    )

    admin = cursor.fetchone()

    if admin is None:

        cursor.execute(
            """
            INSERT INTO users(name,email,phone,password,role)
            VALUES(?,?,?,?,?)
            """,
            (
                "Admin",
                "admin@gmail.com",
                "9876543210",
                "admin123",
                "Admin"
            )
        )

        conn.commit()

    conn.close()


# ---------------- USER FUNCTIONS ----------------

def register_user(name, email, phone, password, role):

    conn = sqlite3.connect("resume.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO users(name,email,phone,password,role)
        VALUES(?,?,?,?,?)
        """,
        (name, email, phone, password, role)
    )

    conn.commit()
    conn.close()


def check_login(email, password):

    conn = sqlite3.connect("resume.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM users
        WHERE email=? AND password=?
        """,
        (email, password)
    )

    user = cursor.fetchone()

    conn.close()

    return user


# ---------------- PDF EXTRACTION ----------------

def extract_text(pdf_path):

    text = ""

    with pdfplumber.open(pdf_path) as pdf:

        for page in pdf.pages:
            text += page.extract_text() or ""

    return text


# ---------------- SKILL EXTRACTION ----------------

def extract_skills(text):

    skills_db = [
    "python",
    "java",
    "c",
    "c++",
    "sql",
    "mysql",
    "html",
    "css",
    "javascript",
    "bootstrap",
    "flask",
    "django",
    "react",
    "node js",
    "machine learning",
    "deep learning",
    "artificial intelligence",
    "data analysis",
    "power bi",
    "excel",
    "git",
    "github",
    "docker",
    "aws",
    "linux",
    "mongodb",
    "tensorflow",
    "pandas",
    "numpy",
    "opencv"
    ]

    text = text.lower()

    skills = []

    for skill in skills_db:
        if skill in text:
            skills.append(skill)

    return skills


# ---------------- MATCH SCORE ----------------

def calculate_similarity(resume_text, job_description):

    documents = [resume_text, job_description]

    vectorizer = TfidfVectorizer()

    matrix = vectorizer.fit_transform(documents)

    score = cosine_similarity(
        matrix[0:1],
        matrix[1:2]
    )[0][0]

    return round(score * 100, 2)
# ---------------- HOME ----------------

@app.route("/")
def home():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session["role"] == "Admin":
        return redirect(url_for("dashboard"))

    return render_template(
        "index.html",
        name=session["name"]
    )


# ---------------- REGISTER ----------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        password = request.form["password"]

        role = "Student"

        try:

            register_user(
                name,
                email,
                phone,
                password,
                role
            )

            flash("Registration Successful")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:

            flash("Email already exists")

    return render_template("register.html")


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        user = check_login(email, password)
        print(user)

        if user:

            session["user_id"] = user[0]
            session["name"] = user[1]
            session["role"] = user[5]

            if user[5] == "Admin":
                return redirect(url_for("dashboard"))

            return redirect(url_for("student_dashboard"))
        
        flash("Invalid Email or Password")

    return render_template("login.html")


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))
# ---------------- UPLOAD RESUME ----------------

@app.route("/upload", methods=["POST"])
def upload():

    if "user_id" not in session:
        return redirect(url_for("login"))

    file = request.files["resume"]
    job_description = request.form["job_description"]

    if file.filename == "":
        flash("Please select a resume.")
        return redirect(url_for("home"))

    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        file.filename
    )

    file.save(filepath)

    resume_text = extract_text(filepath)

    skills = extract_skills(resume_text)

    score = calculate_similarity(
        resume_text,
        job_description
    )

    ats_score = min(score + 10, 100)

    job_skills = extract_skills(job_description)

    missing_skills = list(
        set(job_skills) - set(skills)
    )

    recommendations = []

    if "python" in skills:
        recommendations.append("Python Developer")

    if "sql" in skills:
        recommendations.append("Data Analyst")

    if "html" in skills and "css" in skills:
        recommendations.append("Frontend Developer")

    if "machine learning" in skills:
        recommendations.append("Machine Learning Engineer")

    conn = sqlite3.connect("resume.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO candidates
        (user_id, skills, match_score, ats_score, recommendations)

        VALUES (?, ?, ?, ?, ?)
        """,
        (
            session["user_id"],
            ", ".join(skills),
            score,
            ats_score,
            ", ".join(recommendations)
        )
    )

    conn.commit()
    conn.close()

    return render_template(
        "result.html",
        skills=skills,
        score=score,
        ats_score=ats_score,
        missing_skills=missing_skills,
        recommendations=recommendations,
        job_description=job_description
    )
# ---------------- STUDENT DASHBOARD ----------------

@app.route("/student_dashboard")
def student_dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("resume.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM candidates
        WHERE user_id=?
        ORDER BY id DESC
        """,
        (session["user_id"],)
    )

    resumes = cursor.fetchall()

    conn.close()

    return render_template(
        "student_dashboard.html",
        resumes=resumes,
        name=session["name"]
    )
# ---------------- ADMIN DASHBOARD ----------------

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session["role"] != "Admin":
        return redirect(url_for("student_dashboard"))

    search = request.args.get("search", "")

    conn = sqlite3.connect("resume.db")
    cursor = conn.cursor()

    if search:

        cursor.execute("""
        SELECT
            candidates.id,
            users.name,
            users.email,
            users.phone,
            candidates.skills,
            candidates.match_score,
            candidates.ats_score,
            candidates.recommendations

        FROM candidates

        INNER JOIN users
        ON candidates.user_id = users.id

        WHERE users.name LIKE ?
        OR users.email LIKE ?

        ORDER BY candidates.match_score DESC
        """,
        ('%' + search + '%',
         '%' + search + '%'))

    else:

        cursor.execute("""
        SELECT
            candidates.id,
            users.name,
            users.email,
            users.phone,
            candidates.skills,
            candidates.match_score,
            candidates.ats_score,
            candidates.recommendations

        FROM candidates

        INNER JOIN users
        ON candidates.user_id = users.id

        ORDER BY candidates.match_score DESC
        """)

    candidates = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM users WHERE role='Student'")
    total_students = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM candidates")
    total_resumes = cursor.fetchone()[0]

    cursor.execute("SELECT AVG(ats_score) FROM candidates")
    avg_ats = cursor.fetchone()[0]

    if avg_ats is None:
        avg_ats = 0

    conn.close()

    return render_template(
        "dashboard.html",
        candidates=candidates,
        total_students=total_students,
        total_resumes=total_resumes,
        avg_ats=round(avg_ats,2),
        search=search
    )
# ---------------- DELETE STUDENT ----------------

@app.route("/delete/<int:id>")
def delete(id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session["role"] != "Admin":
        return redirect(url_for("student_dashboard"))

    conn = sqlite3.connect("resume.db")
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM candidates WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()

    flash("Candidate Deleted Successfully")

    return redirect(url_for("dashboard"))
# ---------------- EXPORT CSV ----------------

@app.route("/export")
def export():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("resume.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        users.name,
        users.email,
        users.phone,
        candidates.skills,
        candidates.match_score,
        candidates.ats_score,
        candidates.recommendations

    FROM candidates

    INNER JOIN users
    ON candidates.user_id = users.id
    """)

    rows = cursor.fetchall()

    conn.close()

    def generate():

        yield "Name,Email,Phone,Skills,Match Score,ATS Score,Recommendations\n"

        for row in rows:

            yield (
                f"{row[0]},"
                f"{row[1]},"
                f"{row[2]},"
                f"{row[3]},"
                f"{row[4]},"
                f"{row[5]},"
                f"{row[6]}\n"
            )

    return Response(
        generate(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=students.csv"
        }
    )
# ---------------- MAIN ----------------

create_database()
create_admin()

if __name__ == "__main__":
    app.run(debug=True)