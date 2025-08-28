from discord.ui import Modal, TextInput
import re
import discord

import cogs.twitter.utils as utils

class CircleBoothModal(Modal):
    """添加新項目的模態窗口（支持多項目）"""
    def __init__(self, circle_data: utils.CircleForm, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.booth_input = TextInput(
            label="攤位位置",
            placeholder="（例：34ab）",
            style=discord.TextStyle.short,
            default=circle_data.booth,
            min_length=1,
            max_length=4
        )
        self.add_item(self.booth_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.booth = self.booth_input.value.strip()
        if not re.match(r'^[0-9][0-9](ab?|b)$', self.booth):
            await interaction.response.send_message(
                "❌ 無效的價格格式",
                ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        self.stop()



class CircleInfoModal(Modal):
    """添加新項目的模態窗口（支持多項目）"""
    def __init__(self, circle_data: utils.CircleForm, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.author_input = TextInput(
            label="畫師名稱",
            placeholder="請輸入畫師名稱",
            style=discord.TextStyle.short,
            default=circle_data.author_name,
            min_length=1,
            max_length=50
        )

        self.circle_input = TextInput(
            label="社團名稱",
            placeholder="請輸入社團名稱",
            style=discord.TextStyle.short,
            default=circle_data.circle_name,
            min_length=1,
            max_length=50
        )

        self.addition_input = TextInput(
            label="備註",
            placeholder="請輸入備註（如有）",
            style=discord.TextStyle.paragraph,
            required=False,
            default=circle_data.remarks,
            min_length=0,
            max_length=100
        )

        self.add_item(self.author_input)
        self.add_item(self.circle_input)
        self.add_item(self.addition_input)
        

    async def on_submit(self, interaction: discord.Interaction):
        self.author_name = self.author_input.value.strip()
        self.circle_name = self.circle_input.value.strip()
        self.addition = self.addition_input.value.strip()
        await interaction.response.defer(ephemeral=True)
        self.stop()