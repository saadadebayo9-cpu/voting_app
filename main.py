
import sqlite3
import os

from datetime import date
from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware


app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "change-this-secret-key")
)

templates = Jinja2Templates(directory="templates")


# DATABASE CONNECTION
def get_db():
    conn = sqlite3.connect("voting.db")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL COLLATE NOCASE UNIQUE,
            candidate TEXT NOT NULL,
            voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    return conn


# CANDIDATES
CANDIDATES = [
    "Candidate A",
    "Candidate B"
]


# CHECK IF EMAIL HAS VOTED
def has_voted(email):
    conn = get_db()

    result = conn.execute(
        "SELECT id FROM votes WHERE email = ?",
        (email,)
    ).fetchone()

    conn.close()

    return result is not None


# CALCULATE AGE
def calculate_age(dob):
    today = date.today()

    return today.year - dob.year - (
        (today.month, today.day) < (dob.month, dob.day)
    )


# PAGE 1: LOGIN
@app.get("/")
def login_page(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={}
    )


@app.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    dob: str = Form(...)
):

    email = email.strip().lower()

    try:
        birth_date = date.fromisoformat(dob)

    except ValueError:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": "Please enter a valid date of birth."
            }
        )

    if birth_date > date.today():

        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": "Date of birth cannot be in the future."
            }
        )

    if calculate_age(birth_date) < 18:

        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": "Only voters aged 18 and above are eligible."
            }
        )

    if has_voted(email):

        return templates.TemplateResponse(
            request=request,
            name="success.html",
            context={
                "message": "This email address has already voted."
            }
        )

    request.session["email"] = email

    return RedirectResponse(
        url="/candidates",
        status_code=303
    )


# PAGE 2: CANDIDATES
@app.get("/candidates")
def candidate_page(request: Request):

    email = request.session.get("email")

    if not email:
        return RedirectResponse("/", status_code=303)

    if has_voted(email):

        request.session.clear()

        return templates.TemplateResponse(
            request=request,
            name="success.html",
            context={
                "message": "This email address has already voted."
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="candidates.html",
        context={
            "candidates": CANDIDATES
        }
    )


# CAST VOTE
@app.post("/vote")
def cast_vote(
    request: Request,
    candidate: str = Form(...)
):

    email = request.session.get("email")

    if not email:
        return RedirectResponse("/", status_code=303)

    if candidate not in CANDIDATES:
        return RedirectResponse("/candidates", status_code=303)

    conn = get_db()

    try:

        conn.execute(
            "INSERT INTO votes (email, candidate) VALUES (?, ?)",
            (email, candidate)
        )

        conn.commit()

        request.session.clear()

        return templates.TemplateResponse(
            request=request,
            name="success.html",
            context={
                "message": "Your vote has been successfully cast!"
            }
        )

    except sqlite3.IntegrityError:

        request.session.clear()

        return templates.TemplateResponse(
            request=request,
            name="success.html",
            context={
                "message": "This email address has already voted."
            }
        )

    finally:
        conn.close()
