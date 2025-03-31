import os
import sys

from dotenv import load_dotenv
from escpos.printer import Network

from fax_frizzle import run

load_dotenv()

# Check for required environment variables
required_vars = {
    'PRINTER_HOST': 'Printer host address',
    'PRINTER_PROFILE': 'Printer profile',
    'DISCORD_TOKEN': 'Discord bot token'
}

missing_vars = []
for var_name, var_desc in required_vars.items():
    if not os.getenv(var_name):
        missing_vars.append(f"{var_desc} ({var_name})")

if missing_vars:
    print("Error: The following required environment variables are missing or blank:")
    for var in missing_vars:
        print(f"  - {var}")
    print("\nPlease set these variables in your .env file or environment and try again.")
    sys.exit(1)

printer = Network(
    host=os.getenv('PRINTER_HOST', ''),
    profile=os.getenv('PRINTER_PROFILE', ''))

run(token=os.getenv('DISCORD_TOKEN', ''), printer=printer)
