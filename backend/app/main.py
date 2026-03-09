from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.routers import auth, pagos, configuracion

Base.metadata.create_all(bind=engine)

# Migración: agregar columnas nuevas a tabla existente (SQLite no soporta ALTER condicional)
from sqlalchemy import text
with engine.connect() as conn:
    for col_def in [
        "ALTER TABLE pagos ADD COLUMN monto_clp NUMERIC(12, 0)",
        "ALTER TABLE pagos ADD COLUMN archivo_comprobante VARCHAR(255)",
        "ALTER TABLE pagos ADD COLUMN email_destinatario VARCHAR(254)",
        "ALTER TABLE pagos ADD COLUMN nombre_destinatario VARCHAR(200)",
    ]:
        try:
            conn.execute(text(col_def))
            conn.commit()
        except Exception:
            conn.rollback()

# Migración: mover imagen_cobro/imagen_reembolso legacy a tabla imagenes_pago
from sqlalchemy.orm import Session as _Session
with _Session(engine) as _sess:
    try:
        _pagos_con_imgs = _sess.execute(text(
            "SELECT id, imagen_cobro, imagen_reembolso FROM pagos "
            "WHERE imagen_cobro IS NOT NULL OR imagen_reembolso IS NOT NULL"
        )).fetchall()
        for _row in _pagos_con_imgs:
            _pid, _ic, _ir = _row
            if _ic:
                _sess.execute(text(
                    "INSERT INTO imagenes_pago (pago_id, tipo_imagen, filename) VALUES (:pid, 'cobro', :fn)"
                ), {"pid": _pid, "fn": _ic})
            if _ir:
                _sess.execute(text(
                    "INSERT INTO imagenes_pago (pago_id, tipo_imagen, filename) VALUES (:pid, 'reembolso', :fn)"
                ), {"pid": _pid, "fn": _ir})
        if _pagos_con_imgs:
            _sess.execute(text(
                "UPDATE pagos SET imagen_cobro = NULL, imagen_reembolso = NULL "
                "WHERE imagen_cobro IS NOT NULL OR imagen_reembolso IS NOT NULL"
            ))
            _sess.commit()
    except Exception:
        _sess.rollback()

app = FastAPI(title="Control de Reembolsos")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(pagos.router)
app.include_router(configuracion.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
