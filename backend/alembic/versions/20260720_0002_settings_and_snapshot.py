"""Add dashboard_settings and trade_snapshot_json to trade_opportunities.

Revision ID: 20260720_0002
Revises: 20260718_0001
Create Date: 2026-07-20
"""

import sqlalchemy as sa
from alembic import op

revision = "20260720_0002"
down_revision = "20260718_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trade_opportunities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("strategy", sa.String(length=100), nullable=False),
        sa.Column("strategy_version", sa.String(length=100), nullable=True),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=True),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("entry", sa.Numeric(20, 8), nullable=False),
        sa.Column("stop_loss", sa.Numeric(20, 8), nullable=False),
        sa.Column("take_profit", sa.Numeric(20, 8), nullable=False),
        sa.Column("risk_reward", sa.Numeric(10, 6), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trade_id", sa.Integer(), sa.ForeignKey("trades.id"), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("market_regime", sa.String(length=50), nullable=True),
        sa.Column("trade_setup_json", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("trade_snapshot_json", sa.Text(), nullable=True),
        sa.Column("entry_tolerance", sa.Numeric(20, 8), nullable=False),
    )
    op.create_index("ix_trade_opportunities_strategy", "trade_opportunities", ["strategy"])
    op.create_index("ix_trade_opportunities_symbol", "trade_opportunities", ["symbol"])
    op.create_index("ix_trade_opportunities_status", "trade_opportunities", ["status"])
    op.create_index("ix_trade_opportunities_trade_id", "trade_opportunities", ["trade_id"])

    op.create_table(
        "dashboard_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbols", sa.Text(), nullable=True),
        sa.Column("timeframes", sa.Text(), nullable=True),
        sa.Column("htf_mapping_json", sa.Text(), nullable=True),
        sa.Column("risk_percent", sa.Numeric(10, 6), nullable=True),
        sa.Column("fixed_risk", sa.Numeric(20, 8), nullable=True),
        sa.Column("stop_loss_mode", sa.String(length=30), nullable=True),
        sa.Column("swing_buffer", sa.Numeric(10, 6), nullable=True),
        sa.Column("reward_ratio", sa.Numeric(10, 6), nullable=True),
        sa.Column("max_concurrent_trades", sa.Integer(), nullable=True),
        sa.Column("max_daily_loss", sa.Numeric(20, 8), nullable=True),
        sa.Column("max_weekly_loss", sa.Numeric(20, 8), nullable=True),
        sa.Column("execution_mode", sa.String(length=50), nullable=True),
        sa.Column("account_balance", sa.Numeric(24, 8), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
    )
    op.create_index("ix_dashboard_settings_id", "dashboard_settings", ["id"])


def downgrade() -> None:
    op.drop_index("ix_trade_opportunities_trade_id", table_name="trade_opportunities")
    op.drop_index("ix_trade_opportunities_status", table_name="trade_opportunities")
    op.drop_index("ix_trade_opportunities_symbol", table_name="trade_opportunities")
    op.drop_index("ix_trade_opportunities_strategy", table_name="trade_opportunities")
    op.drop_table("trade_opportunities")
    op.drop_index("ix_dashboard_settings_id", table_name="dashboard_settings")
    op.drop_table("dashboard_settings")
