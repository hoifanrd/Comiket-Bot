from discord import Interaction
import discord
import os
import itertools
import asyncio

from cogs.twitter import utils
import sql_database

EMBED_COLORS = [
    discord.Color.red(),
    discord.Color.orange(),
    discord.Color.gold(),
    discord.Color.green(),
    discord.Color.blue(),
    discord.Color.teal(),
    discord.Color.purple(),
    discord.Color.magenta(),
]

class CircleListCommand:

    def __init__(self, cog_twitter):
        self.cog_twitter = cog_twitter

    async def on_execute(self, interaction: Interaction, day: int, specific_hall: str):
        await interaction.response.defer(ephemeral=True)

        if not utils.check_admin_permission(interaction):
            await interaction.followup.send("❌ 您沒有權限使用此命令", ephemeral=True)
            return

        circles = await sql_database.get_circles_by_day_hall(os.environ.get('CURR_EVENT'), day, specific_hall)

        embeds = []
        for idx, (_, block_circles) in enumerate(itertools.groupby(circles, key=lambda x: x.row)):
            embed_lines = []

            circle: utils.CircleForm
            for circle in block_circles:
                line = f"{circle.row}{circle.booth} <#{circle.channel_id}>"
                embed_lines.append(line)
            
            embed = discord.Embed(
                description = "\n".join(embed_lines),
                color = EMBED_COLORS[idx % len(EMBED_COLORS)]
            )
        
            embeds.append(embed)
        
        content = f"📋 **{specific_hall.replace('e', '東').replace('w', '西').replace('s', '南')} 品書清單**"

        # Discord 一次最多只能發送 10 個 embed，因此分批發送
        for i in range(0, len(embeds), 10):
            await interaction.channel.send(embeds=embeds[i:i+10], content=content if i == 0 else None)
            await asyncio.sleep(1)
        
        await interaction.followup.send("✅ 品書清單已發送至頻道", ephemeral=True)