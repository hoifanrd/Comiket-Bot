import discord
from discord.ui import Button, View, TextInput, Select, Modal
import re

class AddItemModal(Modal):
    """添加新項目的模態窗口（支持多項目）"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 修復：添加 self.items_input = 並正確縮進
        self.items_input = TextInput(
            label="添加多個項目（每行一個）",
            placeholder="格式：項目名稱 價格\n範例：拉麵 300\n壽司 500",
            style=discord.TextStyle.paragraph,
            min_length=1,
            max_length=500
        )
        self.add_item(self.items_input)
        
        # 存儲結果的變數
        self.new_items = []  # 格式: [(item_name, price), ...]

    async def on_submit(self, interaction: discord.Interaction):
        lines = self.items_input.value.split('\n')
        valid_items = []
        errors = []
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
                
            # 使用正則表達式分離項目名稱和價格
            match = re.match(r"(.+?)\s+(\d+)$", line)
            if not match:
                errors.append(f"- 第{i}行: 格式錯誤（需要項目名稱和價格）")
                continue
                
            item_name = match.group(1).strip()
            try:
                price = int(match.group(2))
                if price < 0:
                    errors.append(f"- 第{i}行: 價格不能是負數")
                    continue
                    
                valid_items.append((item_name, price))
            except ValueError:
                errors.append(f"- 第{i}行: 無效的價格 '{match.group(2)}'")
        
        if errors:
            error_msg = "\n".join(errors[:5])  # 最多顯示5個錯誤
            if len(errors) > 5:
                error_msg += f"\n...（共{len(errors)}個錯誤）"
            await interaction.response.send_message(
                f"❌ 添加失敗:\n{error_msg}",
                ephemeral=False
            )
        else:
            self.new_items = valid_items
            await interaction.response.defer()
        
        self.stop()



class CreatePollModal(Modal):
    """創建投票的模態窗口"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.title_input = TextInput(
            label="投票標題",
            placeholder="輸入投票標題（例如：畫師名稱）",
            min_length=1,
            max_length=100
        )
        self.add_item(self.title_input)
        
        self.items_input = TextInput(
            label="投票項目（每行一個）",
            placeholder="格式：項目名稱 價格\n範例：新刊SET 2000\n新刊單品 500\n立牌 2000",
            style=discord.TextStyle.paragraph,
            min_length=1,
            max_length=1000
        )
        self.add_item(self.items_input)
        
        # 存儲結果
        self.title = ""
        self.items = ""

    async def on_submit(self, interaction: discord.Interaction):
        self.title = self.title_input.value.strip()
        self.items = self.items_input.value.strip()
        await interaction.response.defer()




class EditItemModal(Modal):
    """編輯項目的模態窗口"""
    def __init__(self, title, item, price, *args, **kwargs):
        super().__init__(title=title, *args, **kwargs)
        
        self.item = item
        self.price = price
        
        self.name_input = TextInput(
            label="新項目名稱",
            placeholder="留空表示不修改",
            default=item,
            required=False,
            max_length=100
        )
        self.add_item(self.name_input)
        
        self.price_input = TextInput(
            label="新價格",
            placeholder="留空表示不修改",
            default=str(price),
            required=False,
            max_length=10
        )
        self.add_item(self.price_input)
        
        # 存儲結果
        self.new_name = ""
        self.new_price = None

    async def on_submit(self, interaction: discord.Interaction):
        self.new_name = self.name_input.value.strip()
        
        try:
            if self.price_input.value.strip():
                self.new_price = int(self.price_input.value.strip())
                if self.new_price < 0:
                    await interaction.response.send_message(
                        "❌ 價格不能是負數",
                        ephemeral=True
                    )
                    return
        except ValueError:
            await interaction.response.send_message(
                "❌ 無效的價格格式",
                ephemeral=True
            )
            return
            
        await interaction.response.defer()