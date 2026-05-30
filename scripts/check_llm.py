#!/usr/bin/env python3
"""Smoke-check the copied galaxy-selfevolve API client with one request."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv

from core.llm import instantiate_llm_client


REPO_ROOT = Path(__file__).resolve().parents[1]


async def main_async() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", default="gpt_sub2api")
    parser.add_argument("--model", default="gpt-5.4")
    parser.add_argument("--prompt", default="Return exactly: API_OK")
    parser.add_argument("--max-tokens", type=int, default=64)
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env", override=False)
    client = instantiate_llm_client(
        args.client,
        {
            "model": args.model,
            "temperature": 0.0,
            "max_tokens": args.max_tokens,
        },
    )
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

