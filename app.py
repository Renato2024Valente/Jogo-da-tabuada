
import os
from datetime import datetime
from uuid import uuid4

from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash

from sqlalchemy import create_engine, Integer, String, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

DATABASE_URL = os.environ.get("DATABASE_URL") or f"sqlite:///{os.path.join(DATA_DIR,'photos.db')}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

class Base(DeclarativeBase):
    pass

class Photo(Base):
    __tablename__ = "photos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=True)
    description: Mapped[str] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

ADMIN_PIN = os.environ.get("ADMIN_PIN", "1234")

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/galeria")
def galeria():
    with SessionLocal() as db:
        photos = db.query(Photo).order_by(Photo.id.desc()).all()
    return render_template("galeria.html", photos=photos)

@app.post("/upload")
def upload():
    file = request.files.get("file")
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    if not file or file.filename == "":
        flash("Selecione uma imagem.", "danger")
        return redirect(url_for("galeria"))

    allowed = {"png","jpg","jpeg","gif","webp"}
    ext = file.filename.rsplit(".",1)[-1].lower() if "." in file.filename else ""
    if ext not in allowed:
        flash("Formato não suportado. Envie PNG/JPG/GIF/WEBP.", "danger")
        return redirect(url_for("galeria"))

    fname = f"{uuid4().hex}.{ext}"
    file.save(os.path.join(UPLOAD_DIR, fname))

    with SessionLocal() as db:
        p = Photo(filename=fname, title=title, description=description, created_at=datetime.utcnow())
        db.add(p)
        db.commit()
    flash("Foto enviada com sucesso!", "success")
    return redirect(url_for("galeria"))

@app.post("/delete/<int:photo_id>")
def delete(photo_id: int):
    pin = request.form.get("pin","")
    if pin != ADMIN_PIN:
        flash("PIN incorreto.", "danger")
        return redirect(url_for("galeria"))

    with SessionLocal() as db:
        p = db.get(Photo, photo_id)
        if not p:
            flash("Foto não encontrada.", "danger")
            return redirect(url_for("galeria"))
        path = os.path.join(UPLOAD_DIR, p.filename)
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
        db.delete(p)
        db.commit()
    flash("Foto excluída!", "success")
    return redirect(url_for("galeria"))

@app.get("/uploads/<path:filename>")
def uploads(filename):
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=False)

@app.get("/evidencias")
def evidencias():
    padlet_url = "https://padlet.onrender.com/"
    return render_template("evidencias.html", padlet_url=padlet_url)

@app.get("/contato")
def contato():
    return render_template("contato.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
