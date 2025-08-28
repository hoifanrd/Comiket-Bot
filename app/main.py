import discord
import asyncio
import os
import itertools
from discord.ext import commands

import sql_database
from cogs.polls.ui.views import PersistentPollView

discord.utils.setup_logging(level=discord.utils.logging.INFO)
intents = discord.Intents.all()
bot = commands.Bot(command_prefix = os.getenv("PREFIX", "!"), intents=intents)

# 當機器人完成啟動時
@bot.event
async def on_ready():
    slash = await bot.tree.sync()
    print(f"目前登入身份 --> {bot.user}")
    print(f"載入 {len(slash)} 個斜線指令")

# 載入指令程式檔案
@bot.command()
async def load(ctx, extension):
    await bot.load_extension(f"cogs.{extension}")
    await ctx.send(f"Loaded {extension} done.")

# 卸載指令檔案
@bot.command()
async def unload(ctx, extension):
    await bot.unload_extension(f"cogs.{extension}")
    await ctx.send(f"UnLoaded {extension} done.")

# 重新載入程式檔案
@bot.command()
async def reload(ctx, extension):
    await bot.reload_extension(f"cogs.{extension}")
    await ctx.send(f"Reload {extension} done.")

# 一開始bot開機需載入全部程式檔案
async def load_extensions():
    for filename in os.listdir("./cogs"):
        await bot.load_extension(f"cogs.{filename}")

async def main():
    await sql_database.init_db()
    async with bot:
        await load_extensions()
        bot.setup_hook = setup_hook
        await bot.start(os.getenv("TOKEN"))

async def setup_hook():
    results = await sql_database.get_poll_with_buttons()
    for poll_id, item_list in itertools.groupby(results, key=lambda x: x[0]):
        item_list = list(item_list)
        items = [item[1] for item in item_list if item[1] is not None]
        prices = [item[2] for item in item_list if item[2] is not None]
        bot.add_view(PersistentPollView(poll_id, items, prices))

if __name__ == "__main__":
    asyncio.run(main())
