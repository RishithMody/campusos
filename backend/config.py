import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_url: str
    jwt_key: str
    inference_mode: str
    jwt_issuer: str = "campusos"
    jwt_audience: str = "campusos-api"
    redis_ttl: int = 300
    vllm_url: str = ""
    vllm_key: str = ""
    vllm_model: str = ""
    discord_token: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        mode = os.environ.get("CAMPUSOS_INFERENCE_MODE", "")
        if mode not in {"mock", "vllm"}:
            raise ValueError("CAMPUSOS_INFERENCE_MODE must explicitly be mock or vllm")
        required = ["CAMPUSOS_DATABASE_URL", "CAMPUSOS_REDIS_URL", "CAMPUSOS_JWT_KEY"]
        if any(not os.environ.get(key) for key in required):
            raise ValueError("Database, Redis and JWT configuration are required")
        key = os.environ["CAMPUSOS_JWT_KEY"]
        if len(key) < 32:
            raise ValueError("JWT key must have at least 32 characters")
        result = cls(
            database_url=os.environ[required[0]],
            redis_url=os.environ[required[1]],
            jwt_key=key,
            inference_mode=mode,
            vllm_url=os.environ.get("CAMPUSOS_VLLM_URL", ""),
            vllm_key=os.environ.get("CAMPUSOS_VLLM_KEY", ""),
            vllm_model=os.environ.get("CAMPUSOS_VLLM_MODEL", ""),
            discord_token=os.environ.get("CAMPUSOS_DISCORD_TOKEN", ""),
        )
        if mode == "vllm" and not all([result.vllm_url, result.vllm_key, result.vllm_model]):
            raise ValueError("vLLM URL, key and model are required")
        # LangGraph tracing must not export student state to a third party.
        if any(
            os.environ.get(k, "").lower() == "true"
            for k in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2")
        ):
            raise ValueError("External tracing of student data is prohibited")
        return result
