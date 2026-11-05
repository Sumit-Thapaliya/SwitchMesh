"""Fire one representative signal into each SwitchMesh webhook."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor

import httpx


SOURCES = ("telegram", "discord", "sentry", "github")


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate a cross-platform INC-101 burst")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    def fire(source: str) -> tuple[str, str]:
        response = httpx.post(
            f"{args.base_url.rstrip('/')}/webhooks/{source}",
            json={"text": f"checkout FREESHIP TypeError reported by {source}"},
            timeout=10,
        )
        response.raise_for_status()
        return source, response.json()["incident_id"]

    # Deliver the burst concurrently, matching how cross-platform signals arrive.
    with ThreadPoolExecutor(max_workers=len(SOURCES)) as executor:
        for source, incident_id in executor.map(fire, SOURCES):
            print(f"{source}: {incident_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
