"""
Discord input source.
"""
from datetime import datetime
from io import BytesIO
from typing import List, Optional, Union

import arrow
import discord
import requests
from cachetools import TTLCache, cached
from discord import Attachment, Member, User
from PIL import Image

from fax_frizzle.fax import Fax
from fax_frizzle.render.engine import convert_fax_to_preview
from fax_frizzle.service import FaxService
from fax_frizzle.util import is_owner

IMAGE_CONTENT_TYPES = ('image/png', 'image/jpeg')


@cached(cache=TTLCache(maxsize=10, ttl=60 * 60 * 24))
def download_avatar(avatar_url: str) -> Image.Image:
    """
    Download an avatar image from a URL and save it as a PIL Image object.

    I expect this to be fairly sleepy and mostly just wanna guard against the
    same user spamming over and over. So keeping 10 avatars in memory for 24
    hours should be okay.
    """

    response = requests.get(avatar_url)
    response.raise_for_status()
    img = Image.open(BytesIO(response.content))
    img.thumbnail((150, 150))
    return img


def download_attachment_image(url: str) -> Image.Image:
    response = requests.get(url)
    response.raise_for_status()
    img = Image.open(BytesIO(response.content))
    # Force the decode now: the BytesIO goes out of scope on return, and the
    # service is what clamps the size.
    img.load()
    return img


def build_fax(user: Union[User, Member],
              text: str,
              ts: datetime,
              attachments: Optional[List[Attachment]] = None) -> Fax:
    """Turn a Discord author plus message content into a source-neutral Fax."""
    avatar = None
    if user.avatar:
        avatar = download_avatar(user.avatar.url).resize((150, 150))

    image_attachments = []
    if attachments:
        for attachment in attachments:
            if attachment.content_type in IMAGE_CONTENT_TYPES:
                image_attachments.append(download_attachment_image(attachment.url))

    return Fax(user_name=user.name,
               text=text,
               ts=ts,
               user_avatar=avatar,
               image_attachments=image_attachments)


def make_bot(service: FaxService) -> discord.Client:
    intents = discord.Intents.default()
    intents.message_content = True

    client = discord.Client(intents=intents)
    allowed_contexts = discord.app_commands.AppCommandContext(guild=True,
                                                              dm_channel=False,
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
            fax_img = await service.print_fax(build_fax(user=message.author,
                                                        ts=message.created_at,
                                                        text=message.content,
                                                        attachments=message.attachments))
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] Received fax DM from {message.author.name}")
            await message.add_reaction('✅')
            with BytesIO() as fax_stream:
                fax_img = convert_fax_to_preview(fax_img, ts=arrow.now().datetime)
                fax_img.save(fax_stream, "PNG")
                fax_stream.seek(0)
                discord_img = discord.File(fp=fax_stream, filename="fax.png")
                await message.channel.send(file=discord_img)
        except Exception as e:
            await message.add_reaction('❌')
            raise e

    @tree.command(description="Send a fax!")
    async def fax(interaction: discord.Interaction, text: str):
        try:
            await service.print_fax(build_fax(user=interaction.user,
                                              ts=interaction.created_at,
                                              text=text))
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] Received fax command from {interaction.user.name}")
            await interaction.response.send_message("Fax sent ✅", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("Fax failed ❌. Go tell frizzle to fix it!!", ephemeral=True)
            raise e

    return client


async def run(service: FaxService, token: str) -> None:
    """Connect to Discord and serve until cancelled."""
    # Client.run() does this for us, but we need the awaitable form so several
    # sources can share one event loop.
    discord.utils.setup_logging()
    client = make_bot(service)
    async with client:
        await client.start(token)
