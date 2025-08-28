import discord

from discord.ext import commands
from discord import app_commands

import sql_database
from cogs.polls.commands import *


# 定義名為 Polls 的 Cog
class Polls(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.commands = {
            'create_poll': CreatePollCommand(self),
            'end_poll': EndPollCommand(self),
            'end_all_polls': EndAllPollCommand(self),
            'pause_poll': PausePollCommand(self),
            'pause_all_polls': PauseAllPollCommand(self),
            'resume_poll': ResumePollCommand(self),
            'resume_all_polls': ResumeAllPollCommand(self),
            'my_order': MyOrderCommand(self)
        }
        

    @app_commands.command(name = "create_poll", description = "為此討論串創建一個新的投票")
    async def create_poll(self, interaction: discord.Interaction):
        await self.commands['create_poll'].on_execute(interaction)
        


    @app_commands.command(name = "end_poll", description = "結束投票")
    @app_commands.describe(poll_id="要結束的投票ID (或 'all' 結束所有投票)")
    async def end_poll(self, interaction: discord.Interaction, poll_id: str | None):
        if poll_id is not None and poll_id.lower() == 'all':
            await self.commands['end_all_polls'].on_execute(interaction)
            return
        
        if poll_id is not None and poll_id.isdigit():
            poll_id = int(poll_id)
        
        if isinstance(poll_id, str):
            await interaction.response.send_message("❌ 無效的投票ID", ephemeral=True)
            return

        await self.commands['end_poll'].on_execute(interaction, poll_id)
        


    @app_commands.command(name = "pause_poll", description = "暫停投票")
    @app_commands.describe(poll_id="要暫停的投票ID (或 'all' 暫停所有投票)")
    async def Pause(self, interaction: discord.Interaction, poll_id: str | None):
        if poll_id is not None and poll_id.lower() == 'all':
            await self.commands['pause_all_polls'].on_execute(interaction)
            return
        
        if poll_id is not None and poll_id.isdigit():
            poll_id = int(poll_id)
        
        if isinstance(poll_id, str):
            await interaction.response.send_message("❌ 無效的投票ID", ephemeral=True)
            return

        await self.commands['pause_poll'].on_execute(interaction, poll_id)
        


    @app_commands.command(name = "resume_poll", description = "恢復投票")
    @app_commands.describe(poll_id="要恢復的投票ID (或 'all' 恢復所有投票)")
    async def Resume(self, interaction: discord.Interaction, poll_id: str | None):
        if poll_id is not None and poll_id.lower() == 'all':
            await self.commands['resume_all_polls'].on_execute(interaction)
            return
        
        if poll_id is not None and poll_id.isdigit():
            poll_id = int(poll_id)
        
        if isinstance(poll_id, str):
            await interaction.response.send_message("❌ 無效的投票ID", ephemeral=True)
            return

        await self.commands['resume_poll'].on_execute(interaction, poll_id)
    

    @app_commands.command(name = "myorder", description = "生成用戶所有投票的品項列表")
    async def my_order(self, interaction: discord.Interaction):
        await self.commands['my_order'].on_execute(interaction)


    @commands.Cog.listener()
    async def on_raw_thread_delete(self, payload: discord.RawThreadDeleteEvent):
        await sql_database.set_delete_poll_by_channel_id(payload.thread_id)


# Cog 載入 Bot 中
async def setup(bot: commands.Bot):
    await bot.add_cog(Polls(bot))
