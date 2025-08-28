from discord.ui import View, Select
import discord

from cogs.twitter import utils

class SelectCircleRowView(View):

    def __init__(self, circle_data: utils.CircleForm, submit_callback: callable):
        super().__init__(timeout=90)
        self.circle_data = circle_data
        self.submit_callback = submit_callback

        drop_lists = []
        for v in utils.CHAR_GROUPS.values():
            if len(v) <= 25:
                drop_lists.append(list(v))
            else:
                half_idx = len(v) // 2
                drop_lists.append(list(v[:half_idx]))
                drop_lists.append(list(v[half_idx:]))
        
        self.options_list = [[discord.SelectOption(label=row, value=row) if row != circle_data.row
                              else discord.SelectOption(label=row, value=row, default=True) for row in drop_list] for drop_list in drop_lists]

        cur_page = None
        self.selected_row = None
        for i, drop_list in enumerate(drop_lists):
            if circle_data.row in drop_list:
                cur_page = i
                self.selected_row = circle_data.row
                break

        for i, option_list in enumerate(self.options_list):
            if i != cur_page:
                option_list[0].default = True
        
        self.cur_page = cur_page if cur_page is not None else 0
        self.selected_row = self.selected_row if self.selected_row is not None else self.options_list[self.cur_page][0].value

        self.cur_select = Select(
            placeholder="(字母分類)",
            options=self.options_list[self.cur_page],
            min_values=1,
            max_values=1
        )

        submit_btn = discord.ui.Button(
            label="確定",
            style=discord.ButtonStyle.success,
        )
        self.prev_page_btn = discord.ui.Button(
            label="上一頁",
            style=discord.ButtonStyle.primary,
            disabled=cur_page == 0
        )
        self.next_page_btn = discord.ui.Button(
            label="下一頁",
            style=discord.ButtonStyle.primary,
        )

        self.cur_select.callback = self._on_select
        submit_btn.callback = self.on_submit
        self.prev_page_btn.callback = self._on_prev_page
        self.next_page_btn.callback = self._on_next_page

        self.add_item(self.cur_select)
        self.add_item(submit_btn)
        self.add_item(self.prev_page_btn)
        self.add_item(self.next_page_btn)
    
    async def on_submit(self, interaction: discord.Interaction):
        if self.selected_row is None:
            await interaction.response.send_message("❌請選擇一個品書行！", ephemeral=True)
            return
        await self.submit_callback(interaction, self.selected_row)

    async def _on_select(self, interaction: discord.Interaction):
        self.selected_row = interaction.data["values"][0]
        await interaction.response.defer()

    async def _update_page(self, interaction: discord.Interaction):
        self.cur_select.options = self.options_list[self.cur_page]
        self.prev_page_btn.disabled = self.cur_page == 0
        self.next_page_btn.disabled = self.cur_page == len(self.options_list) - 1
        self.selected_row = self.options_list[self.cur_page][0].value
        await interaction.response.edit_message(view=self)

    async def _on_prev_page(self, interaction: discord.Interaction):
        self.cur_page = self.cur_page - 1
        await self._update_page(interaction)

    async def _on_next_page(self, interaction: discord.Interaction):
        self.cur_page = self.cur_page + 1
        await self._update_page(interaction)