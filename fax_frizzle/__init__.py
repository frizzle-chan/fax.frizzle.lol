import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='$', intents=intents)


@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')


@bot.hybrid_command()
async def fax(ctx: commands.Context):
    print(ctx.message.author.name)
    print(ctx.message.author.display_avatar)
    await ctx.send("This is a hybrid command!")


def run(token: str):
    bot.run(token)
