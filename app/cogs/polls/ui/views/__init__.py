from discord.ui import View, Button, Select
import discord
import traceback

from cogs.polls.ui.buttons import *
from .myorder_view import MyOrderView

class PersistentPollView(View):
    def __init__(self, pool_id: int, items: list, prices: list, status: str = 'Active'):
        super().__init__(timeout=None)

        if status == 'Ended':
            ended_btn = Button(
                label="投票已結束",
                style=discord.ButtonStyle.grey,
                disabled=True
            )
            self.add_item(ended_btn)
            return

        if status == 'Active':
            for item, price in zip(items, prices):
                self.add_item(ItemButton(pool_id, item, price))
        
        self.add_item(ResultButton(pool_id))
        self.add_item(CancelVoteButton(pool_id))
        self.add_item(AddItemButton(pool_id))
        self.add_item(MyVotesButton(pool_id))
        self.add_item(ManageButton(pool_id))


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