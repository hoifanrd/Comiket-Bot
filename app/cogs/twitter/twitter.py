
from discord.ext import commands
from discord import app_commands, Interaction
from discord.ui import View, Select, Button
import discord
import traceback

from cogs.twitter.ui.modals import CircleInfoModal, CircleBoothModal
from cogs.twitter.ui.views import SelectCircleRowView

import cogs.twitter.api.twitter as twitter_api
import cogs.twitter.api.anthropic as anthropic_api
import cogs.twitter.api.pixiv as pixiv_api
from cogs.twitter import database
from cogs.twitter import utils

import sql_database

from PIL import Image
from urllib.parse import urlparse
import aiohttp
import io
import asyncio
import json
import os

class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)

# 定義名為 Twitter 的 Cog
class Twitter(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name = "magic", description = "從 Twitter/Pixiv 自動建立品書")
    @app_commands.describe(url = "品書 URL")
    async def magic(self, interaction: Interaction, url: str):
        
        if interaction.channel_id in utils.DEFAULT_DAY1_CHANNELS:
            day = 1
        elif interaction.channel_id in utils.DEFAULT_DAY2_CHANNELS:
            day = 2
        else:
            await interaction.response.send_message("❌請在指定的品書頻道使用此指令！", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)

        link_domain = None
        async with aiohttp.ClientSession(
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"},
            max_line_size=8190 * 5,
            max_field_size=8190 * 5,
        ) as session:
            async with session.get(url, allow_redirects=True, timeout=5) as response:
                domain = urlparse(str(response.url)).netloc.lower()
                if domain.endswith("twitter.com") or domain.endswith("x.com"):
                    link_domain = 'Twitter'
                elif domain.endswith("pixiv.net"):
                    link_domain = 'Pixiv'

        if not link_domain:
            await interaction.followup.send("❌ 這不是一個有效的 Twitter/Pixiv 品書連結！", ephemeral=True)
            return

        try:
            if link_domain == 'Twitter':
                name, title, content, media_links = await twitter_api.get_twitter_details(url)
            elif link_domain == 'Pixiv':
                name, title, content, media_links = await pixiv_api.get_pixiv_details(url)
        except Exception:
            traceback.print_exc()
            await interaction.followup.send(f"❌ 無法獲取資料，請稍後再試", ephemeral=True)
            return
    
        circle_data = database.find_circle_by_user_name(link_domain, name, day)
        
        if not circle_data:
            gpt_circle_data = await anthropic_api.gen_circle_by_tweet_data(title, content, day)

            circle_data = database.find_circle_by_row_booth(gpt_circle_data.row, gpt_circle_data.booth, day)
            
            circle_data.circle_name = circle_data.circle_name or gpt_circle_data.circle_name
            circle_data.author_name = circle_data.author_name or gpt_circle_data.author_name
            circle_data.row = circle_data.row or gpt_circle_data.row
            circle_data.booth = circle_data.booth or gpt_circle_data.booth
            circle_data.has_two_days = gpt_circle_data.has_two_days

        circle_data.user_id = name
        circle_data.link_domain = link_domain
        circle_data.shinagaki_img_urls = media_links
        circle_data.day = day

        if not circle_data:
            await self._create_circle_row_booth_modal(interaction, circle_data)
        else:
            await self._create_circle_final_confirm(interaction, circle_data)

            
    async def _create_circle_info_modal(self, interaction: Interaction, circle_data: utils.CircleForm):

        modal = CircleInfoModal(circle_data=circle_data, title="社團畫師資訊")
        await interaction.response.send_modal(modal)
        await modal.wait()
        circle_data.author_name = modal.author_name
        circle_data.circle_name = modal.circle_name
        circle_data.remarks = modal.addition

        await self._create_circle_two_day_ask(interaction, circle_data)

       

    async def _create_circle_row_booth_modal(self, interaction: Interaction, circle_data: utils.CircleForm):
            
        async def submit_callback(new_interaction: Interaction, selected_row: str):
            
            modal = CircleBoothModal(circle_data=circle_data, title="攤位位置")
            await new_interaction.response.send_modal(modal)
            await modal.wait()

            new_circle_data = database.find_circle_by_row_booth(selected_row, modal.booth, circle_data.day)

            # Update circle_data with the given circle data if it exists
            async def proceed_final_confirm(new_interaction: discord.Interaction):
                circle_data.row = selected_row
                circle_data.booth = modal.booth
                circle_data.circle_name = new_circle_data.circle_name
                circle_data.author_name = new_circle_data.author_name
                circle_data.hall = new_circle_data.hall
                circle_data.has_two_days = new_circle_data.has_two_days
                circle_data.circle_id = new_circle_data.circle_id

                await self._create_circle_final_confirm(new_interaction, circle_data)


            # If not exist, ask for confirmation again
            if not new_circle_data:
                view = View(timeout=60)

                async def confirm_callback(new_interaction: Interaction):
                    await new_interaction.response.defer()
                    await proceed_final_confirm(interaction)

                async def reenter_callback(new_interaction: Interaction):
                    await new_interaction.response.defer()
                    await self._create_circle_row_booth_modal(interaction, circle_data)

                reenter_btn = Button(label="重新輸入", style=discord.ButtonStyle.primary)
                confirm_btn = Button(label="繼續", style=discord.ButtonStyle.secondary)

                reenter_btn.callback = reenter_callback
                confirm_btn.callback = confirm_callback

                view.add_item(reenter_btn)
                view.add_item(confirm_btn)
                
                await interaction.edit_original_response(content="❌ 無法找到該攤位資料，確定要繼續嗎？", embed=None, view=view)
                return
            
            await proceed_final_confirm(interaction)


        view = SelectCircleRowView(circle_data=circle_data, submit_callback=submit_callback)
        await interaction.edit_original_response(content="請選擇攤位所在的字母分類：", view=view, embed=None)


    async def _create_circle_two_day_ask(self, interaction: Interaction, circle_data: utils.CircleForm):

        view = View(timeout=60)

        if isinstance(circle_data.has_two_days, bool):
            default_value = circle_data.has_two_days
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

        has_two_days = default_value
        async def select_callback(new_interaction: discord.Interaction):
            nonlocal has_two_days
            has_two_days = new_interaction.data["values"][0]
            await new_interaction.response.defer()
        
        async def button_callback(new_interaction: discord.Interaction):
            await new_interaction.response.defer()
            circle_data.has_two_days = has_two_days
            await self._create_circle_final_confirm(interaction, circle_data)

        select.callback = select_callback
        button.callback = button_callback

        await interaction.edit_original_response(content="攤位是否為兩天？", view=view, embed=None)


    async def _create_circle_final_confirm(self, interaction: Interaction, circle_data: utils.CircleForm):

        embed = discord.Embed(
            title="❓ 確認品書資訊",
            description=f"- **社團名稱**: {circle_data.circle_name}\n"
                        f"- **畫師名稱**: {circle_data.author_name}\n"
                        f"- **攤位場館**: {circle_data.hall.replace('e', '東').replace('w', '西').replace('s', '南')}\n"
                        f"- **攤位位置**: {circle_data.row}{circle_data.booth}\n"
                        f"- **兩天活動**: {'是' if circle_data.has_two_days else '否'}\n"
                        f"- **備註**: {circle_data.remarks}\n",
            color=discord.Color.green()
        )

        view = View(timeout=60)

        async def confirm_callback(new_interaction: discord.Interaction):
            await new_interaction.response.defer()
            await interaction.edit_original_response(content="✅ 品書正在建立中...",embed=None, view=None)

            # No more google spreadsheet
            # res, msg = await googlesheet_api.fill_in_spreadsheet_from_circle(circle_data)
            found_circle_data = await sql_database.get_circle_by_event_day_row_booth(
                os.environ.get('CURR_EVENT'), circle_data.day, circle_data.row, circle_data.booth)
            
            if found_circle_data is not None:
                found_channel = self.bot.get_channel(found_circle_data.channel_id)
                if found_channel is not None:
                    channel_url = found_channel.jump_url
                    await interaction.edit_original_response(f"📊 品書已存在！\n{channel_url}", embed=None, view=None)
                    return
                else:
                    await sql_database.delete_circle_by_channel_id(found_circle_data.channel_id)
            
            if circle_data.shinagaki_img_urls:
                view = View(timeout=120)

                confirm_btn = Button(label="確認", style=discord.ButtonStyle.green)
                cancel_btn = Button(label="取消", style=discord.ButtonStyle.red)


                async def confirm_btn_callback(new_interaction: discord.Interaction):
                    await new_interaction.response.defer()

                    # 禁用按鈕
                    confirm_btn.disabled = True
                    cancel_btn.disabled = True
                    await interaction.edit_original_response(view=view)

                    files = await self._generate_shinagaki_images(circle_data.link_domain, circle_data.shinagaki_img_urls)
                    await self._create_shinagaki_thread(interaction, circle_data, files)


                async def cancel_btn_callback(new_interaction: discord.Interaction):
                    await new_interaction.response.defer()

                    # 禁用按鈕
                    confirm_btn.disabled = True
                    cancel_btn.disabled = True
                    await interaction.edit_original_response(view=view)

                    await self._create_shinagaki_thread(interaction, circle_data)

                    
                view.add_item(confirm_btn)
                view.add_item(cancel_btn)

                confirm_btn.callback = confirm_btn_callback
                cancel_btn.callback = cancel_btn_callback

                await interaction.edit_original_response(content=f"🖼️偵測到 {circle_data.link_domain} 推文中附有圖片、要把圖片傳到品書串嗎？", view=view, embed=None)

            else:
                # 如果沒有圖片，直接建立品書串
                await self._create_shinagaki_thread(interaction, circle_data)
                    

                
        async def cancel_btn_callback(new_interaction: discord.Interaction):
            await new_interaction.response.defer()
            await interaction.edit_original_response(content="❌ 品書建立已取消", view=None, embed=None)
            await asyncio.sleep(2)
            await interaction.delete_original_response()

        async def edit_info_btn_callback(new_interaction: discord.Interaction):
            await self._create_circle_info_modal(new_interaction, circle_data)

        async def edit_row_booth_callback(new_interaction: discord.Interaction):
            await new_interaction.response.defer()
            await self._create_circle_row_booth_modal(interaction, circle_data)

        confirm_btn = Button(label="確認", style=discord.ButtonStyle.green)
        cancel_btn = Button(label="取消", style=discord.ButtonStyle.red)
        edit_info_btn = Button(label="編輯資料", style=discord.ButtonStyle.primary)
        edit_row_booth_btn = Button(label="更改攤位", style=discord.ButtonStyle.secondary)

        confirm_btn.callback = confirm_callback
        cancel_btn.callback = cancel_btn_callback
        edit_info_btn.callback = edit_info_btn_callback
        edit_row_booth_btn.callback = edit_row_booth_callback

        view.add_item(confirm_btn)
        view.add_item(cancel_btn)
        view.add_item(edit_info_btn)
        view.add_item(edit_row_booth_btn)

        await interaction.edit_original_response(content=None, embed=embed, view=view)


    async def _create_shinagaki_thread(self, interaction: discord.Interaction, circle_data: utils.CircleForm, files: list[discord.File] = None) -> discord.Thread:

        SOCIAL_LINK_PREFIX = {
            'Twitter': 'https://x.com/',
            'Pixiv': 'https://www.pixiv.net/users/'
        }

        msg_title = utils.gen_thread_title(circle_data)
        author_link = SOCIAL_LINK_PREFIX[circle_data.link_domain] + circle_data.user_id
        thread_msg = f"{msg_title}\n{author_link}\n攤位級別 : {database.get_space_cat(circle_data)}\n備註 :{circle_data.remarks}"

        cur_day_channels = utils.DAY1_CHANNELS if circle_data.day == 1 else utils.DAY2_CHANNELS

        sent_thread_msg = await self.bot.get_channel(cur_day_channels[circle_data.hall]) \
            .send(thread_msg, suppress_embeds=True, files=files)
        new_thread = await sent_thread_msg.create_thread(name=msg_title)

        thread_circle_id = utils.gen_thread_circle_id(circle_data)
        await new_thread.send(thread_circle_id)
        await new_thread.send(interaction.user.mention)

        space_cat = database.get_space_cat(circle_data)
        await sql_database.add_circle(circle_data, space_cat, new_thread.id)

        await interaction.edit_original_response(content=f"✅ 品書建立完成！\n{new_thread.jump_url}", embed=None, view=None)
    
        # ======== Create pool =========
        await asyncio.sleep(1)

        # Comments - Removed auto item price list
        # gather_list = await asyncio.gather(*[anthropic_api.gen_item_price_list_by_image(file.fp) for file in (files or [])])

        # items = []
        # prices = []
        # for i, p in gather_list:
        #     items += i
        #     prices += p

        class FakeInteraction:
            def __init__(self, channel, user):
                self.channel = channel
                self.user = user
        
        fake_interaction = FakeInteraction(new_thread, interaction.user)
        cog_poll = self.bot.get_cog('Polls')
        await cog_poll.commands['create_poll']._create_poll_message(fake_interaction, circle_data.circle_name, [], [])
        


    async def _generate_shinagaki_images(self, link_domain: str, media_links: list):

        images = []

        if link_domain == 'Pixiv':
            for url in media_links:
                image_data = await pixiv_api.download_image(url)
                image_data.seek(0)
                images.append(image_data)
        else:
            for idx, url in enumerate(media_links):
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        image_data = io.BytesIO(await response.content.read())
                        image_data.seek(0)
                        images.append(image_data)

        files = []
        for idx, image_data in enumerate(images):
            if idx >= 10:
                break

            compressed_image_data: io.BytesIO = image_data
            next_quality = 85
            while next_quality > 0 and len(compressed_image_data.getvalue()) > 1024 * 1024 * 1.5:  # 1.5 MB
                image = Image.open(image_data)
                compressed_image_data = io.BytesIO()
                image.save(compressed_image_data, format="JPEG", optimize=True, quality=next_quality)
                compressed_image_data.seek(0)
                next_quality -= 5

            files.append(discord.File(compressed_image_data, filename=f"image_{idx + 1}.jpg"))

        return files


    @commands.Cog.listener()
    async def on_raw_thread_delete(self, payload: discord.RawThreadDeleteEvent):
        await sql_database.delete_circle_by_channel_id(payload.thread_id)


# Cog 載入 Bot 中
async def setup(bot: commands.Bot):
    database.preprocess_data()
    await bot.add_cog(Twitter(bot))

