"""Central configuration. All secrets/integration points read from env so the
simulated externals can be swapped for the real ones (Polygon, cloud Face API,
Claude) without touching application code."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core
    database_url: str = "postgresql+psycopg2://examshield:examshield@db:5432/examshield"
    jwt_secret: str = "dev-only-change-me-in-production"
    jwt_alg: str = "HS256"
    jwt_ttl_minutes: int = 720

    # PaperVault — the server-held half of the split AES-256 key lives here.
    # In production this would be an HSM / env-secured vault.
    server_key_seed: str = "examshield-server-vault-seed-do-not-share"

    # VerifyGate — face match threshold (PRD: score >= 0.85 auto-passes).
    face_match_threshold: float = 0.85

    # ChainLedger — simulated Polygon. Set to a real RPC + contract to go live.
    chain_simulated: bool = True
    chain_explorer_base: str = "https://amoy.polygonscan.com/tx/"

    # IntegrityAI — set ANTHROPIC_API_KEY + ai_use_claude=true to use real Claude.
    ai_use_claude: bool = False
    anthropic_api_key: str = ""
    ai_model: str = "claude-sonnet-4-6"

    cors_origins: str = "*"


settings = Settings()
