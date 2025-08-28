import discord
from discord.ui import Button
import asyncio

import sql_database
from cogs.polls.utils import check_voting_permission, is_special_item
import cogs.polls.ui.views as views


class ItemButton(Button):

    def __init__(self, poll_id: int, item: str, price: int):

        super().__init__(
            label=f"{item} ({price}円)",
            custom_id=f"poll_{poll_id}_item_{item}",
            style=discord.ButtonStyle.primary
        )

        self.poll_id = poll_id
        self.item = item
        self.price = price
        self.is_special = is_special_item(item)
    

    async def callback(self, interaction: discord.Interaction):
        if not check_voting_permission(interaction):
            await interaction.response.send_message(
                "❌ 權限不足：只有持有特定身份組的成員可以投票",
                ephemeral=True
            )
            return
        
        if self.is_special:
            # 特殊項目：顯示額外確認界面
            await self._show_special_confirmation(interaction)
        else:
            # 普通項目：直接顯示投票確認
            await self._show_normal_confirmation(interaction)
    
    async def _show_special_confirmation(self, interaction: discord.Interaction):
        """顯示特殊項目的額外確認界面"""
        embed = discord.Embed(
            title="額外確認",
            description=f"您選擇了 **{self.item}**\n如果沒有{self.item}，單品還需要嗎？",
            color=discord.Color.blue()
        )
        
        view = views.TimeoutView(timeout=30)
        need_btn = Button(label="需要", style=discord.ButtonStyle.green)
        not_need_btn = Button(label="不需要", style=discord.ButtonStyle.red)
        
        async def need_callback(new_interaction: discord.Interaction):
            # 記錄用戶選擇
            extra = {"need_single": True}
            # 顯示正常確認界面
            await interaction.delete_original_response()
            view.stop()
            await self._show_normal_confirmation(new_interaction, extra)
            
        
        async def not_need_callback(new_interaction: discord.Interaction):
            # 記錄用戶選擇
            extra = {"need_single": False}
            # 顯示正常確認界面
            await interaction.delete_original_response()
            view.stop()
            await self._show_normal_confirmation(new_interaction, extra)
            
        
        need_btn.callback = need_callback
        not_need_btn.callback = not_need_callback
        
        view.add_item(need_btn)
        view.add_item(not_need_btn)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

    async def _show_normal_confirmation(self, interaction: discord.Interaction, extra: dict = None):
        """顯示正常的投票確認界面"""
        # 創建確認界面（私有）
        embed = discord.Embed(
            title="確認投票",
            description=f"您確定要投票給 **{self.item}** 嗎？",
            color=discord.Color.blue()
        )
        embed.add_field(name="項目", value=self.item, inline=True)
        embed.add_field(name="價格", value=f"{self.price}円", inline=True)  # 使用專屬價格
        
        view = views.TimeoutView(timeout=30)
        confirm_btn = Button(label="確認", style=discord.ButtonStyle.green)
        cancel_btn = Button(label="取消", style=discord.ButtonStyle.red)


        async def confirm_callback(interaction: discord.Interaction):
            """處理確認投票"""
            user = interaction.user
            display_name = user.display_name
            
            # 記錄投票（存儲用戶ID、顯示名稱和項目）

            # sql_database.update_username(user.id, display_name)
            await sql_database.create_vote(user.id, self.poll_id, self.item, extra)
            
            # 發送公開投票通知
            public_embed = discord.Embed(
                color=discord.Color.green()
            )
            public_embed.add_field(name="項目", value=self.item, inline=True)
            public_embed.add_field(name="價格", value=f"{self.price}円", inline=True)  # 使用專屬價格
            public_embed.set_footer(text="點擊「取消投票」按鈕可移除投票")
            
            await interaction.channel.send(content=f"✅ **{user.mention}** 投票成功！", embed=public_embed)
            
            # 刪除私有確認消息
            await interaction.response.edit_message(content="投票已確認", embed=None, view=None)
            await asyncio.sleep(2)
            await interaction.delete_original_response()
            view.stop()
        
        async def cancel_callback(interaction: discord.Interaction):
            """取消投票（刪除私有消息）"""
            await interaction.response.edit_message(content="投票已取消", embed=None, view=None)
            await asyncio.sleep(2)
            await interaction.delete_original_response()
            view.stop()
        
        confirm_btn.callback = confirm_callback
        cancel_btn.callback = cancel_callback
        
        view.add_item(confirm_btn)
        view.add_item(cancel_btn)
        
        # 發送私有確認消息
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()