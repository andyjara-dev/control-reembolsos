from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import String, Date, DateTime, Numeric, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)


class Pago(Base):
    __tablename__ = "pagos"

    id: Mapped[int] = mapped_column(primary_key=True)
    fecha_pago: Mapped[date] = mapped_column(Date, nullable=False)
    concepto: Mapped[str] = mapped_column(String(255), nullable=False)
    proveedor: Mapped[str] = mapped_column(String(100), nullable=False)
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    moneda: Mapped[str] = mapped_column(String(10), default="USD")
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)  # REEMBOLSO, PROVISION
    estado: Mapped[str] = mapped_column(String(20), default="PENDIENTE")  # PENDIENTE, SOLICITADO, PAGADO
    fecha_solicitud: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_reembolso: Mapped[date | None] = mapped_column(Date, nullable=True)
    monto_clp: Mapped[Decimal | None] = mapped_column(Numeric(12, 0), nullable=True)
    comprobante: Mapped[str | None] = mapped_column(String(100), nullable=True)
    archivo_comprobante: Mapped[str | None] = mapped_column(String(255), nullable=True)
    imagen_cobro: Mapped[str | None] = mapped_column(String(255), nullable=True)
    imagen_reembolso: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notas: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    imagenes: Mapped[list["ImagenPago"]] = relationship(back_populates="pago", cascade="all, delete-orphan")


class ImagenPago(Base):
    __tablename__ = "imagenes_pago"

    id: Mapped[int] = mapped_column(primary_key=True)
    pago_id: Mapped[int] = mapped_column(ForeignKey("pagos.id"), nullable=False)
    tipo_imagen: Mapped[str] = mapped_column(String(20), nullable=False)  # "cobro" o "reembolso"
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    pago: Mapped["Pago"] = relationship(back_populates="imagenes")
