from typing import Union

import discord


async def is_owner(client: discord.Client, user: Union[discord.User, discord.Member]) -> bool:
    app: discord.AppInfo = await client.application_info()  # type: ignore
    if app.team:
        ids = {
            m.id
            for m in app.team.members
            if m.role in (discord.TeamMemberRole.admin, discord.TeamMemberRole.developer)
        }
        return user.id in ids
    else:
        return user.id == app.owner.id
