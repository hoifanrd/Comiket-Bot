
from discord.ext import commands
from discord import app_commands, Interaction
from discord.ui import View, Select, Button
import discord

from cogs.twitter.ui.modals import CircleInfoModal, CircleBoothModal
from cogs.twitter.ui.views import SelectCircleRowView

import cogs.twitter.api.twitter as twitter_api
import cogs.twitter.api.anthropic as anthropic_api
import cogs.twitter.api.googlesheet as googlesheet_api
from cogs.twitter import database
from cogs.twitter import utils

import aiohttp
import io
import asyncio
import json

class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)

# 定義名為 Twitter 的 Cog
class Twitter(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name = "twitter_create", description = "從 Twitter 自動建立品書")
    @app_commands.describe(url = "品書 URL")
    async def twitter_create(self, interaction: Interaction, url: str):
        
        if interaction.channel_id in utils.DEFAULT_DAY1_CHANNELS:
            day = 1
        elif interaction.channel_id in utils.DEFAULT_DAY2_CHANNELS:
            day = 2
        else:
            await interaction.response.send_message("❌請在指定的品書頻道使用此指令！", ephemeral=True)
            return
        

        await interaction.response.defer(ephemeral=True)
        try:
            name, title, content, media_links = twitter_api.get_twitter_details(url)
        except Exception as e:
            await interaction.followup.send(f"❌ 無法從 Twitter 獲取資料", ephemeral=True)
            return
    
        circle_data = database.find_circle_by_tweeter_name(name, day)
        
        if not circle_data:
            gpt_circle_data = anthropic_api.gen_circle_by_tweet_data(title, content, day)

            circle_data = database.find_circle_by_row_booth(gpt_circle_data.get('row', ''), gpt_circle_data.get('booth', ''), day)
            circle_data = {
                'circle_name': circle_data.get('circle_name', '') or gpt_circle_data.get('circle_name', ''),
                'author_name': circle_data.get('author_name', '') or gpt_circle_data.get('author_name', ''),
                'row': circle_data.get('row', '') or gpt_circle_data.get('row', ''),
                'booth': circle_data.get('booth', '') or gpt_circle_data.get('booth', ''),
                'has_two_days': gpt_circle_data['has_two_days'],
            }
        
        circle_data['author_link'] = 'https://x.com/' + name
        circle_data['media_links'] = media_links
        circle_data['day'] = day
        
        await self._create_circle_info_modal(interaction, circle_data)
            

    async def _create_circle_info_modal(self, interaction: Interaction, circle_data: dict):

        async def create_callback(interaction: discord.Interaction):
            """按鈕回調，發送模態窗口"""
            modal = CircleInfoModal(circle_data=circle_data, title="社團畫師資訊")
            await interaction.response.send_modal(modal)
            await modal.wait()
            circle_data['author_name'] = modal.author_name
            circle_data['circle_name'] = modal.circle_name
            circle_data['addition'] = modal.addition

            await self._create_circle_row_booth_modal(interaction, circle_data)
            await interaction.delete_original_response()

        embed = discord.Embed(
            title="📝建立品書",
            description="點擊下方按鈕進行以建立品書～",
            color=discord.Color.blue()
        )
        create_view = View()

        create_btn = discord.ui.Button(
            label="建立品書",
            style=discord.ButtonStyle.green,
        )
        create_btn.callback = create_callback
        create_view.add_item(create_btn)

        await interaction.followup.send(embed=embed, view=create_view, ephemeral=True)



    async def _create_circle_row_booth_modal(self, interaction: Interaction, circle_data: dict):
                
        async def submit_callback(new_interaction: Interaction, selected_row: str):
            circle_data['row'] = selected_row
            modal = CircleBoothModal(circle_data=circle_data, title="攤位位置")
            await new_interaction.response.send_modal(modal)
            await modal.wait()
            
            circle_data['booth'] = modal.booth
            await self._create_circle_two_day_ask(new_interaction, circle_data)
            await new_interaction.delete_original_response()

        view = SelectCircleRowView(circle_data=circle_data, submit_callback=submit_callback)
        message = await interaction.followup.send("請選擇攤位所在的字母分類：", view=view, ephemeral=True)


    async def _create_circle_two_day_ask(self, interaction: Interaction, circle_data: dict):

        view = View(timeout=60)

        if isinstance(circle_data['has_two_days'], bool):
            default_value = circle_data['has_two_days']
        else:
            default_value = False

        select = Select(
            placeholder="(兩天？)",
            options=[discord.SelectOption(label="是", value=True, default=default_value), discord.SelectOption(label="否", value=False, default=not default_value)],
            min_values=1,
            max_values=1
        )
        button = Button(
            label="確定",
            style=discord.ButtonStyle.green,
        )

        view.add_item(select)
        view.add_item(button)

        has_two_days = False
        async def select_callback(interaction: discord.Interaction):
            nonlocal has_two_days
            has_two_days = interaction.data["values"][0]
            await interaction.response.defer()
        
        async def button_callback(interaction: discord.Interaction):
            circle_data['has_two_days'] = has_two_days
            await self._create_circle_final_confirm(interaction, circle_data)
            await message.delete()

        select.callback = select_callback
        button.callback = button_callback

        message = await interaction.followup.send("攤位是否為兩天？", view=view, ephemeral=True)


    async def _create_circle_final_confirm(self, interaction: Interaction, circle_data: dict):
        circle_hall = utils.get_hall(circle_data)
        circle_data['circle_hall'] = circle_hall

        embed = discord.Embed(
            title="❓ 確認品書資訊",
            description=f"- **社團名稱**: {circle_data['circle_name']}\n"
                        f"- **畫師名稱**: {circle_data['author_name']}\n"
                        f"- **攤位場館**: {circle_data['circle_hall']}\n"
                        f"- **攤位位置**: {circle_data['row']}{circle_data['booth']}\n"
                        f"- **兩天活動**: {'是' if circle_data['has_two_days'] else '否'}\n"
                        f"- **備註**: {circle_data['addition']}\n",
            color=discord.Color.green()
        )

        view = View(timeout=60)

        async def confirm_callback(new_interaction: discord.Interaction):
            await new_interaction.response.send_message("✅ 品書正在建立中...", ephemeral=True)
            await interaction.delete_original_response()

            res, msg = await googlesheet_api.fill_in_spreadsheet_from_circle(circle_data)
            if res:
                msg_title = f"{circle_data['author_name']} / {circle_data['day']} 日目 / {circle_data['row']} {circle_data['booth']} /「{circle_data['circle_name']}」"
                new_thread = await new_interaction.channel.create_thread(name=msg_title)
                await new_interaction.followup.send(f"✅ 品書已建立！\n{new_thread.jump_url}", ephemeral=True)

                googlesheet_api.fill_in_spreadsheet_dc_link(circle_data, msg['excel_row_id'], new_thread.jump_url)

                thread_msg = f"{msg_title}\n{circle_data['author_link']}\n攤位級別 : {msg['circle_area']}\nDC識別編號 : {msg['circle_sheet_id']}\n備註 :{circle_data['addition']}"
                sent_thread_msg = await new_thread.send(thread_msg)
                await sent_thread_msg.edit(suppress=True)

                if circle_data['media_links']:
                    view = View(timeout=120)

                    confirm_btn = Button(label="確認", style=discord.ButtonStyle.green)
                    cancel_btn = Button(label="取消", style=discord.ButtonStyle.red)

                    async def confirm_btn_callback(new_interaction: discord.Interaction):
                        await new_interaction.response.defer(ephemeral=True)
                        await self._send_twitter_media_to_thread(new_thread, circle_data['media_links'])
                        await new_interaction.followup.send("🖼️ 圖片已傳送到品書串！", ephemeral=True)
                        await asyncio.sleep(2)
                        await message.delete()

                    async def cancel_btn_callback(new_interaction: discord.Interaction):
                        await message.delete()

                    view.add_item(confirm_btn)
                    view.add_item(cancel_btn)

                    confirm_btn.callback = confirm_btn_callback
                    cancel_btn.callback = cancel_btn_callback

                    message = await new_interaction.followup.send(f"🖼️偵測到 Twitter 推文中附有圖片、要把圖片傳到品書串嗎？", ephemeral=True, view=view)

            else:
                await new_interaction.followup.send(f"📊 品書已存在！\n{msg['exist_channel']}", ephemeral=True)
            

        async def cancel_btn_callback(new_interaction: discord.Interaction):
            await new_interaction.response.send_message("❌ 品書建立已取消", ephemeral=True)
            await interaction.delete_original_response()

        confirm_btn = Button(label="確認", style=discord.ButtonStyle.green)
        cancel_btn = Button(label="取消", style=discord.ButtonStyle.red)

        confirm_btn.callback = confirm_callback
        cancel_btn.callback = cancel_btn_callback

        view.add_item(confirm_btn)
        view.add_item(cancel_btn)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


    async def _send_twitter_media_to_thread(self, thread: discord.Thread, media_links: list):

        files = []
        for idx, url in enumerate(media_links):
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    image_data = io.BytesIO(await response.content.read())
                    image_data.seek(0)
                    files.append(discord.File(image_data, filename=f"image_{idx + 1}.jpg"))
                    
        await thread.send(files=files)



# Cog 載入 Bot 中
async def setup(bot: commands.Bot):

    database.init_circle_data()
    await bot.add_cog(Twitter(bot))

