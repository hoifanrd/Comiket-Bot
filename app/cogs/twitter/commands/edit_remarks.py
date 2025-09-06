import discord
from discord import Interaction

from cogs.twitter import handler
from cogs.twitter.ui.modals import EditRemarksModal
from cogs.twitter import utils

import logging
import sql_database

class EditRemarksCommand:

    def __init__(self, cog_twitter):
        self.cog_twitter = cog_twitter

    async def on_execute(self, interaction: Interaction):
        
        # Check permission (same as voting)
        if not utils.check_execute_permission(interaction):
            await interaction.response.send_message("❌ 您沒有權限使用此命令", ephemeral=True)
            return

        circle_data = await sql_database.get_circle_by_channel_id(interaction.channel_id)
        if circle_data is None:
            await interaction.response.send_message(
                "❌ 此頻道沒有對應的品書資料",
                ephemeral=True
            )
            return
    
        if interaction.channel.type != discord.ChannelType.public_thread \
            and interaction.channel.type != discord.ChannelType.private_thread:
            logging.error(f"Channel is stored in 'circles' table but is not Thread: {interaction.channel_id}")
            await interaction.response.send_message(
                "❌ 發生錯誤，無法編輯備註",
                ephemeral=True
            )
            return

        modal = EditRemarksModal(current_remarks=circle_data.remarks, title=f"編輯 {circle_data.circle_name} 的備註")
        await interaction.response.send_modal(modal)
        await modal.wait()

        if modal.new_remarks == circle_data.remarks:
            await interaction.followup.send(
                "✅ 備註沒有變更",
                ephemeral=True
            )
            return
        
        await sql_database.update_circle_remarks_by_channel_id(interaction.channel_id, modal.new_remarks)
        res = await handler.update_shinagaki_message(interaction.channel)

        if not res:
            await interaction.followup.send(
                "❌ 無法編輯初始訊息",
                ephemeral=True
            )
            return
        
        old_remarks = discord.utils.escape_mentions(f"`{circle_data.remarks}`") if circle_data.remarks else "(無)"
        new_remarks = discord.utils.escape_mentions(f"`{modal.new_remarks}`") if modal.new_remarks else "(無)"
        await interaction.followup.send(
            f"✅ 備註已更新: {old_remarks} → {new_remarks}",
            ephemeral=False
        )
    