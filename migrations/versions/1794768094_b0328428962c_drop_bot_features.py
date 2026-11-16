"""drop bot features: KB topics, summary schedules and summary/spam group columns

Revision ID: b0328428962c
Revises: f6a7b8c9d0e1
Create Date: 2026-11-15

Chappa'ai is listen-only: it no longer summarizes groups, answers from a
knowledge base or alerts on spam. The downgrade recreates the schema (not
the data) as the creating revisions left it.

"""

from typing import Sequence, Union

from alembic import op
import pgvector.sqlalchemy
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b0328428962c"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("kb_topic_message")  # its indexes go with it
    op.drop_index("kb_topic_embedding_idx", table_name="kbtopic")
    op.drop_table("kbtopic")
    op.drop_table("group_summary_schedule")
    for column in (
        "summary_language",
        "notify_on_spam",
        "last_ingest",
        "last_summary_sync",
    ):
        op.drop_column("group", column)


def downgrade() -> None:
    # group columns (f26c6bacce0b, 5a9be1edde3d, d4e5f6a7b8c9)
    op.add_column("group", sa.Column("last_ingest", sa.DateTime(), nullable=True))
    op.add_column("group", sa.Column("last_summary_sync", sa.DateTime(), nullable=True))
    op.execute('UPDATE "group" SET last_ingest = NOW(), last_summary_sync = NOW()')
    op.alter_column("group", "last_ingest", existing_type=sa.DateTime(), nullable=False)
    op.alter_column(
        "group", "last_summary_sync", existing_type=sa.DateTime(), nullable=False
    )
    op.add_column(
        "group",
        sa.Column(
            "notify_on_spam",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "group", sa.Column("summary_language", sa.String(length=2), nullable=True)
    )

    # group_summary_schedule (e5f6a7b8c9d0)
    op.create_table(
        "group_summary_schedule",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("group_jid", sa.String(length=255), nullable=False),
        sa.Column("weekdays", sa.ARRAY(sa.Integer()), nullable=False),
        sa.Column("hour", sa.Integer(), nullable=False),
        sa.Column("minute", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=16), nullable=True),
        sa.Column("last_reason", sa.String(length=64), nullable=True),
        sa.Column("last_message_count", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["group_jid"], ["group.group_jid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "hour BETWEEN 0 AND 23", name="ck_group_summary_schedule_hour"
        ),
        sa.CheckConstraint(
            "minute BETWEEN 0 AND 59", name="ck_group_summary_schedule_minute"
        ),
        sa.CheckConstraint(
            "cardinality(weekdays) > 0",
            name="ck_group_summary_schedule_weekdays_not_empty",
        ),
        sa.CheckConstraint(
            "weekdays <@ ARRAY[0,1,2,3,4,5,6]",
            name="ck_group_summary_schedule_weekdays_range",
        ),
    )
    op.create_index(
        op.f("ix_group_summary_schedule_group_jid"),
        "group_summary_schedule",
        ["group_jid"],
        unique=False,
    )

    # kbtopic (05d84f746fc7)
    op.create_table(
        "kbtopic",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column(
            "group_jid",
            sa.String(length=255),
            sa.ForeignKey("group.group_jid"),
            nullable=True,
        ),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "embedding", pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=False
        ),
        sa.Column("speakers", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
    )
    op.create_index(
        "kb_topic_embedding_idx",
        "kbtopic",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    # kb_topic_message (a1b2c3d4e5f6)
    op.create_table(
        "kb_topic_message",
        sa.Column("kb_topic_id", sa.String(), nullable=False),
        sa.Column("message_id", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["kb_topic_id"], ["kbtopic.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["message.message_id"]),
        sa.PrimaryKeyConstraint("kb_topic_id", "message_id"),
    )
    op.create_index(
        "ix_kb_topic_message_kb_topic_id",
        "kb_topic_message",
        ["kb_topic_id"],
        unique=False,
    )
    op.create_index(
        "ix_kb_topic_message_message_id",
        "kb_topic_message",
        ["message_id"],
        unique=False,
    )
