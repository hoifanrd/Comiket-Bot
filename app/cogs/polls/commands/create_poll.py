import discord
import re

from discord.ui import Button, View
from cogs.polls.ui.modals import CreatePollModal
from cogs.polls.ui.views import PersistentPollView

import sql_database

from decimal import *

class CreatePollCommand:

    def __init__(self, cog_poll):
        self.cog_poll = cog_poll

    async def on_execute(self, interaction: discord.Interaction):
        # Check if already exists poll in current channel (or thread)
        if await sql_database.get_not_ended_poll_id_in_channel(interaction.channel.id):
            await interaction.response.send_message(
                "❌ 此頻道已經存在投票",
                ephemeral=True
            )
            return

        # 創建臨時視圖來獲取交互
        view = View(timeout=60)
        button = Button(label="創建投票", style=discord.ButtonStyle.primary)
        view.add_item(button)
        
        await interaction.response.send_message("點擊下方按鈕創建新投票", view=view, ephemeral=True)
        
        async def button_callback(new_interaction: discord.Interaction):
            """按鈕回調，發送模態窗口"""
            modal = CreatePollModal(title="創建新投票")
            await new_interaction.response.send_modal(modal)
            await modal.wait()
            
            if not modal.title or not modal.items:
                await new_interaction.followup.send("❌ 投票創建已取消", ephemeral=True)
                return
            
            # 解析項目和價格
            items = []
            prices = []
            lines = modal.items.split('\n')
            errors = []  # 初始化錯誤列表
            
            for i, line in enumerate(lines, 1):
                line = line.strip()
                if not line:
                    continue
                    
                # 使用正則表達式分離項目名稱和價格
                match = re.match(r"(.+?)\s+(\d+)$", line)
                if not match:
                    errors.append(f"第{i}行: 格式錯誤 (範例: '新刊SET 2000')")
                    continue
                    
                item = match.group(1).strip()
                try:
                    price = int(match.group(2))
                    if price < 0:
                        errors.append(f"第{i}行: 價格必須是正整數")
                        continue
                except ValueError:
                    errors.append(f"第{i}行: 無效的價格 '{match.group(2)}'")
                    continue
                    
                items.append(item)    # 儲存項目名稱
                prices.append(price)  # 儲存價格

            # 檢查項目數量
            if not items:
                await new_interaction.followup.send("❌ 未提供有效的投票項目", ephemeral=True)
                return
                
            if len(items) > 25:
                errors.append("❌ 投票項目最多只能有25個")
                
            # 如果有錯誤，發送錯誤信息
            if errors:
                error_msg = "\n".join(errors[:5])  # 最多顯示5個錯誤
                if len(errors) > 5:
                    error_msg += f"\n...（共{len(errors)}個錯誤）"
                await new_interaction.followup.send(f"❌ 創建投票失敗:\n{error_msg}", ephemeral=True)
                return

            # 創建投票訊息
            # 使用複製的上下文對象
            await self._create_poll_message(new_interaction, modal.title, items, prices)
            await interaction.delete_original_response()
            view.stop()
        
        button.callback = button_callback
    

    async def _create_poll_message(self, interaction: discord.Interaction, title: str, items: list, prices: list):
        """創建投票消息（內部函數）"""
        
        # 創建美觀的投票訊息
        embed = discord.Embed(
            title=f"📊 {title}",
            description="點擊下方按鈕進行投票",
            color=discord.Color.blue()
        )
        
        # 添加投票項目
        for i, (item, price) in enumerate(zip(items, prices)):
            index = i + 1
            if index <= 10:
                prefix = f"{index}."
            else:
                letter = chr(65 + index - 11)  # A=65, B=66, 依此類推
                prefix = f"{letter}."
            
            embed.add_field(
                name=f"{prefix} {item}",
                value=f"```{price}円```",  # 使用專屬價格
                inline=False
            )

        message = await interaction.channel.send(embed=embed)
        
        poll_id = await sql_database.create_poll(title, interaction.channel.id, message.id, interaction.user.id, items, prices)

        view = PersistentPollView(poll_id, items, prices)
        
        await message.edit(view=view)
        
        
        # assert lastrowid == poll_id

        # 發送ID訊息（公開）
        id_embed = discord.Embed(
            description=f"投票已創建！ID: `{poll_id}`",
            color=discord.Color.green()
        )
        await interaction.channel.send(embed=id_embed)

        await message.pin()