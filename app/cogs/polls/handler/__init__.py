from cogs.polls import database
import discord
from discord.ui import View, Button

import cogs.polls.ui.views as views
from cogs.polls.utils import is_special_item


async def generate_results_embed(poll_id):
        
    title = database.get_poll_title(poll_id)
    
    # 創建主結果嵌入
    main_embed = discord.Embed(
        title=f"📊 {title} - 投票結果",
        color=discord.Color.gold()
    )

    # 用戶投票明細
    res = database.get_poll_results_for_users(poll_id)
    
    users_text = []
    total_amount = 0
    for user_name, items, user_price in res:
        item_details = map(lambda x: f"{x[0]}x{x[1]}", items)
        users_text.append(f"• **{user_name}**: {' + '.join(item_details)} = **{user_price}円**")
        total_amount += user_price

    main_embed.add_field(
        name="👥 用戶投票明細",
        value="\n".join(users_text) if users_text else "無用戶投票",
        inline=False
    )

    # 項目總票數
    res = database.get_poll_results_for_items(poll_id)

    items_text = []
    for item_name, count, single_count in res:
        if is_special_item(item_name):
            items_text.append(f"• **{item_name}** × {count} (單品數：{single_count})")
        else:
            items_text.append(f"• **{item_name}** × {count}")

    main_embed.add_field(
        name="📝 項目總票數",
        value="\n".join(items_text) if items_text else "無投票記錄",
        inline=False
    )

    main_embed.add_field(
        name="💰 全部總額",
        value=f"**{total_amount}円**",
        inline=False
    )

    return main_embed



async def update_poll_message(channel: discord.Thread , poll_id: int):

    if channel is None:
        return False

    status = database.get_poll_status(poll_id)

    item_list = database.get_items_by_poll(poll_id)
    title = database.get_poll_title(poll_id)

    items = [item[0] for item in item_list]
    prices = [item[1] for item in item_list]
    
    if status == 'Active':
        embed = discord.Embed(
            title=f"📊 {title}",
            description="點擊下方按鈕進行投票",
            color=discord.Color.blue()
        )
    elif status == 'Paused':
        embed = discord.Embed(
            title=f"❌ 已暫停 - 📊 {title}",
            description="點擊下方按鈕進行投票",
            color=discord.Color.orange()
        )
    elif status == 'Ended':
        embed = discord.Embed(
            title=f"❌ 已結束 - 📊 {title}",
            description="此投票已結束",
            color=discord.Color.dark_grey()
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

    view = views.PersistentPollView(poll_id, items, prices, status)

    message_id = database.get_poll_message_id(poll_id)
    message = channel.get_partial_message(message_id)

    try:
        await message.edit(embed=embed, view=view)
    except discord.NotFound:
        return False
    
    return True
