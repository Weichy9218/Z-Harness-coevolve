#!/usr/bin/env python3
"""Smoke-check the copied galaxy-selfevolve API client with one request."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv

from core.llm import instantiate_llm_client


REPO_ROOT = Path(__file__).resolve().parents[1]


async def main_async() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", default="gpt_sub2api")
    parser.add_argument("--model", default="gpt-5.4")
    parser.add_argument("--api-key-env", default=None)
    parser.add_argument("--base-url-env", default=None)
    parser.add_argument("--reasoning-effort", default=None)
    parser.add_argument("--extra-body-json", default=None)
    parser.add_argument("--prompt", default="Return exactly: API_OK")
    parser.add_argument("--max-tokens", type=int, default=64)
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env", override=False)
    client_args = {
        "model": args.model,
        "temperature": 0.0,
        "max_tokens": args.max_tokens,
    }
    if args.api_key_env:
        client_args["api_key_env"] = args.api_key_env
    if args.base_url_env:
        client_args["base_url_env"] = args.base_url_env
    if args.reasoning_effort:
        client_args["reasoning_effort"] = args.reasoning_effort
    if args.extra_body_json:
        client_args["extra_body"] = json.loads(args.extra_body_json)
    client = instantiate_llm_client(args.client, client_args)
    try:
        response = await client.chat([{"role": "user", "content": args.prompt}])
        print(response.content.strip())
        print(response.usage)
    finally:
        await client.aclose()


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
