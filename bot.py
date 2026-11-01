"""
Entrypoint. Builds the printer, then runs whichever input sources are enabled.

Set FAX_SOURCES to a comma-separated list (default "discord"). Each source
brings its own required environment variables, so running only the HTTP source
needs no Discord credentials at all.
"""
import asyncio
import os
import sys
from typing import Awaitable, Dict, List, NoReturn

from dotenv import load_dotenv
from escpos.printer import Network

from fax_frizzle.service import FaxService
from fax_frizzle.sources import discord_source, http_source

load_dotenv()

DEFAULT_SOURCES = 'discord'

# Needed no matter which sources are enabled.
PRINTER_VARS = {
    'PRINTER_HOST': 'Printer host address',
    'PRINTER_PROFILE': 'Printer profile',
}

# Needed only by the source that names them.
SOURCE_VARS: Dict[str, Dict[str, str]] = {
    'discord': {'DISCORD_TOKEN': 'Discord bot token'},
    'http': {'FAX_HTTP_TOKEN': 'Shared secret for the HTTP fax endpoint'},
}


def _die(*lines: str) -> NoReturn:
    for line in lines:
        print(line)
    sys.exit(1)


def int_env(var: str, default: int) -> int:
    """Read an int from the environment, failing the same way missing vars do.

    A set-but-empty var (`PRINTER_PORT=` in a .env) skips the default, so
    without this a blank line in a config file is a raw ValueError traceback
    instead of a sentence telling you which variable is wrong.
    """
    raw = os.getenv(var)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        _die(f"Error: {var} must be a whole number, got {raw!r}")


def selected_sources() -> List[str]:
    names = [name.strip() for name in os.getenv('FAX_SOURCES', DEFAULT_SOURCES).split(',')]
    names = [name for name in names if name]

    if not names:
        _die("Error: FAX_SOURCES is empty. Nothing would ever send a fax.")

    unknown = [name for name in names if name not in SOURCE_VARS]
    if unknown:
        _die(f"Error: unknown source(s) in FAX_SOURCES: {', '.join(unknown)}",
             f"Known sources: {', '.join(sorted(SOURCE_VARS))}")

    return names


def check_env(names: List[str]) -> None:
    required = dict(PRINTER_VARS)
    for name in names:
        required.update(SOURCE_VARS[name])

    missing = [f"{desc} ({var})" for var, desc in required.items() if not os.getenv(var)]
    if missing:
        _die("Error: The following required environment variables are missing or blank:",
             *(f"  - {var}" for var in missing),
             "\nPlease set these variables in your .env file or environment and try again.")


def build_tasks(service: FaxService, names: List[str]) -> List[Awaitable[None]]:
    tasks: List[Awaitable[None]] = []
    for name in names:
        if name == 'discord':
            tasks.append(discord_source.run(service, token=os.getenv('DISCORD_TOKEN', '')))
        elif name == 'http':
            tasks.append(http_source.run(service,
                                         token=os.getenv('FAX_HTTP_TOKEN', ''),
                                         host=os.getenv('FAX_HTTP_HOST', '127.0.0.1'),
                                         port=int_env('FAX_HTTP_PORT', 8080)))
    return tasks


async def main() -> None:
    sources = selected_sources()
    check_env(sources)

    printer = Network(
        host=os.getenv('PRINTER_HOST', ''),
        port=int_env('PRINTER_PORT', 9100),
        # escpos defaults to 60s. That is a long time to hold a fax hostage when
        # the printer is off, and it's the window the smoke test shortens.
        timeout=int_env('PRINTER_TIMEOUT', 60),
        profile=os.getenv('PRINTER_PROFILE', ''))

    # One service shared by every source: its lock is the only thing serialising
    # ESC/POS on the printer socket.
    service = FaxService(printer)

    print(f"Starting fax sources: {', '.join(sources)}", flush=True)
    # If any source falls over, let the whole process die and get restarted
    # rather than limp along half-deaf.
    await asyncio.gather(*build_tasks(service, sources))


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
