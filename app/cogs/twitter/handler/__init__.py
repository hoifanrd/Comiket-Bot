import discord

from cogs.twitter import utils
import sql_database


async def update_shinagaki_message(channel: discord.Thread):
    
    if channel is None:
        return False

    circle_data = await sql_database.get_circle_by_channel_id(channel.id)
    if circle_data is None:
        return False

    new_thread_content = utils.gen_thread_msg(circle_data)
    try:
        thread_msg = channel.parent.get_partial_message(channel.id)
        await thread_msg.edit(content=new_thread_content)
    except Exception as e:
        return False
    
    return True