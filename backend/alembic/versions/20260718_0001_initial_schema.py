"""Create initial KiyoDesk tables.

Revision ID: 20260718_0001
Revises:
Create Date: 2026-07-18
"""

import sqlalchemy as sa
from alembic import op

revision = "20260718_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the baseline journal, snapshot, provider, and quota tables."""

    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("timeframe", sa.String(length=10)),
        sa.Column("entry_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("stop_loss", sa.Numeric(20, 8)),
        sa.Column("take_profit", sa.Numeric(20, 8)),
        sa.Column("exit_price", sa.Numeric(20, 8)),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("profit_loss", sa.Numeric(20, 8)),
        sa.Column("notes", sa.Text()),
        sa.Column("strategy_version", sa.String(length=100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_trades_symbol", "trades", ["symbol"])
    op.create_table(
        "trade_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("trade_id", sa.Integer(), sa.ForeignKey("trades.id"), nullable=False),
        sa.Column("price", sa.Numeric(20, 8)),
        sa.Column("funding_rate", sa.Numeric(20, 12)),
        sa.Column("open_interest", sa.Numeric(24, 8)),
        sa.Column("liquidations", sa.Numeric(24, 8)),
        sa.Column("market_bias", sa.String(length=30)),
        sa.Column("volatility", sa.Numeric(20, 8)),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_trade_snapshots_trade_id", "trade_snapshots", ["trade_id"])
    op.create_table(
        "market_data",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("exchange", sa.String(length=50)),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("price", sa.Numeric(20, 8)),
        sa.Column("open_interest", sa.Numeric(24, 8)),
        sa.Column("funding_rate", sa.Numeric(20, 12)),
        sa.Column("liquidation_volume", sa.Numeric(24, 8)),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_market_data_symbol", "market_data", ["symbol"])
    op.create_index("ix_market_data_provider", "market_data", ["provider"])
    op.create_table(
        "providers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "api_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("endpoint", sa.String(length=200), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("remaining", sa.Integer()),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_api_usage_provider", "api_usage", ["provider"])


def downgrade() -> None:
    """Drop all initial schema tables."""

    op.drop_table("api_usage")
    op.drop_table("providers")
    op.drop_table("market_data")
    op.drop_table("trade_snapshots")
    op.drop_table("trades")
