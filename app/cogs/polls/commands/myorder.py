import discord
from cogs.polls.ui.views import PersistentMyOrderView

class MyOrderCommand:

    def __init__(self, cog_poll):
        self.cog_poll = cog_poll
    
    async def on_execute(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            # 嘗試私訊用戶
            await interaction.user.send("🔄 正在為您生成品項列表，請稍候...")
        except discord.Forbidden:
            # 如果無法私訊，在頻道中提示
            await interaction.followup.send("❌ 無法向您發送私訊，請檢查您的隱私設定", ephemeral=True)
            return

        view = await PersistentMyOrderView(user_id=interaction.user.id)
        await interaction.user.send(view=view, embed=view._get_embed())


        await interaction.followup.send(
            "✅ 記錄已發送至私訊",
            ephemeral=True
        )
