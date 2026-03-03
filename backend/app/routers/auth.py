from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import verify_password, hash_password, create_token, get_current_user
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, TokenResponse, CambiarPasswordRequest

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
