"""Database models for CierreSucursales application."""
from sqlalchemy import Column, Integer, String, Index
from .extensions import db


class CierreSucursal(db.Model):
    """ORM model for the main CierreSucursales table."""

    __tablename__ = "CierreSucursales4"
    __table_args__ = (
        {"schema": "dbo"},
        Index("ix_cs4_departamento", "Departamento"),
        Index("ix_cs4_departamento_accion", "Departamento", "Accion"),
    )

    id = Column("ID", Integer, primary_key=True)
    ceco = Column("Ceco", String(50), nullable=False)
    departamento = Column("Departamento", String(100), nullable=False)
    accion = Column("Accion", String(50), nullable=False)
