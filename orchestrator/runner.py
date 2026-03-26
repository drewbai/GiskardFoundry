"""Runtime entrypoint for hosting Susan_Calvin via Microsoft Agent Framework."""

from __future__ import annotations

import asyncio

from giskardfoundry.susan_calvin.orchestrator import run_susan_calvin_server


def main() -> None:
    """CLI entrypoint for local execution."""
    asyncio.run(run_susan_calvin_server())


if __name__ == "__main__":
    main()
