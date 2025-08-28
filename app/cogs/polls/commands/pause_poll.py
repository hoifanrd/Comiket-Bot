import discord

import sql_database
from cogs.polls import handler, utils

class PausePollCommand:

    def __init__(self, cog_poll):
        self.cog_poll = cog_poll
    
    async def on_execute(self, interaction: discord.Interaction, poll_id: int | None):
        if poll_id is None:
            # Try to get the active poll ID in the current channel
            poll_id = await sql_database.get_not_ended_poll_id_in_channel(interaction.channel.id)
        
        if poll_id is None:
            await interaction.response.send_message("❌ 此頻道沒有存在活躍投票", ephemeral=True)
            return

        try:
            creator_id = await sql_database.get_poll_creator(poll_id)
        except ValueError:
            await interaction.response.send_message("❌ ID錯誤，找不到指定的投票", ephemeral=True)
            return

        if not (interaction.user.id == creator_id or utils.check_admin_permission(interaction)):
            await interaction.response.send_message("❌ 權限不足：只有投票創建者或管理員可以結束投票", ephemeral=True)
            return
    
        if await sql_database.get_poll_status(poll_id) != "Active":
            await interaction.response.send_message("❌ 投票並非活躍中", ephemeral=True)
            return
    
        await sql_database.update_poll_status(poll_id, "Paused")
        
        # 更新投票消息
        original_channel_id = await sql_database.get_poll_channel_id(poll_id)
        original_channel = self.cog_poll.bot.get_channel(original_channel_id)

        await handler.update_poll_message(original_channel, poll_id)

        await interaction.response.send_message(f"✅ 投票 `{poll_id}` 已暫停")