from discord.ui import Button
import discord

from cogs.polls import handler
from cogs.polls.utils import check_voting_permission, is_special_item

class ResultButton(Button):

    def __init__(self, poll_id: int):
        super().__init__(
            label="查看結果",
            custom_id=f"poll_{poll_id}_results",
            style=discord.ButtonStyle.green
        )
        self.poll_id = poll_id

    
    async def callback(self, interaction: discord.Interaction):
        """處理查看結果按鈕點擊 - 響應公開"""
        # 檢查投票權限
        if not check_voting_permission(interaction):
            await interaction.response.send_message(
                "❌ 權限不足：只有持有特定身份組的成員可以查看結果",
                ephemeral=True
            )
            return
        
        # 生成結果嵌入並發送
        try:
            embed = await handler.generate_results_embed(self.poll_id)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ 獲取結果失敗",
                description=str(e),
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed)


    