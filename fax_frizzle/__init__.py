import discord
from discord.ext import commands
from escpos.escpos import Escpos

from fax_frizzle.faxes import send_fax

intents = discord.Intents.default()
intents.message_content = True


def make_bot(printer: Escpos) -> commands.Bot:
    bot = commands.Bot(command_prefix='$', intents=intents)

    @bot.event
    async def on_ready():
        print(f'We have logged in as {bot.user}')

    @bot.hybrid_command()
    async def fax(ctx: commands.Context):
        await ctx.message.add_reaction("👍")
        send_fax(printer, ctx.message)
        await ctx.message.add_reaction("🖨")

    return bot


def run(token: str, printer: Escpos) -> None:
    bot = make_bot(printer)
    bot.run(token)
