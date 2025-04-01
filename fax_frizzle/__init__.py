from datetime import datetime

import discord
from escpos.escpos import Escpos

from fax_frizzle.faxes import send_fax
from fax_frizzle.util import is_owner


def make_bot(printer: Escpos) -> discord.Client:
    intents = discord.Intents.default()
    intents.message_content = True

    client = discord.Client(intents=intents)
    allowed_contexts = discord.app_commands.AppCommandContext(guild=True,
                                                              dm_channel=True,
                                                              private_channel=True)
    tree = discord.app_commands.CommandTree(client,
                                            allowed_contexts=allowed_contexts)

    @client.event
    async def on_ready():
        print(f'Logged in as {client.user}')

    async def _run_sync(message: discord.Message) -> None:
        if await is_owner(client, message.author):
            print("Syncing commands")
            await tree.sync()
            print("Commands synced")
            await message.reply("Commands synced")

    @client.event
    async def on_message(message: discord.Message) -> None:
        if message.author == client.user:
            return

        if not isinstance(message.channel, discord.DMChannel):
            return

        if message.content.startswith('$sync'):
            await _run_sync(message)
            return

        try:
            await message.add_reaction('🖨')
            await send_fax(printer,
                           user=message.author,
                           ts=message.created_at,
                           text=message.content,
                           attachments=message.attachments)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] Received fax DM from {message.author.name}")
            await message.add_reaction('✅')
        except Exception as e:
            await message.add_reaction('❌')
            raise e

    @tree.command(description="Send a fax!")
    async def fax(interaction: discord.Interaction, text: str):
        await send_fax(printer,
                       user=interaction.user,
                       ts=interaction.created_at,
                       text=text)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] Received fax command from {interaction.user.name}")
        await interaction.response.send_message("Fax sent!", ephemeral=True)

    return client


def run(token: str, printer: Escpos) -> None:
    bot = make_bot(printer)
    bot.run(token)
