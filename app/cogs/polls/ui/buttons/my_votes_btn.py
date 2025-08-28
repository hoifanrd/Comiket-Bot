from discord.ui import Button
import discord

from cogs.polls.utils import check_voting_permission, is_special_item
import sql_database

class MyVotesButton(Button):
    def __init__(self, poll_id: int):
        super().__init__(
            label="我的投票",
            custom_id=f"poll_{poll_id}_my_votes",
            style=discord.ButtonStyle.secondary
        )
        self.poll_id = poll_id

    async def callback(self, interaction: discord.Interaction):
        # 檢查是否有權限查看自己的投票
        if not check_voting_permission(interaction):
            await interaction.response.send_message(
                "❌ 權限不足：只有持有特定身份組的成員可以查看自己的投票",
                ephemeral=True
            )
            return
        
        user_id = interaction.user.id

        user_items = await sql_database.get_my_votes_by_poll_and_user(self.poll_id, user_id)
        if not user_items:
            embed = discord.Embed(
                description="❌ 您在此投票中還沒有投票記錄",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        title = await sql_database.get_poll_title(self.poll_id)

        # 創建私有消息
        embed = discord.Embed(
            title="您的投票記錄",
            description=f"在投票 **{title}** 中",
            color=discord.Color.blue()
        )

        total = 0
        for item in user_items:
            item_name, count, subtotal, need_single_count = item
            total += subtotal
            if is_special_item(item_name):
                embed.add_field(
                    name=f"{item_name} × {count}",
                    value=f"小計: {subtotal}円\n需要單品次數: {need_single_count}",
                    inline=False
                )
            else:
                embed.add_field(
                    name=f"{item_name} × {count}",
                    value=f"小計: {subtotal}円",
                    inline=False
                )
        
        embed.add_field(
            name="總金額",
            value=f"{total}円",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)