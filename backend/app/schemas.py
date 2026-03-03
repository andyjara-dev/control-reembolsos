from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PagoBase(BaseModel):
    fecha_pago: date
    concepto: str
    proveedor: str
    monto: Decimal
    moneda: str = "USD"
    monto_clp: Decimal | None = None
    tipo: str  # REEMBOLSO, PROVISION
    estado: str = "PENDIENTE"
    fecha_solicitud: date | None = None
    fecha_reembolso: date | None = None
    comprobante: str | None = None
    archivo_comprobante: str | None = None
    imagen_cobro: str | None = None
    imagen_reembolso: str | None = None
    notas: str | None = None


class PagoCreate(PagoBase):
    pass


class PagoUpdate(BaseModel):
    fecha_pago: date | None = None
    concepto: str | None = None
    proveedor: str | None = None
    monto: Decimal | None = None
    moneda: str | None = None
    monto_clp: Decimal | None = None
    tipo: str | None = None
    estado: str | None = None
    fecha_solicitud: date | None = None
    fecha_reembolso: date | None = None
    comprobante: str | None = None
    imagen_cobro: str | None = None
    imagen_reembolso: str | None = None
    notas: str | None = None


class ImagenPagoResponse(BaseModel):
    id: int
    pago_id: int
    tipo_imagen: str
    filename: str

    model_config = {"from_attributes": True}


class PagoResponse(PagoBase):
    id: int
    created_at: datetime
    updated_at: datetime
    imagenes_cobro: list[ImagenPagoResponse] = []
    imagenes_reembolso: list[ImagenPagoResponse] = []

    model_config = {"from_attributes": True}

    @classmethod
    def from_pago(cls, pago):
        data = {c.key: getattr(pago, c.key) for c in pago.__table__.columns}
        data["imagenes_cobro"] = [img for img in pago.imagenes if img.tipo_imagen == "cobro"]
        data["imagenes_reembolso"] = [img for img in pago.imagenes if img.tipo_imagen == "reembolso"]
        return cls.model_validate(data)


class ResumenResponse(BaseModel):
    total_pendiente_reembolso: Decimal
    total_pendiente_provision: Decimal
    total_solicitado_reembolso: Decimal
    total_solicitado_provision: Decimal
    total_pagado_mes: Decimal
    cantidad_pendientes: int
    cantidad_no_pagados: int


class CambiarPasswordRequest(BaseModel):
    password_actual: str
    password_nuevo: str


class PagosListResponse(BaseModel):
    items: list[PagoResponse]
    total: int
    total_monto_clp: float
    total_monto_usd: float
