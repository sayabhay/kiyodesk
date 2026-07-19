"""Environment-based application configuration."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and an optional .env file."""

    app_name: str = "KiyoDesk"
    app_env: str = "development"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite+aiosqlite:///./kiyodesk.db"

    @property
    def async_database_url(self) -> str:
        """Return a database URL suitable for async SQLAlchemy (asyncpg for PostgreSQL).

        asyncpg does not accept psycopg2-style query params such as sslmode=disable.
        We strip those and map them to asyncpg connect_args instead via engine kwargs.
        """
        from urllib.parse import urlparse, urlunparse, urlencode, parse_qs

        url = self.database_url
        if url.startswith("postgresql://") or url.startswith("postgres://"):
            parsed = urlparse(url)
            # Remove params unsupported by asyncpg (sslmode → handled by ssl kwarg)
            params = parse_qs(parsed.query, keep_blank_values=True)
            params.pop("sslmode", None)
            new_query = urlencode({k: v[0] for k, v in params.items()})
            clean = urlunparse(parsed._replace(query=new_query))
            return clean.replace("postgresql://", "postgresql+asyncpg://", 1).replace(
                "postgres://", "postgresql+asyncpg://", 1
            )
        return url  # sqlite+aiosqlite:// already correct

    @property
    def sync_database_url(self) -> str:
        """Return a database URL suitable for synchronous SQLAlchemy (Alembic)."""
        url = self.database_url
        # Strip async drivers
        return (
            url.replace("+aiosqlite", "")
            .replace("+asyncpg", "")
            .replace("postgresql+asyncpg://", "postgresql://")
        )

    # Kiyotaka
    kiyotaka_api_key: str | None = Field(default=None, repr=False)
    kiyotaka_base_url: str = "https://api.kiyotaka.ai"
    kiyotaka_requests_per_minute: int = Field(default=10, ge=1)

    # CoinGecko (optional Pro key for higher rate limits)
    coingecko_api_key: str | None = Field(default=None, repr=False)

    # CCXT provider — exchange-configurable market data
    ccxt_exchange: str = "binance"
    ccxt_market_type: str = "future"
    ccxt_api_key: str | None = Field(default=None, repr=False)
    ccxt_api_secret: str | None = Field(default=None, repr=False)
    ccxt_symbol_map: str = "BTC:BTC/USDT:USDT,ETH:ETH/USDT:USDT"

    # Provider failover order — comma-separated names, first = highest priority
    market_providers: str = "kiyotaka,binance,coingecko"

    # Strategy Engine candle configuration
    strategy_timeframe: str = "15m"
    # HTF override — leave empty to auto-resolve via DEFAULT_HTF_MAP in timeframe_config.py.
    # When set, this exact timeframe is used as HTF regardless of the LTF.
    strategy_htf_timeframe: str = ""
    strategy_candle_limit: int = Field(default=200, ge=50, le=1000)
    strategy_htf_candle_limit: int = Field(default=100, ge=20, le=500)

    cache_seconds: int = Field(default=60, ge=1)
    scheduler_enabled: bool = True
    market_refresh_seconds: int = Field(default=60, ge=60)
    market_symbols: str = "BTC,ETH"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def scheduled_symbols(self) -> list[str]:
        """Return normalized, de-duplicated symbols configured for scheduled refreshes."""

        return list(
            dict.fromkeys(
                item.strip().upper() for item in self.market_symbols.split(",") if item.strip()
            )
        )

    @property
    def active_providers(self) -> list[str]:
        """Return provider names in configured failover priority order."""

        return [item.strip().lower() for item in self.market_providers.split(",") if item.strip()]

    @property
    def ccxt_symbol_mapping(self) -> dict[str, str]:
        """Parse ccxt_symbol_map into {APP_SYMBOL: CCXT_SYMBOL}.

        Format: "BTC:BTC/USDT:USDT,ETH:ETH/USDT:USDT"
        The value is everything after the first colon, allowing CCXT's
        colon-containing symbols like "BTC/USDT:USDT" to work correctly.
        """
        result: dict[str, str] = {}
        for item in self.ccxt_symbol_map.split(","):
            item = item.strip()
            if ":" in item:
                first_colon = item.index(":")
                key = item[:first_colon].strip().upper()
                value = item[first_colon + 1 :].strip()
                if key and value:
                    result[key] = value
        return result


@lru_cache
def get_settings() -> Settings:
    """Return cached validated runtime settings."""

    return Settings()
