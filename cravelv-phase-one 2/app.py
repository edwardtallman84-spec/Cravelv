from __future__ import annotations

import os
import random
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "cravelv.db")))

app = FastAPI(title="CraveLV")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS brands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                voice TEXT NOT NULL,
                focus TEXT NOT NULL,
                instagram TEXT DEFAULT '',
                facebook TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                brand_id INTEGER NOT NULL,
                platform TEXT NOT NULL,
                content_type TEXT NOT NULL,
                scheduled_for TEXT NOT NULL,
                caption TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Draft',
                reach INTEGER NOT NULL DEFAULT 0,
                likes INTEGER NOT NULL DEFAULT 0,
                comments INTEGER NOT NULL DEFAULT 0,
                shares INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (brand_id) REFERENCES brands(id)
            );
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                name TEXT NOT NULL,
                contact TEXT NOT NULL,
                event_date TEXT DEFAULT '',
                guest_count INTEGER DEFAULT 0,
                brand_interest TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'New'
            );
            CREATE TABLE IF NOT EXISTS engagements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                brand_id INTEGER NOT NULL,
                customer_name TEXT NOT NULL,
                customer_message TEXT NOT NULL,
                suggested_reply TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Needs reply',
                FOREIGN KEY (brand_id) REFERENCES brands(id)
            );
            """
        )
        count = conn.execute("SELECT COUNT(*) FROM brands").fetchone()[0]
        if count == 0:
            brands = [
                ("Slidin Thru", "bold, playful, craveable, Las Vegas energy", "sliders, loaded fries, catering"),
                ("El Queso Guero", "warm, colorful, street-food confidence", "tacos, burritos, quesadillas, catering"),
                ("Sin City Wings", "high-energy, saucy, sports-friendly", "wings, sauces, game-day orders"),
                ("Sin City Pizza", "friendly, cheesy, neighborhood favorite", "pizza, events, group orders"),
            ]
            conn.executemany("INSERT INTO brands(name, voice, focus) VALUES(?,?,?)", brands)
            brand_ids = {r["name"]: r["id"] for r in conn.execute("SELECT id,name FROM brands")}
            tomorrow = date.today() + timedelta(days=1)
            starter_posts = [
                (brand_ids["Slidin Thru"], "Instagram", "Reel", str(tomorrow), "POV: you found the slider that ruins ordinary burgers for you. 🍔 Tag the friend who owes you lunch. #LasVegasFood #FoodTruck", "Ready"),
                (brand_ids["El Queso Guero"], "Facebook", "Photo", str(tomorrow + timedelta(days=1)), "Three tacos. One decision: asada, chicken tinga, or smoked pork? Tell us your order below. 🌮", "Draft"),
            ]
            conn.executemany("INSERT INTO posts(brand_id,platform,content_type,scheduled_for,caption,status) VALUES(?,?,?,?,?,?)", starter_posts)
            conn.execute(
                "INSERT INTO engagements(created_at,brand_id,customer_name,customer_message,suggested_reply) VALUES(?,?,?,?,?)",
                (datetime.now().isoformat(timespec="minutes"), brand_ids["Slidin Thru"], "VegasFoodFan", "Where are you this weekend?", "We’re finalizing this weekend’s route now. Send us your neighborhood and we’ll tell you the closest stop! 🍔"),
            )


init_db()


@app.get("/health")
def health():
    return {"status": "ok", "app": "CraveLV", "phase": 1}


def local_caption(brand: str, item: str, goal: str, platform: str, tone: str) -> str:
    hooks = [
        f"Stop scrolling—{item} just entered the chat.",
        f"Las Vegas, this {item} is calling your name.",
        f"POV: lunch plans just changed because of this {item}.",
        f"Tag the person who would not share this {item}.",
    ]
    ctas = {
        "followers": "Follow us for truck locations, new drops, and behind-the-scenes food content.",
        "engagement": "Drop your order in the comments and tag your food-truck partner.",
        "catering": "Planning an event? Message us the date and guest count for a catering quote.",
        "sales": "Come find us before we sell out—today’s location is in our latest Story.",
    }
    tags = "#LasVegasFood #VegasFoodie #FoodTruck #LasVegasEats"
    return f"{random.choice(hooks)}\n\n{brand} is serving {item} with {tone.lower()} energy. {ctas.get(goal, ctas['engagement'])}\n\n{tags}"


def ai_caption(brand: str, voice: str, focus: str, item: str, goal: str, platform: str, tone: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return local_caption(brand, item, goal, platform, tone)
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        prompt = f"""Write one high-performing {platform} caption for a Las Vegas food truck.
Brand: {brand}
Brand voice: {voice}
Business focus: {focus}
Featured item/topic: {item}
Primary goal: {goal}
Tone: {tone}
Requirements: strong first-line hook, natural language, one clear CTA, no fake claims, no excessive emojis, 4-7 relevant hashtags, under 900 characters."""
        response = client.responses.create(model=os.getenv("OPENAI_MODEL", "gpt-5-mini"), input=prompt)
        return response.output_text.strip()
    except Exception:
        return local_caption(brand, item, goal, platform, tone)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    with db() as conn:
        stats = {
            "posts": conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0],
            "ready": conn.execute("SELECT COUNT(*) FROM posts WHERE status='Ready'").fetchone()[0],
            "leads": conn.execute("SELECT COUNT(*) FROM leads WHERE status='New'").fetchone()[0],
            "replies": conn.execute("SELECT COUNT(*) FROM engagements WHERE status='Needs reply'").fetchone()[0],
        }
        upcoming = conn.execute("""SELECT posts.*, brands.name brand_name FROM posts JOIN brands ON brands.id=posts.brand_id ORDER BY scheduled_for LIMIT 8""").fetchall()
        brands = conn.execute("SELECT * FROM brands ORDER BY name").fetchall()
        leads = conn.execute("SELECT * FROM leads ORDER BY created_at DESC LIMIT 5").fetchall()
    return templates.TemplateResponse("dashboard.html", {"request": request, "stats": stats, "upcoming": upcoming, "brands": brands, "leads": leads})


@app.get("/content", response_class=HTMLResponse)
def content(request: Request):
    with db() as conn:
        posts = conn.execute("""SELECT posts.*, brands.name brand_name FROM posts JOIN brands ON brands.id=posts.brand_id ORDER BY scheduled_for""").fetchall()
        brands = conn.execute("SELECT * FROM brands ORDER BY name").fetchall()
    return templates.TemplateResponse("content.html", {"request": request, "posts": posts, "brands": brands})


@app.post("/posts")
def create_post(brand_id: int = Form(...), platform: str = Form(...), content_type: str = Form(...), scheduled_for: str = Form(...), caption: str = Form(...), status: str = Form("Draft")):
    with db() as conn:
        conn.execute("INSERT INTO posts(brand_id,platform,content_type,scheduled_for,caption,status) VALUES(?,?,?,?,?,?)", (brand_id, platform, content_type, scheduled_for, caption, status))
    return RedirectResponse("/content", status_code=303)


@app.post("/posts/{post_id}/status")
def update_post_status(post_id: int, status: str = Form(...)):
    with db() as conn:
        conn.execute("UPDATE posts SET status=? WHERE id=?", (status, post_id))
    return RedirectResponse("/content", status_code=303)


@app.get("/generator", response_class=HTMLResponse)
def generator(request: Request):
    with db() as conn:
        brands = conn.execute("SELECT * FROM brands ORDER BY name").fetchall()
    return templates.TemplateResponse("generator.html", {"request": request, "brands": brands, "generated": None})


@app.post("/generator", response_class=HTMLResponse)
def generate(request: Request, brand_id: int = Form(...), item: str = Form(...), goal: str = Form(...), platform: str = Form(...), tone: str = Form(...)):
    with db() as conn:
        brands = conn.execute("SELECT * FROM brands ORDER BY name").fetchall()
        brand = conn.execute("SELECT * FROM brands WHERE id=?", (brand_id,)).fetchone()
    generated = ai_caption(brand["name"], brand["voice"], brand["focus"], item, goal, platform, tone)
    return templates.TemplateResponse("generator.html", {"request": request, "brands": brands, "generated": generated, "selected": {"brand_id": brand_id, "item": item, "goal": goal, "platform": platform, "tone": tone}})


@app.get("/leads", response_class=HTMLResponse)
def leads(request: Request):
    with db() as conn:
        rows = conn.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall()
    return templates.TemplateResponse("leads.html", {"request": request, "leads": rows})


@app.post("/leads")
def create_lead(name: str = Form(...), contact: str = Form(...), event_date: str = Form(""), guest_count: int = Form(0), brand_interest: str = Form(""), notes: str = Form("")):
    with db() as conn:
        conn.execute("INSERT INTO leads(created_at,name,contact,event_date,guest_count,brand_interest,notes) VALUES(?,?,?,?,?,?,?)", (datetime.now().isoformat(timespec="minutes"), name, contact, event_date, guest_count, brand_interest, notes))
    return RedirectResponse("/leads", status_code=303)


@app.get("/engagement", response_class=HTMLResponse)
def engagement(request: Request):
    with db() as conn:
        rows = conn.execute("""SELECT engagements.*, brands.name brand_name FROM engagements JOIN brands ON brands.id=engagements.brand_id ORDER BY created_at DESC""").fetchall()
    return templates.TemplateResponse("engagement.html", {"request": request, "items": rows})


@app.post("/engagement/{item_id}/done")
def engagement_done(item_id: int):
    with db() as conn:
        conn.execute("UPDATE engagements SET status='Replied' WHERE id=?", (item_id,))
    return RedirectResponse("/engagement", status_code=303)
