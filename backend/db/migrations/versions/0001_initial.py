"""Initial durable CampusOS records."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "students",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("contact_handle", sa.String(80), nullable=False, unique=True),
        sa.Column("agent_id", sa.String(80), nullable=False, unique=True),
        sa.Column("ceiling", sa.String(20), nullable=False),
        sa.Column("discord_id", sa.String(80)),
    )
    op.create_table(
        "negotiations",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("data", sa.JSON, nullable=False),
    )
    op.create_table(
        "grants",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("owner", sa.String(100), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("agent", sa.String(80), nullable=False),
        sa.Column("negotiation", sa.String(80), sa.ForeignKey("negotiations.id"), nullable=False),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("expires", sa.String(50), nullable=False),
        sa.Column("revoked", sa.Boolean, nullable=False),
    )
    op.create_table(
        "commitments",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("owner", sa.String(100), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("data", sa.JSON, nullable=False),
    )
    op.create_table(
        "approvals",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("owner", sa.String(100), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("negotiation", sa.String(80), sa.ForeignKey("negotiations.id"), nullable=False),
        sa.Column("data", sa.JSON, nullable=False),
        sa.Column("decision", sa.String(20)),
        sa.Column("decided_at", sa.String(50)),
        sa.Column("decided_version", sa.Integer),
    )
    op.create_table(
        "channels",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("platform_id", sa.String(80), nullable=False, unique=True),
        sa.Column("guild", sa.String(80), nullable=False),
        sa.Column("bot", sa.String(100), nullable=False),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("data", sa.JSON, nullable=False),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("at", sa.String(50), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("resource", sa.String(100), nullable=False),
        sa.Column("detail", sa.Text, nullable=False),
    )
    for table, columns in (
        ("grants", ("owner", "agent", "negotiation")),
        ("commitments", ("owner",)),
        ("approvals", ("owner", "negotiation")),
    ):
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade():
    for table in (
        "audit_log",
        "channels",
        "approvals",
        "commitments",
        "grants",
        "negotiations",
        "students",
    ):
        op.drop_table(table)
