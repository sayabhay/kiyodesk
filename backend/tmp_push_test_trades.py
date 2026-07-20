from datetime import datetime
from decimal import Decimal
import asyncio

from app.database.session import AsyncSessionLocal
from app.repositories.settings_repository import SettingsRepository
from app.repositories.opportunity_repository import OpportunityRepository
from app.runtime.opportunity_manager import OpportunityManager
from app.runtime.deduplicator import Deduplicator
from app.domain.strategy.models.config import StrategyConfig
from app.domain.strategy.models.trade_setup import TradeSetup

async def main():
    async with AsyncSessionLocal() as session:
        settings_repo = SettingsRepository(session)
        settings = await settings_repo.get()
        if settings is None:
            settings = await settings_repo.create_default({
                "risk_percent": Decimal("0.5"),
                "fixed_risk": Decimal("50"),
                "account_balance": Decimal("10000"),
                "execution_mode": "paper",
            })
            print("Created DashboardSettings row with id", settings.id)
        else:
            print("Using existing DashboardSettings row id", settings.id)

        repo = OpportunityRepository(session)
        manager = OpportunityManager(repo, Deduplicator(tolerance=Decimal("0.01")))

        setups = [
            TradeSetup(
                symbol="BTC",
                direction="long",
                entry=Decimal("64000"),
                stop_loss=Decimal("63500"),
                take_profit=Decimal("65000"),
                risk_reward=Decimal("2.0"),
                timeframe="15m",
                reasons=["Bullish BOS confirmed"],
                warnings=[],
                ote_top=Decimal("63900"),
                ote_bottom=Decimal("63700"),
                leg_low=Decimal("63000"),
                leg_high=Decimal("64500"),
                timestamp=datetime(2026, 1, 1, 0, 0),
                config_snapshot=StrategyConfig(),
            ),
            TradeSetup(
                symbol="ETH",
                direction="short",
                entry=Decimal("3200"),
                stop_loss=Decimal("3250"),
                take_profit=Decimal("3050"),
                risk_reward=Decimal("2.0"),
                timeframe="1h",
                reasons=["Bearish BOS confirmed"],
                warnings=[],
                ote_top=Decimal("3230"),
                ote_bottom=Decimal("3180"),
                leg_low=Decimal("3050"),
                leg_high=Decimal("3300"),
                timestamp=datetime(2026, 1, 1, 1, 0),
                config_snapshot=StrategyConfig(),
            ),
            TradeSetup(
                symbol="BTC",
                direction="long",
                entry=Decimal("64500"),
                stop_loss=Decimal("64200"),
                take_profit=Decimal("65500"),
                risk_reward=Decimal("1.5"),
                timeframe="1h",
                reasons=["Secondary long signal"],
                warnings=[],
                ote_top=Decimal("64400"),
                ote_bottom=Decimal("64250"),
                leg_low=Decimal("64000"),
                leg_high=Decimal("65000"),
                timestamp=datetime(2026, 1, 2, 0, 0),
                config_snapshot=StrategyConfig(),
            ),
        ]

        for setup in setups:
            opp = await manager.create_or_update(setup)
            print(
                f"Persisted opportunity {opp.id}: {opp.symbol} {opp.direction} {opp.timeframe} entry={opp.entry} status={opp.status}"
            )
            print("  trade_snapshot_json=", opp.trade_snapshot_json)

        print("\nCurrent active opportunities:")
        active = await repo.list_active()
        for opp in active:
            print(
                f"  {opp.id}: {opp.symbol} {opp.direction} {opp.timeframe} entry={opp.entry} status={opp.status} trade_snapshot_json={opp.trade_snapshot_json}"
            )

if __name__ == "__main__":
    asyncio.run(main())
