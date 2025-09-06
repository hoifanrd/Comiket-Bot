import discord

import sql_database
from cogs.polls import handler, utils

class EndPollCommand:

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

        poll_status = await sql_database.get_poll_status(poll_id)
        if poll_status != "Active" and poll_status != "Paused":
            await interaction.response.send_message("❌ 投票已經結束", ephemeral=True)
            return
    
        await self._end_poll(interaction, poll_id)


    async def _end_poll(self, interaction: discord.Interaction, poll_id: int):

        await sql_database.update_poll_status(poll_id, "Ended")
        
        # 更新投票消息
        results_embed = await handler.generate_results_embed(poll_id)
        original_channel_id = await sql_database.get_poll_channel_id(poll_id)
        original_channel = self.cog_poll.bot.get_channel(original_channel_id)

        if interaction.channel.id == original_channel_id:
            # 當前頻道就是原始頻道，直接發送
            await interaction.response.send_message(f"📊 **投票結束！最終結果：**", embed=results_embed)
        else:
            # 當前頻道不是原始頻道
            if original_channel:
                # 將結果發送到原始頻道
                await original_channel.send(f"📊 **投票結束！最終結果：**", embed=results_embed)
                # 在當前頻道發送提示
                await interaction.response.send_message(f"✅ 投票結果已發送到原始頻道：<#{original_channel_id}>", ephemeral=True)
            else:
                # 原始頻道不存在，在當前頻道發送結果
                await interaction.response.send_message(f"📊 **投票結束！最終結果：**", embed=results_embed)
        
        await handler.update_poll_message(original_channel, poll_id)
        
        confirm_embed = discord.Embed(
            description=f"✅ 投票 ID: `{poll_id}` 已成功結束",
            color=discord.Color.green()
        )
        
        # 確認訊息始終在當前頻道發送
        await interaction.followup.send(embed=confirm_embed)