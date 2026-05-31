"""CLI entrypoint for the periodic Guardian report (run by a systemd timer).

Usage:
    python -m guardian.app.reporting.cli --send
    python -m guardian.app.reporting.cli            # build + print only

Reads configuration from the environment (the same GUARDIAN_* variables used by
the service), so it works without the HTTP API being up or auth being involved.
"""

from __future__ import annotations

import argparse
import asyncio

from guardian.app.alerting import GuardianTelegramClient, GuardianTelegramConfig
from guardian.app.config import get_config
from guardian.app.reporting.report_service import GuardianReportService
from guardian.app.storage import GuardianSQLiteStore, GuardianStorageConfig


async def _run(send: bool) -> int:
    store = GuardianSQLiteStore(GuardianStorageConfig.from_env())
    telegram = GuardianTelegramClient(GuardianTelegramConfig.from_env())
    service = GuardianReportService(store=store, telegram_client=telegram)
    try:
        result = await service.generate_and_send(send=send)
    finally:
        await telegram.aclose()

    print(result.report.text)
    if send:
        if result.sent:
            print("\n[report] gesendet: ok")
        else:
            print(f"\n[report] nicht gesendet: {result.send_skipped_reason or result.send_error}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="PI Guardian periodischer Statusbericht")
    parser.add_argument("--send", action="store_true", help="Bericht zusaetzlich per Telegram senden")
    args = parser.parse_args()
    # Touch config so a broken config surfaces clearly in the timer logs.
    get_config()
    return asyncio.run(_run(send=args.send))


if __name__ == "__main__":
    raise SystemExit(main())
