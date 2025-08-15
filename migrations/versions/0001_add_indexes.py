"""Add indexes for performance"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001_add_indexes"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_cs4_departamento",
        "CierreSucursales4",
        ["Departamento"],
        schema="dbo",
    )
    op.create_index(
        "ix_cs4_departamento_accion",
        "CierreSucursales4",
        ["Departamento", "Accion"],
        schema="dbo",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cs4_departamento",
        table_name="CierreSucursales4",
        schema="dbo",
    )
    op.drop_index(
        "ix_cs4_departamento_accion",
        table_name="CierreSucursales4",
        schema="dbo",
    )
