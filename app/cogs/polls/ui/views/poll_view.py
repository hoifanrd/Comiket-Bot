import discord
from discord.ui import View, Button
from cogs.polls.ui.buttons import *

class PersistentPollView(View):
    def __init__(self, pool_id: int, items: list, prices: list, status: str = 'Active'):
        super().__init__(timeout=None)

        if status == 'Ended':
            ended_btn = Button(
                label="投票已結束",
                style=discord.ButtonStyle.grey,
                disabled=True
            )
            self.add_item(ended_btn)
            return

        if status == 'Active':
            for item, price in zip(items, prices):
                self.add_item(ItemButton(pool_id, item, price))
        
        self.add_item(ResultButton(pool_id))
        self.add_item(CancelVoteButton(pool_id))
        self.add_item(AddItemButton(pool_id))
        self.add_item(MyVotesButton(pool_id))
        self.add_item(ManageButton(pool_id))