import secrets
import string as _string

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import verify_password, hash_password, create_token, get_current_user
from app.database import get_db
from app.models import Configuracion, User
from app.schemas import (
    ActualizarEmailRequest, LoginRequest, OlvidePasswordRequest,
    TokenResponse, CambiarPasswordRequest,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    token = create_token(user.username)
    return TokenResponse(access_token=token)


@router.put("/cambiar-password")
def cambiar_password(
    data: CambiarPasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(data.password_actual, current_user.password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contraseña actual incorrecta")
    current_user.password = hash_password(data.password_nuevo)
    db.commit()
    return {"mensaje": "Contraseña actualizada"}


@router.put("/actualizar-email")
def actualizar_email(
    data: ActualizarEmailRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.email = data.email
    db.commit()
    return {"mensaje": "Email actualizado", "email": current_user.email}


@router.get("/perfil")
def perfil(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "email": current_user.email}


@router.post("/olvide-password")
def olvide_password(data: OlvidePasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not user.email:
        # Respuesta genérica para no revelar existencia del usuario
        return {"mensaje": "Si el usuario existe y tiene email configurado, recibirás un correo con tu nueva contraseña."}

    config_rows = db.query(Configuracion).all()
    config = {r.clave: r.valor for r in config_rows}
    api_key = config.get("resend_api_key") or ""
    if not api_key:
        raise HTTPException(status_code=503, detail="El servicio de email no está configurado. Contacta al administrador.")

    alphabet = _string.ascii_letters + _string.digits
    nueva_password = "".join(secrets.choice(alphabet) for _ in range(12))
    user.password = hash_password(nueva_password)
    db.commit()

    import resend
    resend.api_key = api_key
    email_from = config.get("email_from") or "Control Reembolsos <noreply@resend.dev>"
    nombre_remitente = config.get("nombre_remitente") or "Control Reembolsos"

    html = f"""
<html>
<body style="font-family: Arial, sans-serif; color: #2c2c2c; max-width: 520px; margin: 0 auto;">
  <div style="background: #0f172a; padding: 28px 24px; border-radius: 8px 8px 0 0; text-align: center;">
    <h2 style="color: white; margin: 0; font-size: 20px;">Reembolsos — Restablecimiento de contraseña</h2>
    <p style="color: #38bdf8; margin: 8px 0 0; font-size: 13px;">{nombre_remitente}</p>
  </div>
  <div style="border: 1px solid #1e293b; border-top: none; padding: 24px; border-radius: 0 0 8px 8px; background: #f8fafc;">
    <p style="font-size: 14px;">Hola <strong>{user.username}</strong>,</p>
    <p style="font-size: 14px;">Tu nueva contraseña temporal es:</p>
    <div style="background: #1e293b; color: #38bdf8; font-family: monospace; font-size: 22px; font-weight: bold;
                padding: 16px; text-align: center; border-radius: 6px; letter-spacing: 3px; margin: 16px 0;">
      {nueva_password}
    </div>
    <p style="font-size: 13px; color: #64748b;">
      Por seguridad, te recomendamos cambiar esta contraseña después de iniciar sesión.
    </p>
  </div>
</body>
</html>
"""
    resend.Emails.send({
        "from": email_from,
        "to": [user.email],
        "subject": "Restablecimiento de contraseña — Control Reembolsos",
        "html": html,
    })

    return {"mensaje": "Si el usuario existe y tiene email configurado, recibirás un correo con tu nueva contraseña."}
