import discord
import asyncio
import re
import json
import datetime
import pathlib
import os
import traceback
import functools
from discord.ui import Button, View, TextInput, Select, Modal
from redbot.core import commands, Config
from collections import defaultdict

class PollCog(commands.Cog):
    """提供無打字投票功能的 Cog，支援數據保存和項目管理"""

    def __init__(self, bot):
        self.bot = bot
        # 初始化配置
        self.config = Config.get_conf(self, identifier=1234567890)
        default_global = {
            "polls": {},
            "active_polls": {}
        }
        self.config.register_global(**default_global)
        
        # 新增：投票權限身份組ID
        self.VOTER_ROLE_IDS = [
            1387804452471308472,  # 第一個身份組ID
            1387804502429667369,   # 第二個身份組ID
            1402642906690359428,    #TestID_1
            1402642939657719808,     #TestID_2
            1402643492857184337      #後勤人員
        ]
        
        # 初始化記憶體數據（將從配置加載）
        self.poll_items = {}  # {message_id: [項目列表]}
        self.votes = defaultdict(list)  # {message_id: [(用戶ID, 用戶名, 項目)]}  # 修改為存儲用戶ID
        self.user_votes = defaultdict(lambda: defaultdict(list))  # {message_id: {user_id: [項目]}}
        self.poll_prices = {}  # {message_id: {項目: 價格}}  # 修改為基於投票ID的字典
        self.poll_titles = {}  # {message_id: 標題}
        self.active_polls = {}  # {message_id: 訊息物件}
        self.poll_views = {}  # {message_id: 視圖物件}
        self.poll_creators = {}  # {message_id: 作者ID}
        self.original_to_new = {}  # {原始ID: 新ID} 映射表
        self.poll_channels = {}  # {message_id: 頻道ID}
        
        # 特定身份組ID（@後勤人員）
        self.SPECIAL_ROLE_ID = 1402643492857184337  #後勤人員
        
        # 特定用戶ID（有權限使用!endall）
        self.ENDALL_ALLOWED_USERS = [
            494524905367273472,
            439713481327902723,
            567303642793771018,
            340073174882582528,
            418706767485337620  #LEN, kiro, 右田, カナデ, 遊子
        ]
        
        # 特殊項目列表（需要額外確認）
        self.SPECIAL_ITEMS = ["新刊SET", "新刊set", "新刊Set", "新刊SET-1", "新刊SET-2", "新刊SET-3"]  # 特殊項目列表（不區分大小寫）
        self.special_item_responses = {}  # {message_id: {user_id: {item: [{"need_single": bool}]}}  # 修改為存儲回應列表
        
        # 設置備份目錄（與cog文件同級的money_data文件夾）
        self.backup_dir = pathlib.Path(__file__).parent / "money_data"
        os.makedirs(self.backup_dir, exist_ok=True)  # 確保目錄存在
        
        # 設置訂單列表目錄
        self.order_dir = pathlib.Path(__file__).parent / "order_list"
        os.makedirs(self.order_dir, exist_ok=True)  # 確保目錄存在
        
        # 加載保存的數據
        self.load_task = self.bot.loop.create_task(self.load_poll_data())

    async def _check_voting_permission(self, interaction: discord.Interaction) -> bool:
        """檢查用戶是否有投票權限"""
        # 檢查是否為服務器成員
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return False
        
        # 檢查用戶是否擁有任一指定身份組
        user_roles = interaction.user.roles
        voter_roles = [interaction.guild.get_role(rid) for rid in self.VOTER_ROLE_IDS]
        voter_roles = [role for role in voter_roles if role is not None]
        
        return any(role in user_roles for role in voter_roles)

    async def load_poll_data(self):
        """從配置加載投票數據"""
        data = await self.config.polls()
        active_polls = await self.config.active_polls()
        
        # 加載投票數據
        for message_id, poll_data in data.items():
            message_id = int(message_id)
            self.poll_items[message_id] = poll_data.get("items", [])
            
            # 兼容舊數據格式
            old_votes = poll_data.get("votes", [])
            self.votes[message_id] = []
            for vote in old_votes:
                if len(vote) == 3:  # 新格式 (user_id, display_name, item)
                    self.votes[message_id].append(vote)
                elif len(vote) == 2:  # 舊格式 (display_name, item)
                    # 轉換為新格式，user_id設為0（無法關聯特殊回應）
                    self.votes[message_id].append((0, vote[0], vote[1]))
            
            self.user_votes[message_id] = defaultdict(list, poll_data.get("user_votes", {}))
            self.poll_prices[message_id] = poll_data.get("prices", {})  # 修改為基於投票ID的字典
            self.poll_titles[message_id] = poll_data.get("title", "")
            self.poll_creators[message_id] = poll_data.get("creator_id", 0)
            self.poll_channels[message_id] = poll_data.get("channel_id", 0)  # 加載頻道ID
            
            # 加載特殊項目回應 (兼容舊格式)
            special_responses = poll_data.get("special_responses", {})
            self.special_item_responses[message_id] = {}
            
            for user_id_str, items in special_responses.items():
                user_id = int(user_id_str)
                self.special_item_responses[message_id][user_id] = {}
                
                for item, response in items.items():
                    # 兼容舊格式：如果是字典則轉換為列表
                    if isinstance(response, dict):
                        self.special_item_responses[message_id][user_id][item] = [response]
                    # 新格式：直接存儲列表
                    elif isinstance(response, list):
                        self.special_item_responses[message_id][user_id][item] = response
                    # 其他格式視為錯誤
                    else:
                        print(f"警告：投票 {message_id} 的特殊回應格式錯誤，將初始化為空列表")
                        self.special_item_responses[message_id][user_id][item] = []
            
        # 加載活動投票
        for message_id in active_polls:
            message_id = int(message_id)
            self.active_polls[message_id] = None  # 將在需要時重新獲取消息

    async def save_poll_data(self, message_id: int, is_active: bool = True):
        """保存指定投票的數據"""
        message_id_str = str(message_id)
        poll_data = {
            "items": self.poll_items.get(message_id, []),
            "votes": self.votes.get(message_id, []),
            "user_votes": dict(self.user_votes.get(message_id, defaultdict(list))),
            "prices": self.poll_prices.get(message_id, {}),  # 修改為基於投票ID的字典
            "title": self.poll_titles.get(message_id, ""),
            "creator_id": self.poll_creators.get(message_id, 0),
            "channel_id": self.poll_channels.get(message_id, 0),  # 保存頻道ID
            "special_responses": self.special_item_responses.get(message_id, {})  # 保存特殊項目回應
        }
        
        # 更新全局配置
        async with self.config.polls() as polls:
            polls[message_id_str] = poll_data
            
        # 更新活動投票列表
        async with self.config.active_polls() as active_polls:
            if is_active:
                active_polls[message_id_str] = True
            elif message_id_str in active_polls:
                del active_polls[message_id_str]

    @commands.command(aliases=["cp"])
    async def create_poll(self, ctx):
        """創建美觀的投票（彈出視窗輸入）"""
        # 創建臨時視圖來獲取交互
        view = View(timeout=60)
        button = Button(label="創建投票", style=discord.ButtonStyle.primary)
        view.add_item(button)
        
        msg = await ctx.send("點擊下方按鈕創建新投票", view=view)
        
        async def button_callback(interaction: discord.Interaction):
            """按鈕回調，發送模態窗口"""
            modal = CreatePollModal(title="創建新投票")
            await interaction.response.send_modal(modal)
            await modal.wait()
            
            if not modal.title or not modal.items:
                await interaction.followup.send("❌ 投票創建已取消", ephemeral=True)
                return
            
            # 解析項目和價格
            items = []
            prices_dict = {}  # 專屬於此投票的價格字典
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
                    
                items.append(item)
                prices_dict[item] = price  # 存入專屬字典

            # 檢查項目數量
            if not items:
                await interaction.followup.send("❌ 未提供有效的投票項目", ephemeral=True)
                return
                
            if len(items) > 25:
                errors.append("❌ 投票項目最多只能有25個")
                
            # 如果有錯誤，發送錯誤信息
            if errors:
                error_msg = "\n".join(errors[:5])  # 最多顯示5個錯誤
                if len(errors) > 5:
                    error_msg += f"\n...（共{len(errors)}個錯誤）"
                await interaction.followup.send(f"❌ 創建投票失敗:\n{error_msg}", ephemeral=True)
                return

            # 創建投票訊息
            # 使用複製的上下文對象
            ctx_copy = await self.bot.get_context(interaction.message)
            ctx_copy.author = interaction.user
            await self._create_poll_message(ctx_copy, modal.title, items, prices_dict)
            await msg.delete()
        
        button.callback = button_callback

    async def _create_poll_message(self, ctx, title: str, items: list, prices_dict: dict):
        """創建投票消息（內部函數）"""
        # 創建美觀的投票訊息
        embed = discord.Embed(
            title=f"📊 {title}",
            description="點擊下方按鈕進行投票",
            color=discord.Color.blue()
        )
        
        # 添加投票項目
        for i, item in enumerate(items):
            index = i + 1
            if index <= 10:
                prefix = f"{index}."
            else:
                letter = chr(65 + index - 11)  # A=65, B=66, 依此類推
                prefix = f"{letter}."
            
            embed.add_field(
                name=f"{prefix} {item}",
                value=f"```{prices_dict[item]}円```",  # 使用專屬價格
                inline=False
            )
        
        # 創建按鈕視圖
        view = View(timeout=None)
        
        # 為每個項目添加按鈕
        for item in items:
            btn = Button(
                label=f"{item} ({prices_dict[item]}円)",  # 使用專屬價格
                style=discord.ButtonStyle.primary,
                custom_id=f"vote_{item}_{ctx.message.id}"
            )
            # 使用閉包解決lambda綁定問題
            async def vote_callback(interaction, item=item):
                await self.vote_button(interaction, item)
            btn.callback = vote_callback
            view.add_item(btn)
        
        # 添加結果按鈕
        results_btn = Button(
            label="查看結果",
            style=discord.ButtonStyle.green,
            custom_id=f"results_{ctx.message.id}"
        )
        results_btn.callback = self.results_button
        view.add_item(results_btn)
        
        # 添加取消投票按鈕
        cancel_btn = Button(
            label="取消投票",
            style=discord.ButtonStyle.red,
            custom_id=f"cancel_{ctx.message.id}"
        )
        cancel_btn.callback = self.cancel_vote_button
        view.add_item(cancel_btn)
        
        # 添加新項目按鈕
        add_item_btn = Button(
            label="添加項目",
            style=discord.ButtonStyle.secondary,
            custom_id=f"add_item_{ctx.message.id}"
        )
        add_item_btn.callback = self.add_item_button
        view.add_item(add_item_btn)
        
        # 添加"我的投票"按鈕
        my_votes_btn = Button(
            label="我的投票",
            style=discord.ButtonStyle.secondary,
            custom_id=f"my_votes_{ctx.message.id}"
        )
        my_votes_btn.callback = self.my_votes_button
        view.add_item(my_votes_btn)
        
        # 添加"管理項目"按鈕（僅創建者可見）
        manage_btn = Button(
            label="管理項目",
            style=discord.ButtonStyle.secondary,
            custom_id=f"manage_{ctx.message.id}"
        )
        manage_btn.callback = self.manage_items_button
        view.add_item(manage_btn)
        
        message = await ctx.send(embed=embed, view=view)
        
        # 儲存投票信息
        self.poll_items[message.id] = items
        self.poll_titles[message.id] = title
        self.active_polls[message.id] = message
        self.poll_views[message.id] = view
        self.user_votes[message.id] = defaultdict(list)  # 初始化用戶投票記錄
        self.poll_creators[message.id] = ctx.author.id  # 儲存創建者ID
        self.poll_channels[message.id] = ctx.channel.id  # 儲存頻道ID
        self.poll_prices[message.id] = prices_dict  # 儲存專屬價格字典
        self.special_item_responses[message.id] = {}  # 初始化特殊項目回應
        
        # 保存到配置文件
        await self.save_poll_data(message.id)
        
        # 發送ID訊息（公開）
        id_embed = discord.Embed(
            description=f"投票已創建！ID: `{message.id}`",
            color=discord.Color.green()
        )
        await ctx.send(embed=id_embed)

    @commands.command(aliases=["end"])
    async def End(self, ctx, message_id: int):
        """終止指定ID的投票並顯示結果"""
        # 檢查投票是否存在（雙向檢查ID映射）
        actual_id = None
        
        # 先檢查是否是原始ID
        if message_id in self.poll_items:
            actual_id = message_id
        # 檢查是否是映射中的新ID
        elif message_id in self.original_to_new.values():
            # 反向查找：新ID → 原始ID
            for orig_id, new_id in self.original_to_new.items():
                if new_id == message_id:
                    actual_id = orig_id
                    break
        
        if actual_id is None:
            await ctx.send("❌ 找不到指定的投票，可能已經結束或ID錯誤")
            return
            
        # 檢查權限：創建者或特定身份組
        has_permission = False
        creator_id = self.poll_creators.get(actual_id)
        
        # 檢查是否是創建者
        if ctx.author.id == creator_id:
            has_permission = True
        
        # 檢查是否擁有特定身份組（@後勤人員）
        if not has_permission:
            special_role = ctx.guild.get_role(self.SPECIAL_ROLE_ID)
            if special_role and special_role in ctx.author.roles:
                has_permission = True
                
        if not has_permission:
            await ctx.send("❌ 權限不足：只有投票創建者或後勤人員可以結束此投票")
            return
            
        # 終止投票
        await self._end_poll(ctx, actual_id)
            
    async def _end_poll(self, ctx, message_id: int):
        """內部方法：終止指定投票（保留數據）"""
        # 獲取投票的原始頻道ID
        original_channel_id = self.poll_channels.get(message_id, 0)
        
        # 獲取投票原始頻道對象
        original_channel = self.bot.get_channel(original_channel_id) if original_channel_id else None
        
        # 檢查投票數據是否存在
        if message_id not in self.poll_items:
            await ctx.send(f"❌ 投票數據損壞：找不到投票數據，ID: {message_id}")
            return
            
        # 獲取投票結果
        results_embed = await self._generate_results_embed(message_id)
        
        # 確定結果發送位置
        if ctx.channel.id == original_channel_id:
            # 當前頻道就是原始頻道，直接發送
            await ctx.send(f"📊 **投票結束！最終結果：**", embed=results_embed)
        else:
            # 當前頻道不是原始頻道
            if original_channel:
                # 將結果發送到原始頻道
                await original_channel.send(f"📊 **投票結束！最終結果：**", embed=results_embed)
                # 在當前頻道發送提示
                await ctx.send(f"✅ 投票結果已發送到原始頻道：<#{original_channel_id}>")
            else:
                # 原始頻道不存在，在當前頻道發送結果
                await ctx.send(f"📊 **投票結束！最終結果：**", embed=results_embed)
        
        # 更新投票訊息為已結束狀態
        message = self.active_polls.get(message_id)
        if message and message.embeds:
            try:
                embed = message.embeds[0]
                embed.title = f"❌ 已結束 - {embed.title}"
                embed.description = "此投票已結束"
                embed.color = discord.Color.dark_grey()
                
                # 創建已結束視圖（移除所有互動按鈕）
                ended_view = View(timeout=None)
                ended_btn = Button(
                    label="投票已結束",
                    style=discord.ButtonStyle.grey,
                    disabled=True
                )
                ended_view.add_item(ended_btn)
                
                # 編輯原始投票訊息
                await message.edit(embed=embed, view=ended_view)
            except discord.NotFound:
                pass  # 訊息已被刪除，忽略
        
        # 從活動投票中移除（保留數據）
        if message_id in self.active_polls:
            del self.active_polls[message_id]
        
        # 保存到配置文件（標記為非活躍）
        await self.save_poll_data(message_id, is_active=False)
        
        # 發送確認訊息
        new_id_info = ""
        if message_id in self.original_to_new:
            new_id_info = f" | 新ID: `{self.original_to_new[message_id]}`"
            
        confirm_embed = discord.Embed(
            description=f"✅ 投票 原始ID: `{message_id}`{new_id_info} 已成功結束",
            color=discord.Color.green()
        )
        
        # 確認訊息始終在當前頻道發送
        await ctx.send(embed=confirm_embed)

    @commands.command(aliases=["endall"])
    async def end_all_polls(self, ctx):
        """終止所有活躍的投票（僅限特定用戶）"""
        # 檢查用戶權限
        if ctx.author.id not in self.ENDALL_ALLOWED_USERS:
            await ctx.send("❌ 您沒有權限使用此命令")
            return
            
        # 獲取所有活躍投票的ID
        active_ids = list(self.active_polls.keys())
        
        if not active_ids:
            await ctx.send("❌ 目前沒有活躍的投票")
            return
        
        # 先備份所有活躍投票
        backup_file = await self.backup_data_internal()
        if backup_file:
            backup_msg = f"✅ 已自動備份活躍投票數據: `{backup_file.name}`\n"
        else:
            backup_msg = "⚠️ 自動備份失敗，繼續終止操作\n"
            
        # 確認操作
        confirm_embed = discord.Embed(
            title="⚠️ 確認終止所有投票",
            description=f"{backup_msg}確定要終止所有 {len(active_ids)} 個活躍投票嗎？此操作無法復原！",
            color=discord.Color.orange()
        )
        confirm_embed.set_footer(text="此操作將在每個投票的原始頻道發布結果")
        
        # 創建確認視圖
        view = View(timeout=60)
        confirm_btn = Button(label="確認終止", style=discord.ButtonStyle.danger)
        cancel_btn = Button(label="取消", style=discord.ButtonStyle.secondary)
        view.add_item(confirm_btn)
        view.add_item(cancel_btn)
        
        async def confirm_callback(interaction: discord.Interaction):
            """處理確認終止操作"""
            # 檢查是否為命令發起者
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ 只有發起命令的用戶可以確認此操作", ephemeral=True)
                return
                
            await interaction.response.defer()
            
            # 禁用按鈕防止重複點擊
            confirm_btn.disabled = True
            cancel_btn.disabled = True
            await confirm_msg.edit(view=view)
            
            # 終止所有投票
            success_count = 0
            failed_count = 0
            
            for msg_id in active_ids[:]:  # 使用副本遍歷
                try:
                    # 獲取投票頻道
                    channel_id = self.poll_channels.get(msg_id)
                    if not channel_id:
                        failed_count += 1
                        continue
                        
                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        failed_count += 1
                        continue
                    
                    # 創建模擬上下文
                    class FakeContext:
                        def __init__(self, bot, channel, author):
                            self.bot = bot
                            self.channel = channel
                            self.author = author
                            self.send = channel.send
                            
                    fake_ctx = FakeContext(self.bot, channel, self.bot.user)
                    
                    # 終止投票
                    await self._end_poll(fake_ctx, msg_id)
                    success_count += 1
                    
                    # 避免速率限制
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    failed_count += 1
                    traceback.print_exc()
            
            # 發送總結報告
            result_embed = discord.Embed(
                title="✅ 所有投票已終止",
                description=f"成功終止: {success_count} 個\n失敗: {failed_count} 個",
                color=discord.Color.green()
            )
            await ctx.send(embed=result_embed)
            
            # 刪除確認消息
            await confirm_msg.delete()
        
        async def cancel_callback(interaction: discord.Interaction):
            """取消操作"""
            # 檢查是否為命令發起者
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ 只有發起命令的用戶可以取消此操作", ephemeral=True)
                return
                
            await interaction.response.defer()
            await confirm_msg.delete()
            await ctx.send("操作已取消")
        
        confirm_btn.callback = confirm_callback
        cancel_btn.callback = cancel_callback

        confirm_msg = await ctx.send(embed=confirm_embed, view=view)

    def _remove_poll_data(self, message_id: int):
        """移除指定投票的所有數據"""
        if message_id in self.poll_items:
            del self.poll_items[message_id]
        if message_id in self.votes:
            del self.votes[message_id]
        if message_id in self.user_votes:
            del self.user_votes[message_id]
        if message_id in self.poll_titles:
            del self.poll_titles[message_id]
        if message_id in self.active_polls:
            del self.active_polls[message_id]
        if message_id in self.poll_views:
            del self.poll_views[message_id]
        if message_id in self.poll_creators:
            del self.poll_creators[message_id]
        if message_id in self.poll_channels:
            del self.poll_channels[message_id]
        if message_id in self.poll_prices:  # 移除專屬價格字典
            del self.poll_prices[message_id]
        if message_id in self.special_item_responses:  # 移除特殊項目回應
            del self.special_item_responses[message_id]
        # 清理映射表
        for orig_id, new_id in list(self.original_to_new.items()):
            if new_id == message_id:
                del self.original_to_new[orig_id]

    @commands.command(aliases=["pause"])
    async def stop(self, ctx, message_id: int):
        """暫停指定投票（不再接受新投票）"""
        # 檢查投票是否存在
        if message_id not in self.active_polls:
            await ctx.send("❌ 找不到指定的活躍投票，可能已結束或ID錯誤")
            return
            
        # 檢查權限：創建者或特定身份組
        has_permission = False
        creator_id = self.poll_creators.get(message_id)
        
        # 檢查是否是創建者
        if ctx.author.id == creator_id:
            has_permission = True
        
        # 檢查是否擁有特定身份組（@後勤人員）
        if not has_permission:
            special_role = ctx.guild.get_role(self.SPECIAL_ROLE_ID)
            if special_role and special_role in ctx.author.roles:
                has_permission = True
                
        if not has_permission:
            await ctx.send("❌ 權限不足：只有投票創建者或後勤人員可以暫停此投票")
            return
        
        # 更新投票消息為暫停狀態
        message = self.active_polls.get(message_id)
        if message and message.embeds:
            try:
                embed = message.embeds[0]
                embed.title = f"⏸️ 已暫停 - {embed.title}"
                embed.color = discord.Color.orange()
                
                # 創建暫停視圖（禁用投票按鈕）
                paused_view = View(timeout=None)
                
                # 添加禁用的投票按鈕
                items = self.poll_items.get(message_id, [])
                prices_dict = self.poll_prices.get(message_id, {})
                for item in items:
                    btn = Button(
                        label=f"{item} ({prices_dict.get(item, 0)}円)",
                        style=discord.ButtonStyle.secondary,
                        disabled=True
                    )
                    paused_view.add_item(btn)
                
                # 添加其他功能按鈕（保持可用）
                results_btn = Button(
                    label="查看結果",
                    style=discord.ButtonStyle.green
                )
                results_btn.callback = self.results_button
                paused_view.add_item(results_btn)
                
                cancel_btn = Button(
                    label="取消投票",
                    style=discord.ButtonStyle.red
                )
                cancel_btn.callback = self.cancel_vote_button
                paused_view.add_item(cancel_btn)
                
                add_item_btn = Button(
                    label="添加項目",
                    style=discord.ButtonStyle.secondary
                )
                add_item_btn.callback = self.add_item_button
                paused_view.add_item(add_item_btn)
                
                my_votes_btn = Button(
                    label="我的投票",
                    style=discord.ButtonStyle.secondary
                )
                my_votes_btn.callback = self.my_votes_button
                paused_view.add_item(my_votes_btn)
                
                manage_btn = Button(
                    label="管理項目",
                    style=discord.ButtonStyle.secondary
                )
                manage_btn.callback = self.manage_items_button
                paused_view.add_item(manage_btn)
                
                # 編輯原始投票消息
                await message.edit(embed=embed, view=paused_view)
                
                # 發送確認消息
                await ctx.send(f"✅ 投票 `{message_id}` 已暫停")
            except discord.NotFound:
                await ctx.send("❌ 原始投票消息已被刪除")
        else:
            await ctx.send("❌ 無法找到原始投票消息")

    @commands.command(aliases=["resume"])
    async def open(self, ctx, message_id: int):
        """重新開啟指定投票（恢復投票功能）"""
        # 檢查投票是否存在
        if message_id not in self.poll_items:
            await ctx.send("❌ 找不到指定的投票，可能已結束或ID錯誤")
            return
            
        # 檢查是否在活躍投票中
        if message_id not in self.active_polls:
            await ctx.send("❌ 該投票未處於暫停狀態")
            return
            
        # 檢查權限：創建者或特定身份組
        has_permission = False
        creator_id = self.poll_creators.get(message_id)
        
        # 檢查是否是創建者
        if ctx.author.id == creator_id:
            has_permission = True
        
        # 檢查是否擁有特定身份組（@後勤人員）
        if not has_permission:
            special_role = ctx.guild.get_role(self.SPECIAL_ROLE_ID)
            if special_role and special_role in ctx.author.roles:
                has_permission = True
                
        if not has_permission:
            await ctx.send("❌ 權限不足：只有投票創建者或後勤人員可以開啟此投票")
            return
        
        # 恢復投票消息為活躍狀態
        message = self.active_polls.get(message_id)
        if message and message.embeds:
            try:
                embed = message.embeds[0]
                embed.title = embed.title.replace("⏸️ 已暫停 - ", "")
                embed.color = discord.Color.blue()
                
                # 創建原始視圖（啟用所有按鈕）
                items = self.poll_items.get(message_id, [])
                prices_dict = self.poll_prices.get(message_id, {})
                
                view = View(timeout=None)
                
                # 為每個項目添加按鈕
                for item in items:
                    btn = Button(
                        label=f"{item} ({prices_dict[item]}円)",
                        style=discord.ButtonStyle.primary,
                        custom_id=f"vote_{item}_{message_id}"
                    )
                    # 使用閉包解決綁定問題
                    async def vote_callback(interaction, item=item):
                        await self.vote_button(interaction, item)
                    btn.callback = vote_callback
                    view.add_item(btn)
                
                # 添加結果按鈕
                results_btn = Button(
                    label="查看結果",
                    style=discord.ButtonStyle.green,
                    custom_id=f"results_{message_id}"
                )
                results_btn.callback = self.results_button
                view.add_item(results_btn)
                
                # 添加取消投票按鈕
                cancel_btn = Button(
                    label="取消投票",
                    style=discord.ButtonStyle.red,
                    custom_id=f"cancel_{message_id}"
                )
                cancel_btn.callback = self.cancel_vote_button
                view.add_item(cancel_btn)
                
                # 添加新項目按鈕
                add_item_btn = Button(
                    label="添加項目",
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"add_item_{message_id}"
                )
                add_item_btn.callback = self.add_item_button
                view.add_item(add_item_btn)
                
                # 添加"我的投票"按鈕
                my_votes_btn = Button(
                    label="我的投票",
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"my_votes_{message_id}"
                )
                my_votes_btn.callback = self.my_votes_button
                view.add_item(my_votes_btn)
                
                # 添加"管理項目"按鈕（僅創建者可見）
                manage_btn = Button(
                    label="管理項目",
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"manage_{message_id}"
                )
                manage_btn.callback = self.manage_items_button
                view.add_item(manage_btn)
                
                # 編輯原始投票消息
                await message.edit(embed=embed, view=view)
                
                # 更新視圖引用
                self.poll_views[message_id] = view
                
                # 發送確認消息
                await ctx.send(f"✅ 投票 `{message_id}` 已重新開啟")
            except discord.NotFound:
                await ctx.send("❌ 原始投票消息已被刪除")
        else:
            await ctx.send("❌ 無法找到原始投票消息")

    async def vote_button(self, interaction: discord.Interaction, item: str):
        """處理投票按鈕點擊 - 先顯示確認界面（私有）"""
        # 檢查投票權限
        if not await self._check_voting_permission(interaction):
            await interaction.response.send_message(
                "❌ 權限不足：只有持有特定身份組的成員可以投票",
                ephemeral=True
            )
            return
        
        # 獲取並轉換消息ID
        poll_message_id = interaction.message.id
        if poll_message_id in self.original_to_new.values():
            # 如果是新ID，找到原始ID（如果存在）
            for orig_id, new_id in self.original_to_new.items():
                if new_id == poll_message_id:
                    poll_message_id = orig_id
                    break
        
        # 獲取專屬價格字典
        prices_dict = self.poll_prices.get(poll_message_id, {})
        if not prices_dict:
            await interaction.response.send_message("❌ 投票數據損壞，無法獲取價格", ephemeral=True)
            return
        
        # 檢查是否為特殊項目（不區分大小寫）
        is_special_item = any(special_item.lower() == item.lower() for special_item in self.SPECIAL_ITEMS)
        
        if is_special_item:
            # 特殊項目：顯示額外確認界面
            await self._show_special_confirmation(interaction, item, poll_message_id, prices_dict)
        else:
            # 普通項目：直接顯示投票確認
            await self._show_normal_confirmation(interaction, item, poll_message_id, prices_dict)

    async def _show_special_confirmation(self, interaction: discord.Interaction, item: str, poll_message_id: int, prices_dict: dict):
        """顯示特殊項目的額外確認界面"""
        embed = discord.Embed(
            title="額外確認",
            description=f"您選擇了 **{item}**\n如果沒有{item}，單品還需要嗎？",
            color=discord.Color.blue()
        )
        
        view = View(timeout=30)
        need_btn = Button(label="需要", style=discord.ButtonStyle.green)
        not_need_btn = Button(label="不需要", style=discord.ButtonStyle.red)
        
        async def need_callback(interaction: discord.Interaction):
            # 記錄用戶選擇
            extra = {"need_single": True}
            # 顯示正常確認界面
            await self._show_normal_confirmation(interaction, item, poll_message_id, prices_dict, extra)
        
        async def not_need_callback(interaction: discord.Interaction):
            # 記錄用戶選擇
            extra = {"need_single": False}
            # 顯示正常確認界面
            await self._show_normal_confirmation(interaction, item, poll_message_id, prices_dict, extra)
        
        need_btn.callback = need_callback
        not_need_btn.callback = not_need_callback
        
        view.add_item(need_btn)
        view.add_item(not_need_btn)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _show_normal_confirmation(self, interaction: discord.Interaction, item: str, poll_message_id: int, prices_dict: dict, extra: dict = None):
        """顯示正常的投票確認界面"""
        # 創建確認界面（私有）
        embed = discord.Embed(
            title="確認投票",
            description=f"您確定要投票給 **{item}** 嗎？",
            color=discord.Color.blue()
        )
        embed.add_field(name="項目", value=item, inline=True)
        embed.add_field(name="價格", value=f"{prices_dict.get(item, 0)}円", inline=True)  # 使用專屬價格
        
        # 創建自定義視圖以處理超時
        class TimeoutView(View):
            def __init__(self):
                super().__init__(timeout=30)
                self.message = None
                
            async def on_timeout(self):
                if self.message:
                    await self.message.edit(content="❌ 操作已超時，請重新操作", view=None, embed=None)
        
        view = TimeoutView()
        confirm_btn = Button(label="確認", style=discord.ButtonStyle.green)
        cancel_btn = Button(label="取消", style=discord.ButtonStyle.red)
        
        async def confirm_callback(interaction: discord.Interaction):
            """處理確認投票（私有確認後發送公開通知）"""
            user = interaction.user
            display_name = user.display_name
            
            # 記錄投票（存儲用戶ID、顯示名稱和項目）
            self.votes[poll_message_id].append((user.id, display_name, item))  # 存儲用戶ID
            self.user_votes[poll_message_id][user.id].append(item)
            
            # 保存特殊項目回應（如果有）
            if extra is not None:
                if poll_message_id not in self.special_item_responses:
                    self.special_item_responses[poll_message_id] = {}
                if user.id not in self.special_item_responses[poll_message_id]:
                    self.special_item_responses[poll_message_id][user.id] = {}
                if item not in self.special_item_responses[poll_message_id][user.id]:
                    # 初始化為空列表（如果沒有該項目的回應）
                    self.special_item_responses[poll_message_id][user.id][item] = []
                
                # 將回應添加到列表中（支持多次投票）
                self.special_item_responses[poll_message_id][user.id][item].append(extra)
            
            # 保存到配置文件
            await self.save_poll_data(poll_message_id)
            
            # 發送公開投票通知
            public_embed = discord.Embed(
                description=f"✅ **{display_name}** 投票成功！",
                color=discord.Color.green()
            )
            public_embed.add_field(name="項目", value=item, inline=True)
            public_embed.add_field(name="價格", value=f"{prices_dict[item]}円", inline=True)  # 使用專屬價格
            public_embed.set_footer(text="點擊「取消投票」按鈕可移除投票")
            
            await interaction.channel.send(embed=public_embed)
            
            # 刪除私有確認消息
            await interaction.response.edit_message(content="投票已確認", embed=None, view=None)
            await asyncio.sleep(2)
            await interaction.delete_original_response()
        
        async def cancel_callback(interaction: discord.Interaction):
            """取消投票（刪除私有消息）"""
            await interaction.response.edit_message(content="投票已取消", embed=None, view=None)
            await asyncio.sleep(2)
            await interaction.delete_original_response()
        
        confirm_btn.callback = confirm_callback
        cancel_btn.callback = cancel_callback
        
        view.add_item(confirm_btn)
        view.add_item(cancel_btn)
        
        # 發送私有確認消息
        message = await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

    async def cancel_vote_button(self, interaction: discord.Interaction):
        """處理取消投票按鈕點擊 - 顯示下拉菜單（私有）"""
        # 檢查投票權限
        if not await self._check_voting_permission(interaction):
            await interaction.response.send_message(
                "❌ 權限不足：只有持有特定身份組的成員可以取消投票",
                ephemeral=True
            )
            return
        
        message_id = interaction.message.id
        
        # 轉換消息ID（如果是恢復的投票）
        if message_id in self.original_to_new.values():
            # 如果是新ID，找到原始ID（如果存在）
            for orig_id, new_id in self.original_to_new.items():
                if new_id == message_id:
                    message_id = orig_id
                    break
        
        user = interaction.user
        user_id = user.id
        display_name = user.display_name
        
        # 獲取專屬價格字典
        prices_dict = self.poll_prices.get(message_id, {})
        if not prices_dict:
            await interaction.response.send_message("❌ 投票數據損壞，無法獲取價格", ephemeral=True)
            return
        
        # 獲取用戶的所有投票項目
        user_votes = self.user_votes[message_id].get(user_id, [])
        
        if not user_votes:
            # 發送私有消息
            embed = discord.Embed(
                description=f"❌ **{display_name}** 沒有投票記錄可取消",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # 創建下拉菜單選項
        options = []
        for i, item in enumerate(user_votes):
            options.append(discord.SelectOption(
                label=f"{item} ({prices_dict.get(item, 0)}円)",  # 使用專屬價格
                value=f"{i}_{item}",  # 使用索引和項目名作為值
                description=f"價格: {prices_dict.get(item, 0)}円"  # 使用專屬價格
            ))
        
        # 創建下拉菜單（單選）
        select = Select(
            placeholder="選擇要取消的投票項目",
            options=options,
            min_values=1,
            max_values=1  # 只能選一個
        )
        
        # 創建確定按鈕
        confirm_btn = Button(
            label="確定取消",
            style=discord.ButtonStyle.danger,
            custom_id="confirm_cancel"
        )
        
        # 創建取消按鈕
        cancel_btn = Button(
            label="取消操作",
            style=discord.ButtonStyle.secondary,
            custom_id="cancel_action"
        )
        
        # 創建自定義視圖以處理超時
        class TimeoutView(View):
            def __init__(self):
                super().__init__(timeout=60)
                self.message = None
                
            async def on_timeout(self):
                if self.message:
                    await self.message.edit(content="❌ 操作已超時，請重新操作", view=None, embed=None)
        
        # 創建視圖
        view = TimeoutView()
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
            index_str, item = value.split("_", 1)
            index = int(index_str)
            
            # 移除投票記錄（使用索引確保移除正確的投票）
            if index < len(self.user_votes[message_id][user_id]): 
                # 獲取實際移除的項目
                removed_item = self.user_votes[message_id][user_id][index]
                
                # 從用戶投票記錄中移除
                del self.user_votes[message_id][user_id][index]
                
                # 從總投票記錄中移除
                # 修正：移除所有匹配的投票記錄（可能有多個相同項目的投票）
                self.votes[message_id] = [
                    (uid, name, voted_item) 
                    for (uid, name, voted_item) in self.votes[message_id] 
                    if not (uid == user_id and voted_item == removed_item)
                ]
                        
                # 移除特殊項目回應（如果有）: 移除該項目對應的特定回應
                if message_id in self.special_item_responses:
                    if user_id in self.special_item_responses[message_id]:
                        if removed_item in self.special_item_responses[message_id][user_id]:
                            # 找到並移除對應索引的回應
                            if index < len(self.special_item_responses[message_id][user_id][removed_item]):
                                del self.special_item_responses[message_id][user_id][removed_item][index]
                            
                            # 如果移除後列表為空，刪除該項目鍵
                            if not self.special_item_responses[message_id][user_id][removed_item]:
                                del self.special_item_responses[message_id][user_id][removed_item]
            else:
                await interaction.response.send_message("❌ 無效的投票項目", ephemeral=True)
                return
            
            # 保存到配置文件
            await self.save_poll_data(message_id)
            
            # 發送公開取消通知
            public_embed = discord.Embed(
                description=f"❌ **{display_name}** 已取消投票：",
                color=discord.Color.red()
            )
            public_embed.add_field(name="項目", value=item, inline=True)
            public_embed.add_field(name="價格", value=f"{prices_dict[item]}円", inline=True)  # 使用專屬價格
            
            await interaction.channel.send(embed=public_embed)
            
            # 刪除私有消息
            await interaction.response.edit_message(content="投票已取消", embed=None, view=None)
            await asyncio.sleep(2)
            await interaction.delete_original_response()
        
        async def cancel_callback(interaction: discord.Interaction):
            """處理取消按鈕點擊（刪除私有消息）"""
            await interaction.response.edit_message(content="操作已取消", embed=None, view=None)
            await asyncio.sleep(2)
            await interaction.delete_original_response()
        
        # 設置回調
        select.callback = select_callback
        confirm_btn.callback = confirm_callback
        cancel_btn.callback = cancel_callback
        
        # 發送下拉菜單（私有）- 簡化界面，只保留下拉清單和按鈕
        message = await interaction.response.send_message(view=view, ephemeral=True)
        view.message = await interaction.original_response()

    async def my_votes_button(self, interaction: discord.Interaction):
        """查看我的投票記錄（私有）"""
        # 檢查投票權限
        if not await self._check_voting_permission(interaction):
            await interaction.response.send_message(
                "❌ 權限不足：只有持有特定身份組的成員可以查看投票記錄",
                ephemeral=True
            )
            return
        
        message_id = interaction.message.id
        
        # 轉換消息ID（如果是恢復的投票）
        if message_id in self.original_to_new.values():
            # 如果是新ID，找到原始ID（如果存在）
            for orig_id, new_id in self.original_to_new.items():
                if new_id == message_id:
                    message_id = orig_id
                    break
        
        user_id = interaction.user.id
        user_display_name = interaction.user.display_name
        
        # 獲取專屬價格字典
        prices_dict = self.poll_prices.get(message_id, {})
        if not prices_dict:
            await interaction.response.send_message("❌ 投票數據損壞，無法獲取價格", ephemeral=True)
            return
        
        # 獲取用戶投票記錄
        if message_id not in self.user_votes or user_id not in self.user_votes[message_id]:
            embed = discord.Embed(
                description="❌ 您在此投票中還沒有投票記錄",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        items = self.user_votes[message_id][user_id]
        # 獲取投票標題
        title = self.poll_titles.get(message_id, "未知投票")
        
        # 創建私有消息
        embed = discord.Embed(
            title="您的投票記錄",
            description=f"在投票 **{title}** 中",
            color=discord.Color.blue()
        )
        
        # 修復：按原始投票項目順序顯示項目
        total = 0
        # 獲取原始投票項目順序
        original_items = self.poll_items.get(message_id, [])
        
        # 統計每個項目的投票次數
        item_counts = defaultdict(int)
        for item in items:
            item_counts[item] += 1
        
        # 按原始順序顯示項目
        for item in original_items:
            if item in item_counts and item_counts[item] > 0:
                count = item_counts[item]
                price = prices_dict.get(item, 0)  # 使用專屬價格
                subtotal = price * count
                total += subtotal
                
                # 顯示特殊項目的額外信息
                if any(special_item.lower() == item.lower() for special_item in self.SPECIAL_ITEMS):
                    # 統計需要單品的次數
                    need_single_count = 0
                    if message_id in self.special_item_responses:
                        if user_id in self.special_item_responses[message_id]:
                            if item in self.special_item_responses[message_id][user_id]:
                                # 獲取該項目的所有回應
                                responses = self.special_item_responses[message_id][user_id][item]
                                # 只統計投票次數內的回應
                                for i in range(min(count, len(responses))):
                                    if responses[i].get("need_single", False):
                                        need_single_count += 1
                    
                    embed.add_field(
                        name=f"{item} × {count}",
                        value=f"小計: {subtotal}円\n需要單品次數: {need_single_count}",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name=f"{item} × {count}",
                        value=f"小計: {subtotal}円",
                        inline=False
                    )
        
        # 顯示不在原始列表中的項目（理論上不應該發生）
        for item, count in item_counts.items():
            if item not in original_items:
                price = prices_dict.get(item, 0)  # 使用專屬價格
                subtotal = price * count
                total += subtotal
                embed.add_field(
                    name=f"{item} × {count} (已移除項目)",
                    value=f"小計: {subtotal}円",
                    inline=False
                )
        
        embed.add_field(
            name="總金額",
            value=f"{total}円",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def results_button(self, interaction: discord.Interaction):
        """處理查看結果按鈕點擊 - 響應公開"""
        # 檢查投票權限
        if not await self._check_voting_permission(interaction):
            await interaction.response.send_message(
                "❌ 權限不足：只有持有特定身份組的成員可以查看結果",
                ephemeral=True
            )
            return
        
        message_id = interaction.message.id
        
        # 轉換消息ID（如果是恢復的投票）
        if message_id in self.original_to_new.values():
            # 如果是新ID，找到原始ID（如果存在）
            for orig_id, new_id in self.original_to_new.items():
                if new_id == message_id:
                    message_id = orig_id
                    break
        
        try:
            embed = await self._generate_results_embed(message_id)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ 獲取結果失敗",
                description=str(e),
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed)

    async def _generate_results_embed(self, message_id: int):
        """生成結果嵌入消息（按投票清單順序排列）"""
        if message_id not in self.poll_items:
            raise ValueError("❌ 無效的ID或投票不存在")
        
        # 獲取專屬價格字典
        prices_dict = self.poll_prices.get(message_id, {})
        if not prices_dict:
            raise ValueError("❌ 投票數據損壞，無法獲取價格")
        
        # 獲取原始投票項目順序
        original_items = self.poll_items[message_id]
        
        # 1. 按用戶分組統計投票
        user_votes = defaultdict(lambda: defaultdict(int))
        # 2. 按項目分組統計總票數
        item_totals = defaultdict(int)
        # 3. 統計特殊項目的單品需求數量
        item_single_counts = defaultdict(int)
        total_amount = 0
        
        # 預先統計特殊項目的單品需求數量
        if message_id in self.special_item_responses:
            for user_id, item_data in self.special_item_responses[message_id].items():
                # 獲取該用戶的投票次數
                user_vote_count = defaultdict(int)
                for vote_item in self.user_votes[message_id].get(user_id, []):
                    user_vote_count[vote_item] += 1
                
                for item, responses in item_data.items():
                    # 檢查是否為特殊項目
                    if any(special_item.lower() == item.lower() for special_item in self.SPECIAL_ITEMS):
                        # 只統計實際投票次數內的回應
                        max_index = min(user_vote_count.get(item, 0), len(responses))
                        for i in range(max_index):
                            if responses[i].get("need_single", False):
                                item_single_counts[item] += 1
        
        # 遍歷所有投票記錄
        for (user_id, display_name, item) in self.votes.get(message_id, []):
            # 統計用戶投票
            user_votes[display_name][item] += 1
            # 統計項目總票數
            item_totals[item] += 1
            
        # 4. 計算用戶總金額
        user_totals = {}
        for user, items_dict in user_votes.items():
            user_total = 0
            for item, count in items_dict.items():
                price = prices_dict.get(item, 0)  # 使用專屬價格
                user_total += price * count
            user_totals[user] = user_total
            total_amount += user_total
        
        # 5. 按用戶總金額降序排序
        sorted_users = sorted(user_totals.items(), key=lambda x: x[1], reverse=True)
        
        # 獲取投票標題
        title = self.poll_titles.get(message_id, "投票結果")
        
        # 創建主結果嵌入
        main_embed = discord.Embed(
            title=f"📊 {title} - 投票結果",
            color=discord.Color.gold()
        )
        
        # 1. 添加用戶投票明細（按原始項目順序排列）
        users_text = []
        for user, total in sorted_users:
            user_items = user_votes[user]
            item_details = []
            
            # 按原始投票清單順序顯示項目
            for item in original_items:
                if item in user_items and user_items[item] > 0:
                    count = user_items[item]
                    item_details.append(f"{item}×{count}")
            
            users_text.append(f"• **{user}**: {' + '.join(item_details)} = **{total}円**")
        
        main_embed.add_field(
            name="👥 用戶投票明細",
            value="\n".join(users_text) if users_text else "無用戶投票",
            inline=False
        )
        
        # 2. 添加項目總票數（按原始項目順序排列，只顯示有票的項目）
        items_text = []
        for item in original_items:
            count = item_totals[item]
            if count > 0:  # 只顯示有票的項目
                # 如果是特殊項目，顯示附加信息
                if any(special_item.lower() == item.lower() for special_item in self.SPECIAL_ITEMS):
                    single_count = item_single_counts.get(item, 0)
                    items_text.append(f"• **{item}** × {count} (單品數：{single_count})")
                else:
                    items_text.append(f"• **{item}** × {count}")
        
        main_embed.add_field(
            name="📝 項目總票數",
            value="\n".join(items_text) if items_text else "無投票記錄",
            inline=False
        )
        
        # 3. 添加全部總金額
        main_embed.add_field(
            name="💰 全部總額",
            value=f"**{total_amount}円**",
            inline=False
        )
        
        return main_embed

    async def add_item_button(self, interaction: discord.Interaction):
        """處理添加項目按鈕點擊 - 支持批量添加"""
        # 檢查投票權限
        if not await self._check_voting_permission(interaction):
            await interaction.response.send_message(
                "❌ 權限不足：只有持有特定身份組的成員可以添加項目",
                ephemeral=True
            )
            return
        
        message_id = interaction.message.id
        
        # 轉換消息ID（如果是恢復的投票）
        if message_id in self.original_to_new.values():
            # 如果是新ID，找到原始ID（如果存在）
            for orig_id, new_id in self.original_to_new.items():
                if new_id == message_id:
                    message_id = orig_id
                    break
        
        # 發送模態窗口獲取新項目信息
        modal = AddItemModal(title="添加新項目（批量）")
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        if not modal.new_items:
            return
        
        added_items = []
        errors = []
        
        try:
            if message_id not in self.poll_items:
                await interaction.followup.send("❌ 投票不存在或已結束", ephemeral=False)
                return
            
            current_count = len(self.poll_items[message_id])
            remaining_slots = 25 - current_count
            
            if remaining_slots <= 0:
                await interaction.followup.send("❌ 投票項目已達上限（25個）", ephemeral=False)
                return
            
            # 獲取專屬價格字典
            prices_dict = self.poll_prices.get(message_id, {})
            
            # 批量添加項目（最多填滿25個位置）
            for i, (item_name, price) in enumerate(modal.new_items):
                if i >= remaining_slots:
                    errors.append(f"❌ 只能添加 {remaining_slots} 個項目（已達上限）")
                    break
                    
                if item_name in self.poll_items[message_id]:
                    errors.append(f"❌ 項目 '{item_name}' 已存在")
                    continue
                    
                # 添加新項目
                self.poll_items[message_id].append(item_name)
                prices_dict[item_name] = price  # 更新專屬價格字典
                added_items.append((item_name, price))
            
            if not added_items:
                error_msg = "\n".join(errors[:3])  # 最多顯示3個錯誤
                await interaction.followup.send(f"❌ 添加失敗:\n{error_msg}", ephemeral=False)
                return
            
            # 更新專屬價格字典
            self.poll_prices[message_id] = prices_dict
            
            # 更新投票消息
            title = self.poll_titles[message_id]
            message = self.active_polls[message_id]
            
            # 創建更新後的嵌入消息
            embed = discord.Embed(
                title=f"📊 {title}",
                description="點擊下方按鈕進行投票",
                color=discord.Color.blue()
            )
            
            # 添加所有項目（包括新項目）
            for i, item in enumerate(self.poll_items[message_id]):
                index = i + 1
                if index <= 10:
                    prefix = f"{index}."
                else:
                    letter = chr(65 + index - 11)
                    prefix = f"{letter}."
                
                embed.add_field(
                    name=f"{prefix} {item}",
                    value=f"```{prices_dict[item]}円```",  # 使用專屬價格
                    inline=False
                )
            
            # 更新按鈕視圖
            view = View(timeout=None)
            
            # 為每個項目添加按鈕
            for item in self.poll_items[message_id]:
                btn = Button(
                    label=f"{item} ({prices_dict[item]}円)",  # 使用專屬價格
                    style=discord.ButtonStyle.primary,
                    custom_id=f"vote_{item}_{message_id}"
                )
                # 使用閉包解決綁定問題
                async def vote_callback(interaction, item=item):
                    await self.vote_button(interaction, item)
                btn.callback = vote_callback
                view.add_item(btn)
            
            # 添加結果按鈕
            results_btn = Button(
                label="查看結果",
                style=discord.ButtonStyle.green,
                custom_id=f"results_{message_id}"
            )
            results_btn.callback = self.results_button
            view.add_item(results_btn)
            
            # 添加取消投票按鈕
            cancel_btn = Button(
                label="取消投票",
                style=discord.ButtonStyle.red,
                custom_id=f"cancel_{message_id}"
            )
            cancel_btn.callback = self.cancel_vote_button
            view.add_item(cancel_btn)
            
            # 添加新項目按鈕
            add_item_btn = Button(
                label="添加項目",
                style=discord.ButtonStyle.secondary,
                custom_id=f"add_item_{message_id}"
            )
            add_item_btn.callback = self.add_item_button
            view.add_item(add_item_btn)
            
            # 添加"我的投票"按鈕
            my_votes_btn = Button(
                label="我的投票",
                style=discord.ButtonStyle.secondary,
                custom_id=f"my_votes_{message_id}"
            )
            my_votes_btn.callback = self.my_votes_button
            view.add_item(my_votes_btn)
            
            # 添加"管理項目"按鈕（僅創建者可見）
            manage_btn = Button(
                label="管理項目",
                style=discord.ButtonStyle.secondary,
                custom_id=f"manage_{message_id}"
            )
            manage_btn.callback = self.manage_items_button
            view.add_item(manage_btn)
            
            # 更新消息
            await message.edit(embed=embed, view=view)
            self.poll_views[message_id] = view
            
            # 保存到配置文件
            await self.save_poll_data(message_id)
            
            # 發送確認消息 - 公開
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
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ 添加項目失敗",
                description=str(e),
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=False)

    # 自定義視圖處理超時
    class ManagementTimeoutView(View):
        """管理項目操作的自定義視圖，處理超時"""
        def __init__(self):
            super().__init__(timeout=300)  # 5分鐘超時
            self.message = None  # 儲存消息物件用於超時編輯
                
        async def on_timeout(self):
            """超時處理"""
            if self.message:
                try:
                    await self.message.edit(content="❌ 操作已超時，請重新操作", view=None)
                except discord.NotFound:
                    pass
                    
        async def on_error(self, interaction: discord.Interaction, error: Exception, item):
            """錯誤處理"""
            await interaction.response.send_message(
                f"❌ 發生錯誤: {str(error)}",
                ephemeral=True
            )
            traceback.print_exc()

    async def manage_items_button(self, interaction: discord.Interaction):
        """管理投票項目（僅創建者和後勤人員可見）"""
        message_id = interaction.message.id
        
        # 轉換消息ID（如果是恢復的投票）
        if message_id in self.original_to_new.values():
            # 如果是新ID，找到原始ID（如果存在）
            for orig_id, new_id in self.original_to_new.items():
                if new_id == message_id:
                    message_id = orig_id
                    break
        
        # 檢查權限：創建者或後勤人員
        creator_id = self.poll_creators.get(message_id)
        special_role = interaction.guild.get_role(self.SPECIAL_ROLE_ID) if interaction.guild else None
        
        # 檢查權限
        is_creator = interaction.user.id == creator_id
        is_special = special_role and special_role in interaction.user.roles
        
        if not (is_creator or is_special):
            # 更新錯誤訊息，包含後勤人員信息
            error_msg = "❌ 只有投票創建者或後勤人員可以管理項目"
            await interaction.response.send_message(
                error_msg,
                ephemeral=True
            )
            return
            
        # 獲取當前項目
        items = self.poll_items.get(message_id, [])
        if not items:
            await interaction.response.send_message(
                "❌ 此投票沒有項目可管理",
                ephemeral=True
            )
            return
        
        # 獲取專屬價格字典
        prices_dict = self.poll_prices.get(message_id, {})
        if not prices_dict:
            await interaction.response.send_message(
                "❌ 投票數據損壞，無法獲取價格",
                ephemeral=True
            )
            return
            
        # 創建下拉菜單選項
        options = []
        for i, item in enumerate(items):
            options.append(discord.SelectOption(
                label=f"{item} ({prices_dict.get(item, 0)}円)",  # 使用專屬價格
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
            style=discord.ButtonStyle.primary,
            custom_id="edit_item"
        )
        
        delete_btn = Button(
            label="刪除項目",
            style=discord.ButtonStyle.danger,
            custom_id="delete_item"
        )
        
        cancel_btn = Button(
            label="取消",
            style=discord.ButtonStyle.secondary,
            custom_id="cancel_manage"
        )
        
        # 創建自定義視圖
        view = self.ManagementTimeoutView()
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
            await interaction.response.defer()  # 關鍵修復：響應交互
        
        async def edit_callback(interaction: discord.Interaction):
            """處理編輯按鈕點擊"""
            nonlocal selected_index
            if selected_index is None:
                await interaction.response.send_message("❌ 請先選擇一個項目", ephemeral=True)
                return
                
            # 獲取當前項目信息
            item = items[selected_index]
            current_price = prices_dict.get(item, 0)
            
            # 發送編輯模態窗口
            modal = EditItemModal(title="編輯項目", item=item, price=current_price)
            await interaction.response.send_modal(modal)
            await modal.wait()
            
            if modal.new_name or modal.new_price is not None:
                # 更新項目信息
                new_name = modal.new_name if modal.new_name else item
                new_price = modal.new_price if modal.new_price is not None else current_price
                
                # 檢查名稱是否重複
                if new_name != item and new_name in items:
                    await interaction.followup.send(
                        f"❌ 項目名稱 '{new_name}' 已存在",
                        ephemeral=True
                    )
                    return
                
                # 更新項目
                self.poll_items[message_id][selected_index] = new_name
                
                # 更新價格
                if item in prices_dict:
                    del prices_dict[item]
                prices_dict[new_name] = new_price
                
                # 更新用戶投票中的項目名稱
                for vote_list in self.user_votes[message_id].values():
                    for i, voted_item in enumerate(vote_list):
                        if voted_item == item:
                            vote_list[i] = new_name
                
                # 更新總投票記錄
                for i, (uid, name, voted_item) in enumerate(self.votes[message_id]):
                    if voted_item == item:
                        self.votes[message_id][i] = (uid, name, new_name)
                
                # 更新特殊項目回應（如果有的話）
                if message_id in self.special_item_responses:
                    for user_id, responses in self.special_item_responses[message_id].items():
                        if item in responses:
                            responses[new_name] = responses.pop(item)
                
                # 更新投票消息
                await update_poll_message()
                
                # 保存到配置文件
                await self.save_poll_data(message_id)
                
                # 發送確認消息
                await interaction.followup.send(
                    f"✅ 項目已更新: `{item}` → `{new_name} ({new_price}円)`",
                    ephemeral=False
                )
        
        async def delete_callback(interaction: discord.Interaction):
            """處理刪除按鈕點擊"""
            nonlocal selected_index
            if selected_index is None:
                await interaction.response.send_message("❌ 請先選擇一個項目", ephemeral=True)
                return
                
            item = items[selected_index]
            
            # 確認刪除
            confirm_embed = discord.Embed(
                title="⚠️ 確認刪除項目",
                description=f"確定要刪除 **{item}** 嗎？此操作無法復原！",
                color=discord.Color.orange()
            )
            confirm_embed.add_field(name="項目", value=item, inline=True)
            confirm_embed.add_field(name="價格", value=f"{prices_dict.get(item, 0)}円", inline=True)
            
            # 使用自定義視圖防止超時
            confirm_view = View(timeout=120)
            confirm_btn = Button(label="確認刪除", style=discord.ButtonStyle.danger)
            cancel_btn = Button(label="取消", style=discord.ButtonStyle.secondary)
            
            async def confirm_delete(interaction: discord.Interaction):
                # 驗證投票是否仍然有效
                if message_id not in self.poll_items:
                    await interaction.response.edit_message(
                        content="❌ 投票已結束",
                        embed=None,
                        view=None
                    )
                    return
                
                # 刪除項目
                del self.poll_items[message_id][selected_index]
                
                # 刪除價格
                if item in prices_dict:
                    del prices_dict[item]
                
                # 從用戶投票中移除
                for vote_list in self.user_votes[message_id].values():
                    while item in vote_list:
                        vote_list.remove(item)
                
                # 從總投票記錄中移除
                self.votes[message_id] = [
                    (uid, name, voted_item) 
                    for (uid, name, voted_item) in self.votes[message_id] 
                    if voted_item != item
                ]
                
                # 移除特殊項目回應
                if message_id in self.special_item_responses:
                    for user_id in self.special_item_responses[message_id]:
                        if item in self.special_item_responses[message_id][user_id]:
                            del self.special_item_responses[message_id][user_id][item]
                
                # 更新投票消息
                await update_poll_message()
                
                # 保存到配置文件
                await self.save_poll_data(message_id)
                
                # 發送確認消息
                await interaction.response.edit_message(
                    content=f"✅ 項目 `{item}` 已刪除",
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
        
        async def cancel_callback(interaction: discord.Interaction):
            """取消管理操作"""
            await interaction.response.edit_message(
                content="管理操作已取消",
                view=None
            )
        
        async def update_poll_message():
            """更新投票消息"""
            # 檢查投票是否仍然存在
            if message_id not in self.poll_items:
                return
            
            title = self.poll_titles[message_id]
            message = self.active_polls[message_id]
            
            # 創建更新後的嵌入消息
            embed = discord.Embed(
                title=f"📊 {title}",
                description="點擊下方按鈕進行投票",
                color=discord.Color.blue()
            )
            
            # 添加所有項目
            for i, item in enumerate(self.poll_items[message_id]):
                index = i + 1
                if index <= 10:
                    prefix = f"{index}."
                else:
                    letter = chr(65 + index - 11)
                    prefix = f"{letter}."
                
                embed.add_field(
                    name=f"{prefix} {item}",
                    value=f"```{prices_dict[item]}円```",  # 使用專屬價格
                    inline=False
                )
            
            # 更新按鈕視圖
            view = View(timeout=None)
            
            # 為每個項目添加按鈕
            for item in self.poll_items[message_id]:
                btn = Button(
                    label=f"{item} ({prices_dict[item]}円)",  # 使用專屬價格
                    style=discord.ButtonStyle.primary,
                    custom_id=f"vote_{item}_{message_id}"
                )
                # 使用默認參數解決lambda綁定問題
                async def vote_callback(interaction, item=item):
                    await self.vote_button(interaction, item)
                btn.callback = vote_callback
                view.add_item(btn)
            
            # 添加結果按鈕
            results_btn = Button(
                label="查看結果",
                style=discord.ButtonStyle.green,
                custom_id=f"results_{message_id}"
            )
            results_btn.callback = self.results_button
            view.add_item(results_btn)
            
            # 添加取消投票按鈕
            cancel_btn = Button(
                label="取消投票",
                style=discord.ButtonStyle.red,
                custom_id=f"cancel_{message_id}"
            )
            cancel_btn.callback = self.cancel_vote_button
            view.add_item(cancel_btn)
            
            # 添加新項目按鈕
            add_item_btn = Button(
                label="添加項目",
                style=discord.ButtonStyle.secondary,
                custom_id=f"add_item_{message_id}"
            )
            add_item_btn.callback = self.add_item_button
            view.add_item(add_item_btn)
            
            # 添加"我的投票"按鈕
            my_votes_btn = Button(
                label="我的投票",
                style=discord.ButtonStyle.secondary,
                custom_id=f"my_votes_{message_id}"
            )
            my_votes_btn.callback = self.my_votes_button
            view.add_item(my_votes_btn)
            
            # 添加"管理項目"按鈕（僅創建者可見）
            manage_btn = Button(
                label="管理項目",
                style=discord.ButtonStyle.secondary,
                custom_id=f"manage_{message_id}"
            )
            manage_btn.callback = self.manage_items_button
            view.add_item(manage_btn)
            
            # 更新消息
            await message.edit(embed=embed, view=view)
            self.poll_views[message_id] = view
        
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

    @commands.command(aliases=["ap"])
    async def active_polls(self, ctx):
        """查看當前活躍的投票 - 響應公開"""
        if not self.active_polls:
            await ctx.send("目前沒有活躍的投票")
            return
        
        # 將活躍投票轉換為列表並排序
        active_polls_list = sorted(
            self.active_polls.items(),
            key=lambda x: x[0]  # 按消息ID排序
        )
        
        # 分頁處理（每頁最多25個）
        PAGE_SIZE = 25
        total_pages = (len(active_polls_list) + PAGE_SIZE - 1) // PAGE_SIZE
        
        for page_index in range(total_pages):
            start_index = page_index * PAGE_SIZE
            end_index = start_index + PAGE_SIZE
            page_data = active_polls_list[start_index:end_index]
            
            embed = discord.Embed(
                title=f"📋 活躍投票列表 (第 {page_index + 1}/{total_pages} 頁)",
                color=discord.Color.purple()
            )
            
            for msg_id, message in page_data:
                title = self.poll_titles.get(msg_id, "未命名投票")
                jump_url = f"[跳轉]({message.jump_url})" if message else "訊息不可用"
                creator = f"<@{self.poll_creators.get(msg_id, '未知')}>"
                
                # 添加原始ID信息（如果是恢復的投票）
                original_id_info = ""
                if msg_id in self.original_to_new.values():
                    for orig_id, new_id in self.original_to_new.items():
                        if new_id == msg_id:
                            original_id_info = f"\n原始ID: `{orig_id}`"
                            break
                
                embed.add_field(
                    name=f"ID: `{msg_id}`",
                    value=(
                        f"**{title}**\n"
                        f"創建者: {creator}\n"
                        f"{jump_url}{original_id_info}"
                    ),
                    inline=False
                )
            
            embed.set_footer(text=f"共 {len(self.active_polls)} 個活躍投票")
            await ctx.send(embed=embed)

    async def is_poll_accessible(self, message_id: int) -> bool:
        """檢查投票是否可訪問（頻道和消息是否存在）"""
        # 檢查頻道是否存在
        channel_id = self.poll_channels.get(message_id)
        if not channel_id:
            return False
            
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return False
            
        # 嘗試獲取原始消息（用於檢查消息是否存在）
        try:
            # 如果是恢復的投票，使用原始ID
            original_id = message_id
            if message_id in self.original_to_new.values():
                for orig_id, new_id in self.original_to_new.items():
                    if new_id == message_id:
                        original_id = orig_id
                        break
            
            # 嘗試獲取消息
            message = await channel.fetch_message(original_id)
            return message is not None
        except discord.NotFound:
            return False
        except discord.Forbidden:
            return False
        except Exception:
            return False

    async def backup_data_internal(self):
        """內部備份方法：備份所有可訪問的投票數據"""
        try:
            # 確保備份目錄存在
            os.makedirs(self.backup_dir, exist_ok=True)
            
            # 創建備份數據（只包含可訪問的投票）
            backup_data = {
                "poll_items": {},
                "votes": {},
                "user_votes": {},
                "poll_prices": {},
                "poll_titles": {},
                "poll_creators": {},
                "original_to_new": self.original_to_new,
                "poll_channels": {},
                "active_poll_channels": {},
                "special_responses": {}
            }

            # 收集所有可訪問的投票ID（包括活躍和非活躍）
            accessible_poll_ids = set()
            
            # 1. 活躍投票：檢查頻道和消息是否存在
            for message_id in list(self.active_polls.keys()):
                if await self.is_poll_accessible(message_id):
                    accessible_poll_ids.add(message_id)
            
            # 2. 非活躍投票：檢查頻道是否存在
            for message_id in list(self.poll_items.keys()):
                # 跳過已經處理過的活躍投票
                if message_id in accessible_poll_ids:
                    continue
                    
                # 檢查頻道是否存在
                channel_id = self.poll_channels.get(message_id)
                if not channel_id:
                    continue
                    
                channel = self.bot.get_channel(channel_id)
                if channel:
                    accessible_poll_ids.add(message_id)
            
            # 備份所有可訪問的投票
            for message_id in accessible_poll_ids:
                backup_data["poll_items"][message_id] = self.poll_items[message_id]
                backup_data["votes"][message_id] = self.votes[message_id]
                backup_data["user_votes"][message_id] = dict(self.user_votes[message_id])
                backup_data["poll_prices"][message_id] = self.poll_prices[message_id]
                backup_data["poll_titles"][message_id] = self.poll_titles[message_id]
                backup_data["poll_creators"][message_id] = self.poll_creators[message_id]
                backup_data["poll_channels"][message_id] = self.poll_channels[message_id]
                backup_data["special_responses"][message_id] = self.special_item_responses.get(message_id, {})
                
                # 如果是活躍投票，記錄頻道ID
                if message_id in self.active_polls:
                    backup_data["active_poll_channels"][message_id] = self.poll_channels[message_id]
            
            # 生成帶時間戳的文件名
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"backup_{timestamp}.json"

            # 寫入文件
            with backup_file.open("w", encoding="utf-8") as f:
                json.dump(backup_data, f, indent=4, ensure_ascii=False)
                
            return backup_file
        except Exception as e:
            traceback.print_exc()
            return None

    @commands.command(aliases=["save", "backup"])
    async def backup_data(self, ctx):
        """手動備份投票數據（僅儲存可訪問的投票）"""
        backup_file = await self.backup_data_internal()
        if backup_file:
            # 統計備份中的投票
            with backup_file.open("r", encoding="utf-8") as f:
                backup_data = json.load(f)
            active_count = len(backup_data.get("active_poll_channels", {}))
            inactive_count = len(backup_data.get("poll_items", {})) - active_count
            await ctx.send(
                f"✅ 投票數據已備份：`{backup_file.name}` (包含 {active_count} 個活躍投票和 {inactive_count} 個可訪問的非活躍投票)",
                file=discord.File(str(backup_file)))
        else:
            await ctx.send("❌ 備份失敗")

    async def _recreate_poll_message(self, channel, title: str, items: list, creator_id: int, original_message_id: int):
        """重新創建投票消息（內部函數）"""
        # 先嘗試關閉原始投票消息
        try:
            # 獲取原始投票消息
            original_channel_id = self.poll_channels.get(original_message_id)
            if original_channel_id:
                original_channel = self.bot.get_channel(original_channel_id)
                if original_channel:
                    try:
                        original_message = await original_channel.fetch_message(original_message_id)
                        
                        # 編輯原始消息為已結束狀態
                        if original_message.embeds:
                            embed = original_message.embeds[0]
                            embed.title = f"❌ 已結束 - {embed.title}"
                            embed.description = "此投票已被新恢復的投票取代"
                            embed.color = discord.Color.dark_grey()
                        
                        # 創建已結束視圖
                        ended_view = View(timeout=None)
                        ended_btn = Button(
                            label="投票已結束",
                            style=discord.ButtonStyle.grey,
                            disabled=True
                        )
                        ended_view.add_item(ended_btn)
                        
                        # 更新原始消息
                        await original_message.edit(embed=embed, view=ended_view)
                        
                        # 從活動投票中移除
                        if original_message_id in self.active_polls:
                            del self.active_polls[original_message_id]
                            
                        # 從配置中標記為非活躍
                        await self.save_poll_data(original_message_id, is_active=False)
                            
                    except discord.NotFound:
                        print(f"原始投票消息 {original_message_id} 已被刪除，無法關閉")
                    except Exception as e:
                        print(f"關閉原始投票時出錯: {e}")
        except Exception as e:
            print(f"嘗試關閉原始投票時發生錯誤: {e}")

        # 獲取專屬價格字典
        prices_dict = self.poll_prices.get(original_message_id, {})
        if not prices_dict:
            await channel.send(f"❌ 無法恢復投票 {original_message_id}，價格數據缺失")
            return
        
        # 創建美觀的投票訊息
        embed = discord.Embed(
            title=f"📊 {title} (已恢復)",
            description="投票已從備份恢復，點擊下方按鈕進行投票",
            color=discord.Color.blue()
        )
        
        # 添加投票項目
        for i, item in enumerate(items):
            index = i + 1
            if index <= 10:
                prefix = f"{index}."
            else:
                letter = chr(65 + index - 11)  # A=65, B=66, 依此類推
                prefix = f"{letter}."
            
            embed.add_field(
                name=f"{prefix} {item}",
                value=f"```{prices_dict[item]}円```",  # 使用專屬價格
                inline=False
            )
        
        # 創建按鈕視圖
        view = View(timeout=None)
        
        # 為每個項目添加按鈕
        for item in items:
            btn = Button(
                label=f"{item} ({prices_dict[item]}円)",  # 使用專屬價格
                style=discord.ButtonStyle.primary
            )
            # 使用閉包正確綁定項目
            async def vote_callback(interaction, item=item):
                await self.vote_button(interaction, item)
            btn.callback = vote_callback
            view.add_item(btn)
        
        # 添加結果按鈕
        results_btn = Button(
            label="查看結果",
            style=discord.ButtonStyle.green
        )
        results_btn.callback = self.results_button
        view.add_item(results_btn)
        
        # 添加取消投票按鈕
        cancel_btn = Button(
            label="取消投票",
            style=discord.ButtonStyle.red
        )
        cancel_btn.callback = self.cancel_vote_button
        view.add_item(cancel_btn)
        
        # 添加新項目按鈕
        add_item_btn = Button(
            label="添加項目",
            style=discord.ButtonStyle.secondary
        )
        add_item_btn.callback = self.add_item_button
        view.add_item(add_item_btn)
        
        # 添加"我的投票"按鈕
        my_votes_btn = Button(
            label="我的投票",
            style=discord.ButtonStyle.secondary
        )
        my_votes_btn.callback = self.my_votes_button
        view.add_item(my_votes_btn)
        
        # 添加"管理項目"按鈕（僅創建者可見）
        manage_btn = Button(
            label="管理項目",
            style=discord.ButtonStyle.secondary
        )
        manage_btn.callback = self.manage_items_button
        view.add_item(manage_btn)
        
        # 發送消息
        message = await channel.send(embed=embed, view=view)
        
        # 更新投票信息（保留原始ID）
        self.poll_views[original_message_id] = view
        
        # 記錄原始ID到新ID的映射
        self.original_to_new[original_message_id] = message.id
        
        # 發送ID訊息（公開）
        id_embed = discord.Embed(
            description=f"投票已恢復！原始ID: `{original_message_id}` | 新消息ID: `{message.id}`",
            color=discord.Color.green()
        )
        await channel.send(embed=id_embed)
        
        return message

    @commands.command(aliases=["restore"])
    @commands.is_owner()
    async def restore_data(self, ctx, backup_file: str):
        """從備份文件恢復投票數據（僅機器人所有者可用）"""
        try:
            # 確保備份目錄存在
            os.makedirs(self.backup_dir, exist_ok=True)
            
            # 構建備份文件路徑
            backup_path = self.backup_dir / backup_file
            
            # 檢查文件是否存在
            if not backup_path.exists():
                await ctx.send(f"❌ 找不到備份文件: `{backup_file}`")
                return
                
            # 讀取備份數據
            with backup_path.open("r", encoding="utf-8") as f:
                backup_data = json.load(f)
                
            # 清除當前內存數據
            self.poll_items.clear()
            self.votes.clear()
            self.user_votes.clear()
            self.poll_prices.clear()  # 使用新的價格儲存結構
            self.poll_titles.clear()
            self.active_polls.clear()
            self.poll_views.clear()
            self.poll_creators.clear()
            self.original_to_new.clear()
            self.poll_channels.clear()
            self.special_item_responses.clear()
            
            # 恢復內存數據
            self.poll_items = {int(k): v for k, v in backup_data.get("poll_items", {}).items()}
            
            # 恢復投票記錄
            self.votes = defaultdict(list)
            for mid, votes in backup_data.get("votes", {}).items():
                self.votes[int(mid)] = votes
                
            # 恢復用戶投票數據
            self.user_votes = defaultdict(lambda: defaultdict(list))
            for mid, user_data in backup_data.get("user_votes", {}).items():
                mid_int = int(mid)
                for uid, items in user_data.items():
                    self.user_votes[mid_int][int(uid)] = items
            
            # 恢復價格數據（使用新的結構）
            self.poll_prices = {int(mid): prices for mid, prices in backup_data.get("poll_prices", {}).items()}
            
            # 恢復標題和創建者
            self.poll_titles = {int(k): v for k, v in backup_data.get("poll_titles", {}).items()}
            self.poll_creators = {int(k): v for k, v in backup_data.get("poll_creators", {}).items()}
            
            # 恢復頻道ID
            self.poll_channels = {int(k): v for k, v in backup_data.get("poll_channels", {}).items()}
            
            # 恢復特殊項目回應
            self.special_item_responses = {}
            for mid, responses in backup_data.get("special_responses", {}).items():
                mid_int = int(mid)
                self.special_item_responses[mid_int] = {}
                for user_id_str, item_data in responses.items():
                    user_id = int(user_id_str)
                    self.special_item_responses[mid_int][user_id] = {}
                    for item, response_list in item_data.items():
                        # 確保每個回應都是列表格式
                        if isinstance(response_list, list):
                            self.special_item_responses[mid_int][user_id][item] = response_list
                        else:
                            # 如果格式不正確，初始化為空列表
                            self.special_item_responses[mid_int][user_id][item] = []
            
            # 恢復映射表
            self.original_to_new = backup_data.get("original_to_new", {})
            
            # 恢復活動投票（使用原始頻道重建投票）
            restored_active_polls = {}
            # 修復：使用正確的字段 active_poll_channels
            active_poll_channels = backup_data.get("active_poll_channels", {})
            
            # 重建活躍投票的消息
            recreate_queue = []
            for mid_str, channel_id in active_poll_channels.items():
                mid = int(mid_str)
                channel = self.bot.get_channel(int(channel_id))
                if not channel:
                    # 頻道不存在，跳過
                    continue
                    
                # 準備重新創建投票
                recreate_queue.append({
                    "message_id": mid,
                    "channel": channel,
                    "title": self.poll_titles.get(mid, "恢復的投票"),
                    "items": self.poll_items[mid],
                    "creator_id": self.poll_creators.get(mid)
                })
                # 將該投票標記為活躍（在重新創建消息後會加入active_polls）
                restored_active_polls[mid] = channel

            # 將恢復的活躍投票記錄到 active_polls（暫時為頻道，稍後替換為消息對象）
            self.active_polls = restored_active_polls
                
            # 保存到Config系統
            for message_id in self.poll_items.keys():
                is_active = message_id in self.active_polls
                await self.save_poll_data(message_id, is_active)
            
            # 重建視圖
            self.poll_views = {}
            
            # 重新發送所有投票消息（避免速率限制）
            await ctx.send(f"✅ 已成功從 `{backup_file}` 恢復數據！共恢復 {len(self.poll_items)} 個投票。")
            await ctx.send("⏳ 正在重新創建投票消息，這可能需要一些時間...")
            
            # 使用佇列和延遲來避免速率限制
            recreate_queue = []
            for msg_id, channel in self.active_polls.items():
                # 只處理有效的投票
                if not channel or msg_id not in self.poll_items:
                    continue
                    
                # 準備重新創建投票
                recreate_queue.append({
                    "message_id": msg_id,
                    "channel": channel,
                    "title": self.poll_titles.get(msg_id, "恢復的投票"),
                    "items": self.poll_items[msg_id],
                    "creator_id": self.poll_creators.get(msg_id)
                })
            
            # 分批處理，避免速率限制
            BATCH_SIZE = 2  # 每次處理的投票數量
            DELAY_SECONDS = 5  # 批次之間的延遲
            
            total_count = len(recreate_queue)
            processed = 0
            
            for i in range(0, total_count, BATCH_SIZE):
                batch = recreate_queue[i:i+BATCH_SIZE]
                
                # 在原始頻道重新發送投票
                for vote_data in batch:
                    try:
                        # 重新創建投票消息
                        new_message = await self._recreate_poll_message(
                            vote_data["channel"],
                            vote_data["title"],
                            vote_data["items"],
                            vote_data["creator_id"],
                            vote_data["message_id"]
                        )
                        
                        # 更新活動投票記錄
                        self.active_polls[vote_data["message_id"]] = new_message
                        processed += 1
                        
                        # 更新進度
                        progress = f"⏳ 已處理 {processed}/{total_count} 個投票"
                        await ctx.send(progress)
                    except Exception as e:
                        error_msg = f"❌ 重新創建投票 {vote_data['message_id']} 失敗: {str(e)}"
                        await ctx.send(error_msg)
                
                # 批次之間延遲
                if i + BATCH_SIZE < total_count:
                    await asyncio.sleep(DELAY_SECONDS)
            
            await ctx.send(f"✅ 所有投票消息已成功重新創建！共處理 {processed}/{total_count} 個投票")
            
        except Exception as e:
            # 打印詳細錯誤信息到控制台
            traceback.print_exc()
            # 發送簡要錯誤信息到頻道
            await ctx.send(f"❌ 恢復失敗: {str(e)}")

    @commands.command(aliases=["myorder"])
    async def my_order(self, ctx):
        """生成用戶所有投票的品項列表（TXT文件）並私訊發送"""
        try:
            # 嘗試私訊用戶
            await ctx.author.send("正在為您生成品項列表，請稍候...")
        except discord.Forbidden:
            # 如果無法私訊，在頻道中提示
            await ctx.send("❌ 無法向您發送私訊，請檢查您的隱私設定")
            return
            
        user_id = ctx.author.id
        user_name = ctx.author.display_name
        
        # 收集用戶在所有投票中的品項
        user_orders = []
        total_amount = 0
        
        # 遍歷所有投票
        for poll_id in self.poll_items.keys():
            # 檢查用戶是否在該投票中有記錄
            if poll_id in self.user_votes and user_id in self.user_votes[poll_id]:
                # 獲取用戶投票列表
                user_votes_list = self.user_votes[poll_id][user_id]
                
                # 新增：跳過沒有投票項目的投票
                if not user_votes_list:
                    continue
                    
                # 獲取投票標題
                title = self.poll_titles.get(poll_id, f"未知投票 (ID: {poll_id})")
                # 獲取專屬價格字典
                prices_dict = self.poll_prices.get(poll_id, {})
                
                # 統計每個項目的數量
                item_counts = defaultdict(int)
                for item in user_votes_list:
                    item_counts[item] += 1
                
                # 計算該投票的總金額
                poll_total = 0
                order_lines = []
                
                # 按原始項目順序顯示
                for item in self.poll_items[poll_id]:
                    if item in item_counts and item_counts[item] > 0:
                        count = item_counts[item]
                        price = prices_dict.get(item, 0)
                        subtotal = price * count
                        poll_total += subtotal
                        
                        # 添加特殊項目備註
                        special_note = ""
                        if any(special_item.lower() == item.lower() for special_item in self.SPECIAL_ITEMS):
                            # 統計需要單品的次數
                            need_single_count = 0
                            if poll_id in self.special_item_responses:
                                if user_id in self.special_item_responses[poll_id]:
                                    if item in self.special_item_responses[poll_id][user_id]:
                                        # 獲取該項目的所有回應
                                        responses = self.special_item_responses[poll_id][user_id][item]
                                        # 只統計投票次數內的回應
                                        for i in range(min(count, len(responses))):
                                            if responses[i].get("need_single", False):
                                                need_single_count += 1
                                        
                                        special_note = f" (需要單品: {need_single_count}次)"
                        
                        order_lines.append(f"  - {item} × {count} @ {price}円 = {subtotal}円{special_note}")
                
                # 添加該投票的總結
                user_orders.append({
                    "title": title,
                    "items": order_lines,
                    "total": poll_total
                })
                total_amount += poll_total
        
        if not user_orders:
            try:
                await ctx.author.send("❌ 您目前沒有任何投票記錄")
            except discord.Forbidden:
                await ctx.send(f"{ctx.author.mention} 您目前沒有任何投票記錄，但無法向您發送私訊")
            return
        
        # 生成TXT文件
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{user_name}_品項_{timestamp}.txt"
        filepath = self.order_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"{user_name} 的品項總覽\n")
            f.write(f"生成時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 40 + "\n\n")
            
            for order in user_orders:
                f.write(f"投票: {order['title']}\n")
                f.write("\n".join(order["items"]))
                f.write(f"\n小計: {order['total']}円\n")
                f.write("-" * 40 + "\n")
            
            f.write(f"\n總金額: {total_amount}円\n")
        
        # 私訊發送文件
        try:
            await ctx.author.send(f"✅ 您的品項列表已生成", file=discord.File(str(filepath)))
            await ctx.send(f"✅ 已將品項列表發送至您的私訊")
        except discord.Forbidden:
            await ctx.send(f"❌ 無法向您發送私訊，請檢查您的隱私設定")

    @commands.command(aliases=["allorder"])
    async def all_orders(self, ctx):
        """生成所有投票項目的總統計（按投票分組顯示）"""
        # 按投票分組統計
        poll_statistics = {}
        all_items = set()  # 用於統計所有出現過的項目（去重）
        grand_total = 0
        
        # 遍歷所有投票
        for poll_id in self.poll_items.keys():
            # 獲取投票標題
            title = self.poll_titles.get(poll_id, f"未知投票 (ID: {poll_id})")
            
            # 獲取專屬價格字典
            prices_dict = self.poll_prices.get(poll_id, {})
            
            # 初始化該投票的統計
            if poll_id not in poll_statistics:
                poll_statistics[poll_id] = {
                    "title": title,
                    "items": defaultdict(int),
                    "total": 0
                }
            
            # 檢查該投票是否有投票記錄
            if poll_id in self.votes:
                for _, _, item in self.votes[poll_id]:
                    # 統計項目數量
                    poll_statistics[poll_id]["items"][item] += 1
                    # 累計項目金額
                    price = prices_dict.get(item, 0)
                    poll_statistics[poll_id]["total"] += price
                    # 添加到全局項目集合
                    all_items.add(item)
            
            # 累加到總金額
            grand_total += poll_statistics[poll_id]["total"]
        
        if not poll_statistics:
            await ctx.send("❌ 目前沒有任何投票記錄")
            return
        
        # 生成TXT文件
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"所有項目統計_{timestamp}.txt"
        filepath = self.order_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("所有投票品項總統計\n")
            f.write(f"生成時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 40 + "\n\n")
            
            # 按投票ID排序
            sorted_polls = sorted(poll_statistics.items(), key=lambda x: x[0])
            
            for poll_id, data in sorted_polls:
                f.write(f"投票：{data['title']}\n")
                
                # 按項目名稱排序
                sorted_items = sorted(data["items"].items(), key=lambda x: x[0])
                
                for item, count in sorted_items:
                    price = self.poll_prices.get(poll_id, {}).get(item, 0)
                    item_total = price * count
                    f.write(f"- {item}: {count}個 = {item_total}円\n")
                
                f.write(f"---------\n")
                f.write(f"小計: {data['total']}円\n\n")
            
            f.write("=" * 40 + "\n")
            f.write(f"總金額: {grand_total}円\n")
            f.write(f"項目種類: {len(all_items)}")
        
        # 發送文件
        await ctx.send(f"✅ 所有品項統計已生成", file=discord.File(str(filepath)))


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
                errors.append(f"第{i}行: 格式錯誤（需要項目名稱和價格）")
                continue
                
            item_name = match.group(1).strip()
            try:
                price = int(match.group(2))
                if price <= 0:
                    errors.append(f"第{i}行: 價格必須是正整數")
                    continue
                    
                valid_items.append((item_name, price))
            except ValueError:
                errors.append(f"第{i}行: 無效的價格 '{match.group(2)}'")
        
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
                if self.new_price <= 0:
                    await interaction.response.send_message(
                        "❌ 價格必須是正整數",
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

async def setup(bot):

    await bot.add_cog(PollCog(bot))
