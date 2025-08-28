
    @commands.command(aliases=["ap"])
    async def active_polls(self, ctx):
        """列出所有活躍的投票"""
        active_polls = sql_database.get_active_polls()
        
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



    @commands.command(aliases=["allorder"])
    async def all_orders(self, ctx):
        """生成所有投票項目的總統計（按投票分組顯示）"""

        all_votes = sql_database.get_all_votes()
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



