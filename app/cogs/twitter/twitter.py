
from discord.ext import commands
from discord import app_commands, Interaction
import discord

from cogs.twitter.commands import *
from cogs.twitter import database

import sql_database

# 定義名為 Twitter 的 Cog
class Twitter(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.commands = {
            'magic': MagicCommand(self),
            'edit_remarks': EditRemarksCommand(self),
            'circle_list': CircleListCommand(self)
        }
    
    @app_commands.command(name = "magic", description = "從 Twitter/Pixiv 自動建立品書")
    @app_commands.describe(url = "品書 URL")
    async def magic(self, interaction: Interaction, url: str):
        await self.commands['magic'].on_execute(interaction, url)
        

    @app_commands.command(name = "edit_remarks", description = "編輯品書備註")
    async def edit_remarks(self, interaction: Interaction):
        await self.commands['edit_remarks'].on_execute(interaction)


    @app_commands.command(name = "circle_list", description = "列出品書清單")
    @app_commands.describe(day = "N日目", specific_hall = "場地")
    @app_commands.choices(
        day=[app_commands.Choice(name=str(i), value=i) for i in range(1, 3)],
        specific_hall=[app_commands.Choice(name=hall.replace('e', '東').replace('w', '西').replace('s', '南'),
                                value=hall) for hall in database.get_all_specific_halls()]
    )
    async def circle_list(self, interaction: Interaction, day: app_commands.Choice[int], specific_hall: app_commands.Choice[str]):
        await self.commands['circle_list'].on_execute(interaction, day.value, specific_hall.value)


    @commands.Cog.listener()
    async def on_raw_thread_delete(self, payload: discord.RawThreadDeleteEvent):
        await sql_database.delete_circle_by_channel_id(payload.thread_id)


# Cog 載入 Bot 中
async def setup(bot: commands.Bot):
    database.preprocess_data()
    await bot.add_cog(Twitter(bot))

