from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    oanda_token: str = ""
    oanda_env: str = "practice"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    telegram_bot_token: str = ""
    symbol: str = "XAU_USD"
    timeframes: str = "D1,H4,H1,M15,M5"
    scheduler_interval_min: int = 5
    signal_threshold: int = 55
    cooldown_min: int = 30
    db_url: str = "sqlite:///./gold_signal.db"

    @property
    def timeframe_list(self) -> list[str]:
        return [t.strip() for t in self.timeframes.split(",") if t.strip()]


def get_settings() -> Settings:
    return Settings()
