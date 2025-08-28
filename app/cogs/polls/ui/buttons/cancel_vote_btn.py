from discord.ui import Button, Select
import discord
import asyncio

from cogs.polls.utils import check_voting_permission
import sql_database
import cogs.polls.ui.views as views

class CancelVoteButton(Button):
    def __init__(self, poll_id: int):
        super().__init__(
            label="取消投票",
            custom_id=f"poll_{poll_id}_cancel_vote",
            style=discord.ButtonStyle.red
        )
        self.poll_id = poll_id

    async def callback(self, interaction: discord.Interaction):
        # 檢查投票權限
        if not check_voting_permission(interaction):
            await interaction.response.send_message(
                "❌ 權限不足：只有持有特定身份組的成員可以取消投票",
                ephemeral=True
            )
            return
        
        user = interaction.user
        user_id = user.id
        display_name = user.display_name

        user_votes = await sql_database.get_votes_by_poll_and_user(self.poll_id, user_id)
        if not user_votes:
            # 發送私有消息
            embed = discord.Embed(
                description=f"❌ **{display_name}** 沒有投票記錄可取消",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        options = []
        for i, vote in enumerate(user_votes):
            vote_id, item, price, need_single = vote
            options.append(discord.SelectOption(
                label=f"{item}" + (" (需要單品)" if need_single else ""),
                value=f"{i}_{item}",  # 使用索引和項目名作為值
                description=f"價格: {price}円"  # 使用專屬價格
            ))
        
        select = Select(
            placeholder="選擇要取消的投票項目",
            options=options,
            min_values=1,
            max_values=1  # 只能選一個
        )
        
        # 創建確定按鈕
        confirm_btn = Button(
            label="確定取消",
            style=discord.ButtonStyle.danger
        )

        # 創建取消按鈕
        cancel_btn = Button(
            label="取消操作",
            style=discord.ButtonStyle.secondary
        )

        view = views.TimeoutView(timeout=30)
        view.add_item(select)
        view.add_item(confirm_btn)
        view.add_item(cancel_btn)

        # 存儲選擇狀態
        selected_items = []

        async def select_callback(interaction: discord.Interaction):
            """處理選擇變化"""
            nonlocal selected_items
            selected_items = interaction.data["values"]
            await interaction.response.defer()
        
        async def confirm_callback(interaction: discord.Interaction):
            """處理確定按鈕點擊（私有操作後發送公開通知）"""
            nonlocal selected_items
            if not selected_items:
                await interaction.response.send_message("❌ 請先選擇要取消的項目", ephemeral=True)
                return
            
            # 只處理選中的第一個項目（單選）
            value = selected_items[0]
            # 分割索引和項目名
            index_str, _ = value.split("_", 1)
            idx = int(index_str)

            if idx < len(user_votes):
                vote_id = user_votes[idx][0]  # 獲取投票ID
                await sql_database.delete_vote(vote_id)  # 刪除投票記錄
            else:
                await interaction.response.send_message("❌ 無效的投票項目", ephemeral=True)
                return
        
            public_embed = discord.Embed(
                description=f"❌ **{display_name}** 已取消投票：",
                color=discord.Color.red()
            )
            public_embed.add_field(name="項目", value=user_votes[idx][1], inline=True)
            public_embed.add_field(name="價格", value=f"{user_votes[idx][2]}円", inline=True)  # 使用專屬價格
            
            await interaction.channel.send(embed=public_embed)
            
            # 刪除私有消息
            await interaction.response.edit_message(content="投票已取消", embed=None, view=None)
            await asyncio.sleep(2)
            await interaction.delete_original_response()
            view.stop()
        
        async def cancel_callback(interaction: discord.Interaction):
            """處理取消按鈕點擊（刪除私有消息）"""
            await interaction.response.edit_message(content="操作已取消", embed=None, view=None)
            await asyncio.sleep(2)
            await interaction.delete_original_response()
            view.stop()
        
        # 設置回調
        select.callback = select_callback
        confirm_btn.callback = confirm_callback
        cancel_btn.callback = cancel_callback
        
        # 發送下拉菜單（私有）- 簡化界面，只保留下拉清單和按鈕
        message = await interaction.response.send_message(view=view, ephemeral=True)
        view.message = await interaction.original_response()
