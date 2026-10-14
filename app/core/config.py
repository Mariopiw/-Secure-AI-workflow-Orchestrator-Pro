from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://workflow:workflow@db:5432/workflow"
    redis_url: str = "redis://redis:6379/0"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    webhook_signing_secret: str = "change-me-webhook-secret"
    webhook_replay_window_seconds: int = 300

    ai_mode: str = "mock"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ai_model: str = "qwen3.5:4b"

    max_workflow_retries: int = 5
    stuck_after_seconds: int = 300
    four_eyes_required: bool = True

    bootstrap_tenant: str = "demo-bank"
    bootstrap_submitter_username: str = "submitter"
    bootstrap_submitter_password: str = "change-submit-password"
    bootstrap_approver_username: str = "approver"
    bootstrap_approver_password: str = "change-approve-password"
    bootstrap_operator_username: str = "operator"
    bootstrap_operator_password: str = "change-operator-password"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
