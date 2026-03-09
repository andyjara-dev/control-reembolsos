from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Configuracion
from app.schemas import ConfiguracionItem

CLAVES_SENSIBLES = {"resend_api_key"}

router = APIRouter(
    prefix="/api/configuracion",
    tags=["configuracion"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[ConfiguracionItem])
def get_configuracion(db: Session = Depends(get_db)):
    items = db.query(Configuracion).all()
    result = []
    for item in items:
        valor = item.valor
        if item.clave in CLAVES_SENSIBLES and valor:
            valor = "***"
        result.append(ConfiguracionItem(clave=item.clave, valor=valor))
    return result


@router.put("")
def set_configuracion(items: list[ConfiguracionItem], db: Session = Depends(get_db)):
    for item in items:
        # No sobreescribir claves sensibles si el valor es "***" (no cambió)
        if item.clave in CLAVES_SENSIBLES and item.valor == "***":
            continue
        existing = db.query(Configuracion).filter(Configuracion.clave == item.clave).first()
        if existing:
            existing.valor = item.valor
        else:
            db.add(Configuracion(clave=item.clave, valor=item.valor))
    db.commit()
    return {"mensaje": "Configuración guardada"}
