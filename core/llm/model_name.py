from __future__ import annotations

import argparse
import json
import os

from dotenv import find_dotenv, load_dotenv
from openai import OpenAI


DEFAULT_CREDENTIAL_PROFILES = (
    ("GPT_sub2api_apikey", "GPT_sub2api_URL"),
    ("GPT_sub2api_apikey_2", "GPT_sub2api_URL"),
    ("apihy_API_KEY_qwen", "apihy_BASE_URL"),
    ("apihy_API_KEY_deepseek", "apihy_BASE_URL"),
    ("OPENROUTER_API_KEY", "OPENROUTER_BASE_URL"),
)
SELECTOR_API_KEY_ENV = "MODEL_NAME_API_KEY_ENV"
SELECTOR_BASE_URL_ENV = "MODEL_NAME_BASE_URL_ENV"


load_dotenv(find_dotenv(usecwd=True), override=False)


def _read_env(env_name: str) -> str:
    return os.getenv(env_name, "").strip()


def _pick_env_name(
    *,
    explicit_env: str | None,
    selector_env: str,
    fallback_envs: tuple[str, ...],
) -> str:
    candidate = str(explicit_env or "").strip()
    if candidate:
        return candidate

    selector_value = _read_env(selector_env)
    if selector_value:
        return selector_value

    for env_name in fallback_envs:
        if _read_env(env_name):
            return env_name
    return fallback_envs[0]


def _pick_default_env_pair() -> tuple[str, str]:
    for api_key_env, base_url_env in DEFAULT_CREDENTIAL_PROFILES:
        if _read_env(api_key_env) and _read_env(base_url_env):
            return api_key_env, base_url_env
    return DEFAULT_CREDENTIAL_PROFILES[0]


def resolve_credentials(
    *,
    api_key_env: str | None = None,
    base_url_env: str | None = None,
) -> tuple[str, str, str, str]:
    default_api_key_env, default_base_url_env = _pick_default_env_pair()
    resolved_api_key_env = str(api_key_env or "").strip() or _read_env(SELECTOR_API_KEY_ENV)
    resolved_base_url_env = str(base_url_env or "").strip() or _read_env(SELECTOR_BASE_URL_ENV)
    if not resolved_api_key_env and not resolved_base_url_env:
        resolved_api_key_env, resolved_base_url_env = default_api_key_env, default_base_url_env
    elif not resolved_api_key_env:
        resolved_api_key_env = default_api_key_env
    elif not resolved_base_url_env:
        resolved_base_url_env = default_base_url_env

    api_key = _read_env(resolved_api_key_env)
    base_url = _read_env(resolved_base_url_env)
    if not api_key or not base_url:
        raise ValueError(
            "Missing credentials. "
            f"Tried api key env `{resolved_api_key_env}` and base url env `{resolved_base_url_env}`."
        )
    return api_key, base_url, resolved_api_key_env, resolved_base_url_env


def list_model_names(
    *,
    api_key_env: str | None = None,
    base_url_env: str | None = None,
) -> list[str]:
    api_key, base_url, _, _ = resolve_credentials(
        api_key_env=api_key_env,
        base_url_env=base_url_env,
    )
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=60)
    response = client.models.list()
    return [
        model_id
        for item in getattr(response, "data", [])
        if (model_id := getattr(item, "id", None))
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="List models from one OpenAI-compatible base URL.")
    parser.add_argument("--api-key-env", help="Env var name for the API key, e.g. BOYUE_API_KEY")
    parser.add_argument("--base-url-env", help="Env var name for the base URL, e.g. BOYUE_BASE_URL")
    args = parser.parse_args()

    _, _, resolved_api_key_env, resolved_base_url_env = resolve_credentials(
        api_key_env=args.api_key_env,
        base_url_env=args.base_url_env,
    )
    model_names = list_model_names(
        api_key_env=resolved_api_key_env,
        base_url_env=resolved_base_url_env,
    )
    print(
        json.dumps(
            {
                "api_key_env": resolved_api_key_env,
                "base_url_env": resolved_base_url_env,
                "models": model_names,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
