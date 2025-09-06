import itertools
import discord
import io
import datetime
import xlsxwriter
import os

from discord.ui import View, Button, Select

import sql_database
from cogs.polls import utils
import cogs.twitter.database as circle_database 

PAGE_SIZE = 25
HALF2FULL = dict((i, i + 0xFEE0) for i in range(0x21, 0x7F))

# A workaround to allow async __init__ in a class
class aobject(object):
    async def __new__(cls, *a, **kw):
        instance = super().__new__(cls)
        await instance.__init__(*a, **kw)
        return instance

    async def __init__(self):
        pass


class PersistentMyOrderView(View, aobject):
    async def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.embed_pages = await self._fetch_embeds_pages_from_order_data()
        self.cur_page = 0

        self.prev_page_btn = Button(
            label="上一頁",
            style=discord.ButtonStyle.primary,
            disabled=True,
            custom_id=f"myorder_{user_id}_prev"
        )
        self.next_page_btn = Button(
            label="下一頁",
            style=discord.ButtonStyle.primary,
            disabled=len(self.embed_pages) <= 1,
            custom_id=f"myorder_{user_id}_next"
        )
        export_csv_btn = Button(
            label="匯出所有品項",
            style=discord.ButtonStyle.green,
            custom_id=f"myorder_{user_id}_export"
        )

        self.selected_day = None
        self.selected_hall = None

        self.filter_day_select = Select(
            placeholder="N日目：(無)",
            options=[discord.SelectOption(label="(無)", value='none'), 
                     discord.SelectOption(label="１日目", value='1'),
                     discord.SelectOption(label="２日目", value='2')
            ],
            min_values=1,
            max_values=1,
            custom_id=f"myorder_{user_id}_day"
        )

        self.filter_hall_select = Select(
            placeholder="場地分類：(無)",
            options=[discord.SelectOption(label="(無)", value='none')] +
                    [discord.SelectOption(label=hall.replace('e', '東').replace('w', '西').replace('s', '南').translate(HALF2FULL), value=hall)
                        for hall in circle_database.get_all_specific_halls()],
            min_values=1,
            max_values=1,
            custom_id=f"myorder_{user_id}_hall"
        )

        self.prev_page_btn.callback = self._on_prev_page
        self.next_page_btn.callback = self._on_next_page
        self.filter_day_select.callback = self._on_day_select
        self.filter_hall_select.callback = self._on_hall_select
        export_csv_btn.callback = self._on_export

        self.add_item(self.filter_day_select)
        self.add_item(self.filter_hall_select)
        self.add_item(self.prev_page_btn)
        self.add_item(self.next_page_btn)
        self.add_item(export_csv_btn)


    def _get_hall_select_placeholder(self):
        if self.selected_hall is None:
            return "場地分類：(無)"
        else:
            return f"場地分類：{self.selected_hall.replace('e', '東').replace('w', '西').replace('s', '南').translate(HALF2FULL)}"

    def _get_day_select_placeholder(self):
        if self.selected_day is None:
            return "N日目：(無)"
        else:
            return f"N日目：{str(self.selected_day).translate(HALF2FULL)}日目"


    async def _on_export(self, interaction: discord.Interaction):
        await interaction.response.send_message("✅ 正在匯出...", ephemeral=True)
        orders = await sql_database.get_myorder_export(interaction.user.id)
        
        orders_simplified = []
        for circle, iter in itertools.groupby(orders, key=lambda x: (x[0], x[1], x[2], x[3], x[4], x[5], x[6], x[7])):
            total_price = sum(x[9] * x[10] for x in iter)
            orders_simplified.append(circle + (total_price,))

        
        with io.BytesIO() as buf:
            workbook = xlsxwriter.Workbook(buf, {'in_memory': True})

            simplified_sheet = workbook.add_worksheet('品項總覽')
            simplified_sheet.write_row(0, 0, ['DC頻道ID', '活動名稱', '活動日目', '攤位場地', '攤位字母分類', '攤位位置', '社團名稱', '畫師名稱', '總金額'])
            for row_idx, order in enumerate(orders_simplified, start=1):
                order = list(order)
                order[0] = str(int(order[0]))
                simplified_sheet.write_row(row_idx, 0, order)
                
            detail_sheet = workbook.add_worksheet('品項明細')
            detail_sheet.write_row(0, 0, ['DC頻道ID', '活動名稱', '活動日目', '攤位場地', '攤位字母分類', '攤位位置', '社團名稱', '畫師名稱', '物品名稱', '單個價格', '需要數量', '需要單品數量'])
            for row_idx, order in enumerate(orders, start=1):
                order = list(order)
                order[0] = str(int(order[0]))
                detail_sheet.write_row(row_idx, 0, order)

            workbook.close()

            buf.seek(0)
            await interaction.followup.send(file=discord.File(buf, filename=f'{interaction.user.name}_品項_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'))
        
        await interaction.delete_original_response()


    async def _on_hall_select(self, interaction: discord.Interaction):
        self.selected_hall = interaction.data["values"][0]
        if self.selected_hall == 'none':
            self.selected_hall = None
        self.filter_hall_select.placeholder = self._get_hall_select_placeholder()

        self.cur_page = 0
        self.embed_pages = await self._fetch_embeds_pages_from_order_data(day=self.selected_day, hall=self.selected_hall)
        if self.embed_pages:
            await self._update_page(interaction)

    async def _on_day_select(self, interaction: discord.Interaction):
        self.selected_day = interaction.data["values"][0]
        if self.selected_day == 'none':
            self.selected_day = None
        else:
            self.selected_day = int(self.selected_day)
        self.filter_day_select.placeholder = self._get_day_select_placeholder()

        self.cur_page = 0
        self.embed_pages = await self._fetch_embeds_pages_from_order_data(day=self.selected_day, hall=self.selected_hall)
        if self.embed_pages:
            await self._update_page(interaction)


    async def _update_page(self, interaction: discord.Interaction):
        self.prev_page_btn.disabled = self.cur_page == 0
        self.next_page_btn.disabled = self.cur_page == len(self.embed_pages) - 1
        await interaction.response.edit_message(view=self, embed=self._get_embed())

    async def _on_prev_page(self, interaction: discord.Interaction):
        self.cur_page = self.cur_page - 1
        await self._update_page(interaction)

    async def _on_next_page(self, interaction: discord.Interaction):
        self.cur_page = self.cur_page + 1
        await self._update_page(interaction)


    def _get_embed(self):
        return self.embed_pages[self.cur_page]

    async def _fetch_embeds_pages_from_order_data(self, hall: str = None, day: int = None) -> list:
        user_votes = await sql_database.get_all_votes_by_user(self.user_id, hall=hall, day=day)

        user_orders = []
        for poll_id, iter in itertools.groupby(user_votes, key=lambda x: x[0]):
            order_lines = []
            poll_total = 0
            for _, channel_id, item_name, count, price, need_single_count in iter:
                if utils.is_special_item(item_name):
                    order_lines.append(f"- {item_name} × {count} @ {price}円 = {count * price}円 (需要單品: {need_single_count}次)")
                else:
                    order_lines.append(f"- {item_name} × {count} @ {price}円 = {count * price}円")
                poll_total += count * price

            user_orders.append({
                "channel_id": channel_id,
                "items": order_lines,
                "total": poll_total
            })

        # ================= Generate embeds =================
        if not user_orders:
            embed = discord.Embed(
                title=f"📋 我的訂單: {os.environ.get('CURR_EVENT', '未知活動').capitalize()}",
                color=discord.Color.blue()
            )

            embed.description = "❌您沒有相關的投票記錄"
            return [embed]


        all_embeds = []
        page_embed = discord.Embed(
            title=f"📋 {os.environ.get('CURR_EVENT', '未知活動').capitalize()}: 我的訂單",
            color=discord.Color.blue()
        )
        field_in_page = 0
        page_chars = 0
        total_amount = 0

        for total_idx, order in enumerate(user_orders):

            items_str = "\n".join(order["items"])
            embed_name = f"{total_idx+1}. <#{order['channel_id']}>"
            embed_value = items_str + f"\n**攤位總計: {order['total']}円**\n**　**"

            page_embed.add_field(
                name=embed_name,
                value=embed_value,
                inline=False
            )
            total_amount += order['total']

            field_in_page += 1
            page_chars += len(embed_name) + len(embed_value)

            if page_chars >= 5400 or field_in_page >= PAGE_SIZE:
                all_embeds.append(page_embed)
                page_embed = discord.Embed(
                    title="📋 我的訂單",
                    color=discord.Color.blue()
                )
                field_in_page = 0
                page_chars = 0
        
        if field_in_page > 0:
            all_embeds.append(page_embed)

        for idx, embed in enumerate(all_embeds):
            embed.set_footer(text=f"總金額: {total_amount}円 （第 {idx+1}/{len(all_embeds)} 頁）")
        
        return all_embeds