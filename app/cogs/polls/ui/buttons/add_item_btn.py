from discord.ui import Button
import discord

from cogs.polls.ui.modals import AddItemModal
from cogs.polls.utils import check_voting_permission
import sql_database
from cogs.polls import handler

class AddItemButton(Button):
    def __init__(self, poll_id: int):
        super().__init__(
            label="添加項目",
            custom_id=f"poll_{poll_id}_add_item",
            style=discord.ButtonStyle.secondary
        )
        self.poll_id = poll_id

    async def callback(self, interaction: discord.Interaction):
        # 檢查是否有權限添加項目
        if not check_voting_permission(interaction):
            await interaction.response.send_message(
                "❌ 權限不足：只有持有特定身份組的成員可以添加項目",
                ephemeral=True
            )
            return
        
        # 發送模態窗口獲取新項目信息
        modal = AddItemModal(title="添加新項目（批量）")
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        if not modal.new_items:
            return
        
        added_items = []
        errors = []
        
        poll_items = await sql_database.get_items_by_poll(self.poll_id)
        poll_items = list(map(lambda x: x[0], poll_items))  # 提取項目名稱
        current_count = len(poll_items)
        remaining_slots = 25 - current_count
        
        if remaining_slots <= 0:
            await interaction.followup.send("❌ 投票項目已達上限（25個）", ephemeral=False)
            return

        # 批量添加項目（最多填滿25個位置）
        for i, (item_name, price) in enumerate(modal.new_items):
            if i >= remaining_slots:
                errors.append(f"- 只能添加 {remaining_slots} 個項目（已達上限）")
                break
                
            if item_name in poll_items:
                errors.append(f"- 項目 '{item_name}' 已存在")
                continue
                
            added_items.append((item_name, price))
        
        if not added_items:
            error_msg = "\n".join(errors[:3])  # 最多顯示3個錯誤
            await interaction.followup.send(f"❌ 添加失敗:\n{error_msg}", ephemeral=False)
            return

        # 寫入數據庫
        await sql_database.add_items_to_poll(self.poll_id, added_items)
        # 重新載入投票消息
        await handler.update_poll_message(interaction.channel, self.poll_id)

        success_msg = "\n".join([f"• {item} - {price}円" for item, price in added_items])
        confirm_embed = discord.Embed(
            title=f"✅ 已添加 {len(added_items)} 個項目",
            description=success_msg,
            color=discord.Color.green()
        )

        if errors:
            error_msg = "\n".join(errors[:3])  # 最多顯示3個錯誤
            confirm_embed.add_field(
                name="⚠️ 部分項目添加失敗",
                value=error_msg,
                inline=False
            )
        
        await interaction.followup.send(embed=confirm_embed, ephemeral=False)