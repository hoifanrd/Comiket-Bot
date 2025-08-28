import discord
import asyncio
import traceback

from discord.ui import Button

import sql_database
from cogs.polls import handler, utils
from cogs.polls.ui.views import TimeoutView

class ResumeAllPollCommand:

    def __init__(self, cog_poll):
        self.cog_poll = cog_poll
    
    async def on_execute(self, interaction: discord.Interaction):
        if not utils.check_endall_permission(interaction):
            await interaction.response.send_message("❌ 您沒有權限使用此命令", ephemeral=True)
            return

        # 確認操作
        paused_polls = await sql_database.get_paused_polls()
        confirm_embed = discord.Embed(
            title="🔄 確認恢復所有投票",
            description=f"確定要恢復所有 {len(paused_polls)} 個活躍投票嗎？",
            color=discord.Color.blue()
        )

        confirm_view = TimeoutView(timeout=60)
        confirm_btn = Button(label="確認恢復", style=discord.ButtonStyle.primary)
        cancel_btn = Button(label="取消", style=discord.ButtonStyle.secondary)
        
        
        async def confirm_callback(new_interaction: discord.Interaction):
            """處理確認恢復操作"""
            # 檢查是否為命令發起者
            if interaction.user.id != new_interaction.user.id:
                await new_interaction.response.send_message("❌ 只有發起命令的用戶可以確認此操作", ephemeral=True)
                return
                
            await new_interaction.response.defer()
            
            # 禁用按鈕防止重複點擊
            confirm_btn.disabled = True
            cancel_btn.disabled = True
            await interaction.edit_original_response(view=confirm_view)
            
            # 終止所有投票
            success_count = 0
            failed_count = 0
            
            for poll_id, _, channel_id, _, _ in paused_polls:
                try: 
                    channel = self.cog_poll.bot.get_channel(channel_id)
                    if not channel:
                        failed_count += 1
                        continue
                    
                    await sql_database.update_poll_status(poll_id, "Active")
        
                    # 更新投票消息
                    original_channel_id = await sql_database.get_poll_channel_id(poll_id)
                    original_channel = self.cog_poll.bot.get_channel(original_channel_id)

                    res = await handler.update_poll_message(original_channel, poll_id)
                    if not res:
                        failed_count += 1
                        continue

                    success_count += 1
                    
                    # 避免速率限制
                    await asyncio.sleep(0.8)
                    
                except Exception as e:
                    failed_count += 1
                    traceback.print_exc()
            
            # 發送總結報告
            result_embed = discord.Embed(
                title="✅ 所有投票已恢復",
                description=f"成功恢復: {success_count} 個\n失敗: {failed_count} 個",
                color=discord.Color.green()
            )
            await new_interaction.followup.send(embed=result_embed)
            
            # 刪除確認消息
            await interaction.delete_original_response()
            confirm_view.stop()
        

        async def cancel_callback(new_interaction: discord.Interaction):
            """取消操作"""
            # 檢查是否為命令發起者
            if interaction.user.id != new_interaction.user.id:
                await new_interaction.response.send_message("❌ 只有發起命令的用戶可以取消此操作", ephemeral=True)
                return
                
            await interaction.delete_original_response()
            await new_interaction.response.send_message("操作已取消")
            await asyncio.sleep(2)
            await new_interaction.delete_original_response()
            confirm_view.stop()

        confirm_btn.callback = confirm_callback
        cancel_btn.callback = cancel_callback

        confirm_view.add_item(confirm_btn)
        confirm_view.add_item(cancel_btn)

        await interaction.response.send_message(embed=confirm_embed, view=confirm_view)
        confirm_view.message = await interaction.original_response()