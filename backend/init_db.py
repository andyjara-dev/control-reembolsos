"""Crea el usuario admin inicial si no existe."""
import os
import sys

# Permitir ejecutar tanto dentro del contenedor como localmente
sys.path.insert(0, os.path.dirname(__file__))

from app.config import ADMIN_USER, ADMIN_PASS
from app.database import engine, Base, SessionLocal
from app.models import User
from app.auth import hash_password

Base.metadata.create_all(bind=engine)

# Migraciones: agregar columnas nuevas si no existen
from sqlalchemy import text
with engine.connect() as conn:
    for col, col_type in [
        ("imagen_cobro", "VARCHAR(255)"),
        ("imagen_reembolso", "VARCHAR(255)"),
    ]:
        try:
            conn.execute(text(f"ALTER TABLE pagos ADD COLUMN {col} {col_type}"))
            conn.commit()
            print(f"Columna '{col}' agregada a pagos.")
        except Exception:
            conn.rollback()

db = SessionLocal()
try:
    existing = db.query(User).filter(User.username == ADMIN_USER).first()
    if not existing:
        user = User(username=ADMIN_USER, password=hash_password(ADMIN_PASS))
        db.add(user)
        db.commit()
        print(f"Usuario '{ADMIN_USER}' creado.")
    else:
        print(f"Usuario '{ADMIN_USER}' ya existe.")
finally:
    db.close()
