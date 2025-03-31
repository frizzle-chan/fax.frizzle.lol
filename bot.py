import os
from dotenv import load_dotenv
from fax_frizzle import run

load_dotenv()
run(token=os.getenv('DISCORD_TOKEN'))