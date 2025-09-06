
import discord
import traceback
from discord.ui import View

from .poll_view import PersistentPollView
from .myorder_view import PersistentMyOrderView


class TimeoutView(View):
    def __init__(self, timeout: int):
        super().__init__(timeout=timeout)
        self.message = None
        
    async def on_timeout(self):
        if self.message:
            await self.message.edit(content="❌ 操作已超時，請重新操作", view=None, embed=None)


class ManagementTimeoutView(View):
    """管理項目操作的自定義視圖，處理超時"""
    def __init__(self, timeout: int):
        super().__init__(timeout=timeout)  # 5分鐘超時
        self.message = None  # 儲存消息物件用於超時編輯
            
    async def on_timeout(self):
        """超時處理"""
        if self.message:
            await self.message.edit(content="❌ 操作已超時，請重新操作", view=None, embed=None)
                
    async def on_error(self, interaction: discord.Interaction, error: Exception, item):
        """錯誤處理"""
        await interaction.response.send_message(
            f"❌ 發生錯誤: {str(error)}",
            ephemeral=True
        )
        traceback.print_exc()