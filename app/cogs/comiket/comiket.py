import discord
import re
import asyncio
import traceback
import itertools
import datetime
import io

from discord.ext import commands
from discord.ui import Button, View

from cogs.comiket.ui.modals import CreatePollModal
from cogs.comiket.ui.views import PersistentPollView, TimeoutView
from cogs.comiket import database
from cogs.comiket import utils
from cogs.comiket import handler

# 定義名為 Comiket 的 Cog
class Comiket(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
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
            await self._create_poll_message(ctx_copy, modal.title, items, prices)
            await msg.delete()
            view.stop()
        
        button.callback = button_callback


    async def _create_poll_message(self, ctx, title: str, items: list, prices: list):
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
        
        # 新增投票到資料庫
        poll_id = database.get_next_poll_id()

        # 創建按鈕視圖
        view = PersistentPollView(poll_id, items, prices)
        
        message = await ctx.send(embed=embed, view=view)
        
        lastrowid = database.create_poll(title, ctx.channel.id, message.id, ctx.author.id, items, prices)
        assert lastrowid == poll_id

        # 發送ID訊息（公開）
        id_embed = discord.Embed(
            description=f"投票已創建！ID: `{poll_id}`",
            color=discord.Color.green()
        )
        await ctx.send(embed=id_embed)



    @commands.command(aliases=["end"])
    async def End(self, ctx, poll_id: int = None):
        if poll_id is None: 
            await ctx.send("❌ 請提供要結束的投票ID")
            return

        try:
            creator_id = database.get_poll_creator(poll_id)
        except ValueError:
            await ctx.send("❌ ID錯誤，找不到指定的投票")
            return

        if not (ctx.author.id == creator_id or utils.check_admin_permission(ctx)):
            await ctx.send("❌ 權限不足：只有投票創建者或管理員可以結束投票")
            return

        if database.get_poll_status(poll_id) == "Ended":
            await ctx.send("❌ 投票已經結束")
            return
    
        await self._end_poll(ctx, poll_id)


    async def _end_poll(self, ctx, poll_id: int):

        database.update_poll_status(poll_id, "Ended")
        
        # 更新投票消息
        results_embed = await handler.generate_results_embed(poll_id)
        original_channel_id = database.get_poll_channel_id(poll_id)
        original_channel = self.bot.get_channel(original_channel_id)

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
        
        await handler.update_poll_message(original_channel, poll_id)
        
        confirm_embed = discord.Embed(
            description=f"✅ 投票 ID: `{poll_id}` 已成功結束",
            color=discord.Color.green()
        )
        
        # 確認訊息始終在當前頻道發送
        await ctx.send(embed=confirm_embed)



    @commands.command(aliases=["endall"])
    async def end_all_polls(self, ctx):
        """終止所有活躍的投票（僅限特定用戶）"""
        # 檢查用戶權限
        if not utils.check_endall_permission(ctx):
            await ctx.send("❌ 您沒有權限使用此命令")
            return

        # 確認操作
        active_polls = database.get_active_polls()
        confirm_embed = discord.Embed(
            title="⚠️ 確認終止所有投票",
            description=f"確定要終止所有 {len(active_polls)} 個活躍投票嗎？此操作無法復原！",
            color=discord.Color.orange()
        )
        confirm_embed.set_footer(text="此操作將在每個投票的原始頻道發布結果")
        
        confirm_view = TimeoutView(timeout=60)
        confirm_btn = Button(label="確認終止", style=discord.ButtonStyle.danger)
        cancel_btn = Button(label="取消", style=discord.ButtonStyle.secondary)
        
        
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
            await confirm_msg.edit(view=confirm_view)
            
            # 終止所有投票
            success_count = 0
            failed_count = 0
            
            for poll_id, _, channel_id, _, _ in active_polls:
                try: 
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
                    await self._end_poll(fake_ctx, poll_id)
                    success_count += 1
                    
                    # 避免速率限制
                    await asyncio.sleep(0.8)
                    
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
            confirm_view.stop()
        

        async def cancel_callback(interaction: discord.Interaction):
            """取消操作"""
            # 檢查是否為命令發起者
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ 只有發起命令的用戶可以取消此操作", ephemeral=True)
                return
                
            await interaction.response.defer()
            await confirm_msg.delete()
            await ctx.send("操作已取消")
            confirm_view.stop()

        
        confirm_btn.callback = confirm_callback
        cancel_btn.callback = cancel_callback

        confirm_view.add_item(confirm_btn)
        confirm_view.add_item(cancel_btn)

        confirm_msg = await ctx.send(embed=confirm_embed, view=confirm_view)
        confirm_view.message = confirm_msg


    @commands.command(aliases=["pause"])
    async def Pause(self, ctx, poll_id: int = None):
        """暫停指定投票（不再接受新投票）"""
        if poll_id is None: 
            await ctx.send("❌ 請提供要暫停的投票ID")
            return

        try:
            creator_id = database.get_poll_creator(poll_id)
        except ValueError:
            await ctx.send("❌ ID錯誤，找不到指定的投票")
            return

        if not (ctx.author.id == creator_id or utils.check_admin_permission(ctx)):
            await ctx.send("❌ 權限不足：只有投票創建者或後勤人員可以暫停此投票")
            return
    
        if database.get_poll_status(poll_id) == "Paused":
            await ctx.send("❌ 投票已經暫停")
            return
    
        database.update_poll_status(poll_id, "Paused")
        
        # 更新投票消息
        original_channel_id = database.get_poll_channel_id(poll_id)
        original_channel = self.bot.get_channel(original_channel_id)

        res = await handler.update_poll_message(original_channel, poll_id)
        if not res:
            await ctx.send("❌ 原始投票消息已被刪除")
            return

        await ctx.send(f"✅ 投票 `{poll_id}` 已暫停")



    @commands.command(aliases=["pauseall"])
    async def pause_all_polls(self, ctx):
        if not utils.check_endall_permission(ctx):
            await ctx.send("❌ 您沒有權限使用此命令")
            return

        # 確認操作
        active_polls = database.get_active_polls()
        confirm_embed = discord.Embed(
            title="⚠️ 確認暫停所有投票",
            description=f"確定要暫停所有 {len(active_polls)} 個活躍投票嗎？",
            color=discord.Color.yellow()
        )

        confirm_view = TimeoutView(timeout=60)
        confirm_btn = Button(label="確認暫停", style=discord.ButtonStyle.danger)
        cancel_btn = Button(label="取消", style=discord.ButtonStyle.secondary)
        
        
        async def confirm_callback(interaction: discord.Interaction):
            """處理確認暫停操作"""
            # 檢查是否為命令發起者
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ 只有發起命令的用戶可以確認此操作", ephemeral=True)
                return
                
            await interaction.response.defer()
            
            # 禁用按鈕防止重複點擊
            confirm_btn.disabled = True
            cancel_btn.disabled = True
            await confirm_msg.edit(view=confirm_view)
            
            # 終止所有投票
            success_count = 0
            failed_count = 0
            
            for poll_id, _, channel_id, _, _ in active_polls:
                try: 
                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        failed_count += 1
                        continue
                    
                    database.update_poll_status(poll_id, "Paused")
        
                    # 更新投票消息
                    original_channel_id = database.get_poll_channel_id(poll_id)
                    original_channel = self.bot.get_channel(original_channel_id)

                    res = await handler.update_poll_message(original_channel, poll_id)
                    if not res:
                        failed_count += 1
                        continue

                    success_count += 1
                    
                    # 避免速率限制
                    await asyncio.sleep(0.8)
                    
                except Exception as e:
                    failed_count += 1
                    traceback.print_exc()
            
            # 發送總結報告
            result_embed = discord.Embed(
                title="✅ 所有投票已暫停",
                description=f"成功暫停: {success_count} 個\n失敗: {failed_count} 個",
                color=discord.Color.green()
            )
            await ctx.send(embed=result_embed)
            
            # 刪除確認消息
            await confirm_msg.delete()
            confirm_view.stop()
        

        async def cancel_callback(interaction: discord.Interaction):
            """取消操作"""
            # 檢查是否為命令發起者
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ 只有發起命令的用戶可以取消此操作", ephemeral=True)
                return
                
            await interaction.response.defer()
            await confirm_msg.delete()
            await ctx.send("操作已取消")
            confirm_view.stop()

        
        confirm_btn.callback = confirm_callback
        cancel_btn.callback = cancel_callback

        confirm_view.add_item(confirm_btn)
        confirm_view.add_item(cancel_btn)

        confirm_msg = await ctx.send(embed=confirm_embed, view=confirm_view)
        confirm_view.message = confirm_msg



    @commands.command(aliases=["resume"])
    async def Resume(self, ctx, poll_id: int = None):
        """恢復指定投票（重新接受新投票）"""
        if poll_id is None: 
            await ctx.send("❌ 請提供要恢復的投票ID")
            return

        try:
            creator_id = database.get_poll_creator(poll_id)
        except ValueError:
            await ctx.send("❌ ID錯誤，找不到指定的投票")
            return

        if not (ctx.author.id == creator_id or utils.check_admin_permission(ctx)):
            await ctx.send("❌ 權限不足：只有投票創建者或後勤人員可以恢復此投票")
            return
    
        if database.get_poll_status(poll_id) != "Paused":
            await ctx.send("❌ 投票未處於暫停狀態")
            return
    
        database.update_poll_status(poll_id, "Active")
        
        # 更新投票消息
        original_channel_id = database.get_poll_channel_id(poll_id)
        original_channel = self.bot.get_channel(original_channel_id)

        res = await handler.update_poll_message(original_channel, poll_id)
        if not res:
            await ctx.send("❌ 原始投票消息已被刪除")
            return

        await ctx.send(f"✅ 投票 `{poll_id}` 已重新開啟")


    @commands.command(aliases=["resumeall"])
    async def resume_all_polls(self, ctx):
        if not utils.check_endall_permission(ctx):
            await ctx.send("❌ 您沒有權限使用此命令")
            return

        # 確認操作
        paused_polls = database.get_paused_polls()
        confirm_embed = discord.Embed(
            title="🔄 確認恢復所有投票",
            description=f"確定要恢復所有 {len(paused_polls)} 個活躍投票嗎？",
            color=discord.Color.blue()
        )

        confirm_view = TimeoutView(timeout=60)
        confirm_btn = Button(label="確認恢復", style=discord.ButtonStyle.primary)
        cancel_btn = Button(label="取消", style=discord.ButtonStyle.secondary)
        
        
        async def confirm_callback(interaction: discord.Interaction):
            """處理確認恢復操作"""
            # 檢查是否為命令發起者
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ 只有發起命令的用戶可以確認此操作", ephemeral=True)
                return
                
            await interaction.response.defer()
            
            # 禁用按鈕防止重複點擊
            confirm_btn.disabled = True
            cancel_btn.disabled = True
            await confirm_msg.edit(view=confirm_view)
            
            # 終止所有投票
            success_count = 0
            failed_count = 0
            
            for poll_id, _, channel_id, _, _ in paused_polls:
                try: 
                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        failed_count += 1
                        continue
                    
                    database.update_poll_status(poll_id, "Active")
        
                    # 更新投票消息
                    original_channel_id = database.get_poll_channel_id(poll_id)
                    original_channel = self.bot.get_channel(original_channel_id)

                    res = await handler.update_poll_message(original_channel, poll_id)
                    if not res:
                        failed_count += 1
                        continue

                    success_count += 1
                    
                    # 避免速率限制
                    await asyncio.sleep(0.8)
                    
                except Exception as e:
                    failed_count += 1
                    traceback.print_exc()
            
            # 發送總結報告
            result_embed = discord.Embed(
                title="✅ 所有投票已恢復",
                description=f"成功恢復: {success_count} 個\n失敗: {failed_count} 個",
                color=discord.Color.green()
            )
            await ctx.send(embed=result_embed)
            
            # 刪除確認消息
            await confirm_msg.delete()
            confirm_view.stop()
        

        async def cancel_callback(interaction: discord.Interaction):
            """取消操作"""
            # 檢查是否為命令發起者
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ 只有發起命令的用戶可以取消此操作", ephemeral=True)
                return
                
            await interaction.response.defer()
            await confirm_msg.delete()
            await ctx.send("操作已取消")
            confirm_view.stop()

        
        confirm_btn.callback = confirm_callback
        cancel_btn.callback = cancel_callback

        confirm_view.add_item(confirm_btn)
        confirm_view.add_item(cancel_btn)

        confirm_msg = await ctx.send(embed=confirm_embed, view=confirm_view)
        confirm_view.message = confirm_msg


    @commands.command(aliases=["ap"])
    async def active_polls(self, ctx):
        """列出所有活躍的投票"""
        active_polls = database.get_active_polls()
        
        if not active_polls:
            await ctx.send("❌ 當前沒有活躍的投票")
            return
        
        # 分頁處理（每頁最多25個）
        PAGE_SIZE = 25
        total_pages = (len(active_polls) + PAGE_SIZE - 1) // PAGE_SIZE
        
        for page_index in range(total_pages):
            start_index = page_index * PAGE_SIZE
            end_index = start_index + PAGE_SIZE
            page_data = active_polls[start_index:end_index]
            
            embed = discord.Embed(
                title=f"📋 活躍投票列表 (第 {page_index + 1}/{total_pages} 頁)",
                color=discord.Color.purple()
            )
            
            for poll_id, title, channel_id, message_id, creator_id in page_data:
                original_channel = self.bot.get_channel(channel_id)

                if original_channel:
                    message_url = original_channel.get_partial_message(message_id).jump_url
                    jump_url = f"[跳轉]({message_url})"
                else:
                    jump_url = "訊息不可用"
                creator = f"<@{creator_id}>"
                
                embed.add_field(
                    name=f"ID: `{poll_id}`",
                    value=(
                        f"**{title}**\n"
                        f"創建者: {creator}\n"
                        f"{jump_url}"
                    ),
                    inline=False
                )
            
            embed.set_footer(text=f"共 {len(active_polls)} 個活躍投票")
            await ctx.send(embed=embed)


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

        # 獲取用戶在所有投票中的投票記錄
        user_votes = database.get_all_votes_by_user(user_id)
        for poll_id, iter in itertools.groupby(user_votes, key=lambda x: x[0]):
            order_lines = []
            poll_total = 0
            for _, title, item_name, count, price, need_single_count in iter:
                if utils.is_special_item(item_name):
                    order_lines.append(f"  - {item_name} × {count} @ {price}円 = {count * price}円 (需要單品: {need_single_count}次)")
                else:
                    order_lines.append(f"  - {item_name} × {count} @ {price}円 = {count * price}円")
                poll_total += count * price

            total_amount += poll_total
            user_orders.append({
                "title": title,
                "items": order_lines,
                "total": poll_total
            })
        
        if not user_orders:
            try:
                await ctx.author.send("❌ 您目前沒有任何投票記錄")
            except discord.Forbidden:
                await ctx.send(f"{ctx.author.mention} 您目前沒有任何投票記錄，但無法向您發送私訊")
            return
    
        # 生成TXT文件
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{user_name}_品項_{timestamp}.txt"

        with io.BytesIO() as buf:
            with io.TextIOWrapper(buf, encoding='utf-8') as f:
                f.write(f"{user_name} 的品項總覽\n")
                f.write(f"生成時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 40 + "\n\n")
                
                for order in user_orders:
                    f.write(f"投票: {order['title']}\n")
                    f.write("\n".join(order['items']))
                    f.write(f"\n小計: {order['total']}円\n")
                    f.write("-" * 40 + "\n")
                
                f.write(f"\n總金額: {total_amount}円\n")

                # 私訊發送文件
                f.seek(0)
                try:
                    await ctx.author.send(f"✅ 您的品項列表已生成", file=discord.File(buf, filename=filename))
                    await ctx.send(f"✅ 已將品項列表發送至您的私訊")
                except discord.Forbidden:
                    await ctx.send(f"❌ 無法向您發送私訊，請檢查您的隱私設定")


    @commands.command(aliases=["allorder"])
    async def all_orders(self, ctx):
        """生成所有投票項目的總統計（按投票分組顯示）"""

        all_votes = database.get_all_votes()
        # 按投票分組統計
        all_orders = []
        all_items_set = set()
        total_amount = 0

        for poll_id, iter in itertools.groupby(all_votes, key=lambda x: x[0]):
            order_lines = []
            poll_total = 0
            for _, title, item_name, count, price, need_single_count in iter:
                if utils.is_special_item(item_name):
                    order_lines.append(f"  - {item_name} × {count} @ {price}円 = {count * price}円 (需要單品: {need_single_count}次)")
                else:
                    order_lines.append(f"  - {item_name} × {count} @ {price}円 = {count * price}円")
                poll_total += count * price
                all_items_set.add(item_name)

            total_amount += poll_total
            all_orders.append({
                "title": title,
                "items": order_lines,
                "total": poll_total
            })
        
        if not all_orders:
            await ctx.send("❌ 目前沒有任何投票記錄")
            return
    
        # 生成TXT文件
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"所有項目統計_{timestamp}.txt"

        with io.BytesIO() as buf:
            with io.TextIOWrapper(buf, encoding='utf-8') as f:
                f.write(f"所有投票品項總統計\n")
                f.write(f"生成時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 40 + "\n\n")
                
                for order in all_orders:
                    f.write(f"投票: {order['title']}\n")
                    f.write("\n".join(order['items']))
                    f.write(f"\n小計: {order['total']}円\n")
                    f.write("-" * 40 + "\n")
                
                f.write(f"\n總金額: {total_amount}円\n")
                f.write(f"項目種類: {len(all_items_set)}")

                # 私訊發送文件
                f.seek(0)
                await ctx.send(f"✅ 所有品項列表已生成", file=discord.File(buf, filename=filename))





# Cog 載入 Bot 中
async def setup(bot: commands.Bot):
    database.init_db()
    await bot.add_cog(Comiket(bot))