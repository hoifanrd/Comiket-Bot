import discord
from discord.ui import Button
import asyncio
import traceback

from cogs.polls import utils
from cogs.polls.ui.views import TimeoutView
from cogs.polls import handler

import sql_database

class MovePollCommand:

    def __init__(self, cog_poll):
        self.cog_poll = cog_poll
    
    async def on_execute(self, interaction: discord.Interaction, from_id: int, to_id: int):

        if not utils.check_admin_permission(interaction):
            await interaction.response.send_message("❌ 您沒有權限使用此命令", ephemeral=True)
            return
        
        if from_id == to_id:
            await interaction.response.send_message("❌ 投票ID不能相同！", ephemeral=True)
            return

        try:
            from_status = await sql_database.get_poll_status(from_id)
            if from_status == "Deleted":
                raise ValueError
        except ValueError:
            await interaction.response.send_message(f"❌ 無效的投票ID: `{from_id}`", ephemeral=True)
            return
        
        try:
            to_status = await sql_database.get_poll_status(to_id)
            if to_status == "Deleted":
                raise ValueError
        except ValueError:
            await interaction.response.send_message(f"❌ 無效的投票ID: `{to_id}`", ephemeral=True)
            return

        confirm_embed = discord.Embed(
            title="⚠️ 確認覆蓋投票",
            description=f"確定要將投票 `{from_id}` 覆蓋至投票 `{to_id}` 嗎？\n被覆蓋投票的所有數據將會消失！此操作無法復原！",
            color=discord.Color.orange()
        )
        
        confirm_view = TimeoutView(timeout=60)
        confirm_btn = Button(label="確認覆蓋", style=discord.ButtonStyle.danger)
        cancel_btn = Button(label="取消", style=discord.ButtonStyle.secondary)

        async def confirm_callback(new_interaction: discord.Interaction):
            await new_interaction.response.defer()
            confirm_view.stop()

            confirm_btn.disabled = True
            cancel_btn.disabled = True
            await interaction.edit_original_response(view=confirm_view)

            await self._move_poll(interaction, from_id, to_id)
        
        async def cancel_callback(new_interaction: discord.Interaction):
            await new_interaction.response.defer()
            confirm_view.stop()

            await interaction.edit_original_response(content="操作已取消", embed=None, view=None)
            await asyncio.sleep(2)
            await interaction.delete_original_response()

        confirm_btn.callback = confirm_callback
        cancel_btn.callback = cancel_callback
        confirm_view.add_item(confirm_btn)
        confirm_view.add_item(cancel_btn)

        await interaction.response.send_message(embed=confirm_embed, view=confirm_view, ephemeral=True)
    

    async def _move_poll(self, interaction: discord.Interaction, from_id: int, to_id: int):
        
        to_channel_id = await sql_database.get_poll_channel_id(to_id)
        to_message_id = await sql_database.get_poll_message_id(to_id)
        from_channel_id = await sql_database.get_poll_channel_id(from_id)
        from_message_id = await sql_database.get_poll_message_id(from_id)

        await sql_database.swap_poll_channel_message(from_id, to_id)
        await sql_database.set_delete_poll_by_channel_id(from_channel_id)

        # Update the message in the overwritten poll's channel
        to_channel: discord.Thread = self.cog_poll.bot.get_channel(to_channel_id)
        await handler.update_poll_message(to_channel, from_id)

        # Update the to_poll channel poll id to the overwritten ID
        to_message_partial = to_channel.get_partial_message(to_message_id)
        try:
            to_poll_id_msg: discord.Message = [msg async for msg in to_channel.history(after=to_message_partial, limit=1)][0]
            embed = to_poll_id_msg.embeds[0]
            assert f"投票已創建！ID: `{to_id}`" == embed.description
            embed.description = f"投票已創建！ID: `{from_id}`"
            await to_poll_id_msg.edit(embed=embed)
        except Exception as e:
            traceback.print_exc()
            pass
    
        # Edit the from_id channel message
        from_channel: discord.Thread = self.cog_poll.bot.get_channel(from_channel_id)
        from_message_partial = from_channel.get_partial_message(from_message_id)

        embed = discord.Embed(
            title="📢 投票已遷移:",
            description=to_channel.jump_url,
            color=discord.Color.blue()
        )

        await from_message_partial.edit(embed=embed, view=None, content=None)


        # Send result message to both channels and initiator
        result_embed = discord.Embed(
            description=f"⚠️ 投票 `{to_id}` 已被投票 `{from_id}` 覆蓋",
            color=discord.Color.yellow()
        )
        await to_channel.send(embed=result_embed)

        result_embed = discord.Embed(
            description=f"⚠️ 投票 `{from_id}` 已遷移至 {to_channel.jump_url}",
            color=discord.Color.yellow()
        )
        await from_channel.send(embed=result_embed)

        result_embed = discord.Embed(
            description=f"✅ 投票 `{from_id}` 已成功覆蓋投票 `{to_id}`",
            color=discord.Color.green()
        )
        await interaction.edit_original_response(embed=result_embed, content=None, view=None)

        # Tag the voted users again in the new channel
        res = await sql_database.get_poll_results_for_users(from_id)
        tags = []
        for user_id, _, _ in res:
            tags.append(f"<@{user_id}>")

        if tags:
            tag_str = " ".join(tags)
            await to_channel.send(f"{tag_str}")