import discord
import asyncio
import traceback

from discord.ui import Button

from cogs.polls import utils
from cogs.polls.ui.views import TimeoutView
import sql_database

class EndAllPollCommand:

    def __init__(self, cog_poll):
        self.cog_poll = cog_poll
    
    async def on_execute(self, interaction: discord.Interaction):
        # 檢查用戶權限
        if not utils.check_endall_permission(interaction):
            await interaction.response.send_message("❌ 您沒有權限使用此命令", ephemeral=True)
            return

        # 確認操作
        active_polls = await sql_database.get_active_polls()
        confirm_embed = discord.Embed(
            title="⚠️ 確認終止所有投票",
            description=f"確定要終止所有 {len(active_polls)} 個活躍投票嗎？此操作無法復原！",
            color=discord.Color.orange()
        )
        confirm_embed.set_footer(text="此操作將在每個投票的原始頻道發布結果")
        
        confirm_view = TimeoutView(timeout=60)
        confirm_btn = Button(label="確認終止", style=discord.ButtonStyle.danger)
        cancel_btn = Button(label="取消", style=discord.ButtonStyle.secondary)
        
        
        async def confirm_callback(new_interaction: discord.Interaction):
            """處理確認終止操作"""
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
            
            for poll_id, _, channel_id, _, _ in active_polls:
                try: 
                    channel = self.cog_poll.bot.get_channel(channel_id)
                    if not channel:
                        failed_count += 1
                        continue
                    
                    # 創建模擬上下文
                    class FakeInteraction:
                        class Response(object):
                            pass

                        def __init__(self, channel):
                            self.response = self.Response()
                            self.response.send_message = channel.send
                            self.followup = channel
                            self.channel = channel
                            
                    fake_interaction = FakeInteraction(channel)
                    
                    # 終止投票
                    await self.cog_poll.commands['end_poll']._end_poll(fake_interaction, poll_id)
                    success_count += 1
                    
                    # 避免速率限制
                    await asyncio.sleep(0.8)
                    
                except Exception as e:
                    failed_count += 1
                    traceback.print_exc()
            
            # 發送總結報告
            result_embed = discord.Embed(
                title="✅ 所有投票已終止",
                description=f"成功終止: {success_count} 個\n失敗: {failed_count} 個",
                color=discord.Color.green()
            )
            await new_interaction.followup.send(embed=result_embed)
            
            # 刪除確認消息
            await interaction.delete_original_response()
            confirm_view.stop()
        

        async def cancel_callback(new_interaction: discord.Interaction):
            """取消操作"""
            # 檢查是否為命令發起者
            if new_interaction.user.id != interaction.user.id:
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