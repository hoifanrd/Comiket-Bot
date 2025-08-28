from discord.ui import Button, Select
import discord

import cogs.polls.ui.views as views

from cogs.polls.ui.modals import EditItemModal
import sql_database
from cogs.polls import utils
from cogs.polls import handler

class ManageButton(Button):
    def __init__(self, poll_id: int):
        super().__init__(
            label="管理項目",
            custom_id=f"poll_{poll_id}_manage",
            style=discord.ButtonStyle.secondary
        )
        self.poll_id = poll_id

    async def callback(self, interaction: discord.Interaction):
        
        # creator_id = await sql_database.get_poll_creator(self.poll_id)
        
        # # 檢查是否有權限管理項目
        # is_creator = interaction.user.id == creator_id
        # is_special = utils.check_admin_permission(interaction)
        
        # if not (is_creator or is_special):
        #     # 更新錯誤訊息，包含後勤人員信息
        #     error_msg = "❌ 只有投票創建者或後勤人員可以管理項目"
        #     await interaction.response.send_message(
        #         error_msg,
        #         ephemeral=True
        #     )
        #     return

        item_list = await sql_database.get_items_by_poll(self.poll_id)
        if not item_list:
            await interaction.response.send_message(
                "❌ 此投票沒有可管理的項目",
                ephemeral=True
            )
            return
    
        # 創建下拉菜單選項
        options = []
        for i, (item, price) in enumerate(item_list):
            options.append(discord.SelectOption(
                label=f"{item} ({price}円)",  # 使用專屬價格
                value=str(i),
                description=f"點擊管理此項目"
            ))
        
        # 創建下拉菜單
        select = Select(
            placeholder="選擇要管理的項目",
            options=options,
            min_values=1,
            max_values=1
        )
        
        # 創建操作按鈕
        edit_btn = Button(
            label="編輯項目",
            style=discord.ButtonStyle.primary
        )
        
        delete_btn = Button(
            label="刪除項目",
            style=discord.ButtonStyle.danger
        )
        
        cancel_btn = Button(
            label="取消",
            style=discord.ButtonStyle.secondary
        )

        # 創建自定義視圖
        view = views.ManagementTimeoutView(timeout=300)
        view.add_item(select)
        view.add_item(edit_btn)
        view.add_item(delete_btn)
        view.add_item(cancel_btn)
        
        # 存儲選擇狀態
        selected_index = None
        
        async def select_callback(interaction: discord.Interaction):
            """處理選擇變化"""
            nonlocal selected_index
            selected_index = int(interaction.data["values"][0])
            await interaction.response.defer()
        
        async def edit_callback(interaction: discord.Interaction):
            """處理編輯按鈕點擊"""
            nonlocal selected_index
            if selected_index is None:
                await interaction.response.send_message("❌ 請先選擇一個項目", ephemeral=True)
                return
                
            # 獲取當前項目信息
            edit_item, current_price = item_list[selected_index]
            
            # 發送編輯模態窗口
            modal = EditItemModal(title="編輯項目", item=edit_item, price=current_price)
            await interaction.response.send_modal(modal)
            await modal.wait()
            
            if modal.new_name or modal.new_price is not None:
                # 更新項目信息
                new_name = modal.new_name if modal.new_name else edit_item
                new_price = modal.new_price if modal.new_price is not None else current_price
                
                # 檢查名稱是否重複
                item_names = [item[0] for item in item_list]  # 獲取所有項目名稱
                if new_name != edit_item and new_name in item_names:
                    await interaction.followup.send(
                        f"❌ 項目名稱 '{new_name}' 已存在",
                        ephemeral=True
                    )
                    return

                # 更新數據庫
                await sql_database.update_poll_item(self.poll_id, edit_item, new_name, new_price)
                # 重新載入投票消息
                await handler.update_poll_message(interaction.channel, self.poll_id)

                await interaction.followup.send(
                    f"✅ 項目已更新: `{edit_item}` → `{new_name} ({new_price}円)`",
                    ephemeral=False
                )
            
        async def delete_callback(interaction: discord.Interaction):
            """處理刪除按鈕點擊"""
            nonlocal selected_index
            if selected_index is None:
                await interaction.response.send_message("❌ 請先選擇一個項目", ephemeral=True)
                return
                
            delete_item, price = item_list[selected_index]
            
            # 確認刪除
            confirm_embed = discord.Embed(
                title="⚠️ 確認刪除項目",
                description=f"確定要刪除 **{delete_item}** 嗎？此操作無法復原！",
                color=discord.Color.orange()
            )
            confirm_embed.add_field(name="項目", value=delete_item, inline=True)
            confirm_embed.add_field(name="價格", value=f"{price}円", inline=True)
            
            # 使用自定義視圖防止超時
            confirm_view = views.TimeoutView(timeout=120)
            confirm_btn = Button(label="確認刪除", style=discord.ButtonStyle.danger)
            cancel_btn = Button(label="取消", style=discord.ButtonStyle.secondary)
            
            async def confirm_delete(interaction: discord.Interaction):
                # 驗證投票是否仍然有效
                if await sql_database.get_poll_status(self.poll_id) == 'Ended':
                    await interaction.response.edit_message(
                        content="❌ 投票已結束",
                        embed=None,
                        view=None
                    )
                    return
                
                # 刪除項目
                await sql_database.delete_item_from_poll(self.poll_id, delete_item)
                # 重新載入投票消息
                await handler.update_poll_message(interaction.channel, self.poll_id)

                # 發送確認消息
                await interaction.response.edit_message(
                    content=f"✅ 項目 `{delete_item}` 已刪除",
                    embed=None,
                    view=None
                )
            
            async def cancel_delete(interaction: discord.Interaction):
                await interaction.response.edit_message(
                    content="操作已取消",
                    embed=None,
                    view=None
                )
            
            confirm_btn.callback = confirm_delete
            cancel_btn.callback = cancel_delete
            
            confirm_view.add_item(confirm_btn)
            confirm_view.add_item(cancel_btn)
            
            await interaction.response.send_message(embed=confirm_embed, view=confirm_view, ephemeral=True)
            confirm_view.message = await interaction.original_response()

        async def cancel_callback(interaction: discord.Interaction):
            """取消管理操作"""
            await interaction.response.edit_message(
                content="管理操作已取消",
                view=None
            )

        # 設置回調
        select.callback = select_callback
        edit_btn.callback = edit_callback
        delete_btn.callback = delete_callback
        cancel_btn.callback = cancel_callback
        
        # 發送管理界面
        await interaction.response.send_message(
            "請選擇要管理的項目:",
            view=view,
            ephemeral=True
        )
        # 記錄消息以便超時處理
        view.message = await interaction.original_response()