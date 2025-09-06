import os
import asyncpg
import cogs.twitter.utils as twitter_utils

poll: asyncpg.Pool = None

# 初始化資料庫
async def init_db():

    global poll
    poll = await asyncpg.create_pool(user=os.environ.get('POSTGRES_USER'),
                                password=os.environ.get('POSTGRES_PASSWORD'),
                                database=os.environ.get('POSTGRES_DB'),
                                host=os.environ.get('POSTGRES_HOST'))
    
    async with poll.acquire() as conn:
        # 創建 polls 和 items 表
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS polls (
                poll_id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                channel_id NUMERIC(30) NOT NULL,
                message_id NUMERIC(30) NOT NULL,
                creator_id NUMERIC(30) NOT NULL,
                status TEXT DEFAULT 'Active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS items (
                name TEXT NOT NULL,
                poll_id INTEGER NOT NULL,
                price INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (name, poll_id),
                CONSTRAINT fk_items_polls FOREIGN KEY(poll_id) REFERENCES polls(poll_id) ON DELETE CASCADE ON UPDATE CASCADE
            )
        ''')

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS votes (
                vote_id SERIAL PRIMARY KEY,
                user_id NUMERIC(30) NOT NULL,
                poll_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                need_single BOOLEAN DEFAULT NULL,
                voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_votes_items FOREIGN KEY(name, poll_id) REFERENCES items(name, poll_id) ON DELETE CASCADE ON UPDATE CASCADE
            )
        ''')

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS circles (
                event_name TEXT NOT NULL,
                day INT NOT NULL,
                block TEXT NOT NULL,
                space_no TEXT NOT NULL,
                circle_id TEXT,
                circle_name TEXT,
                author_name TEXT,
                hall TEXT,
                space_cat TEXT,
                social_link TEXT,
                remarks TEXT,
                channel_id NUMERIC(30) UNIQUE,
                PRIMARY KEY (event_name, day, block, space_no)
            )
        ''')

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS circle_status (
                channel_id NUMERIC(30),
                user_id NUMERIC(30),
                status TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_status_circle FOREIGN KEY(channel_id) REFERENCES circles(channel_id) ON DELETE CASCADE ON UPDATE CASCADE
            )
        ''')


# 創建新的投票
async def create_poll(title: str, channel_id: int, message_id: int, creator_id: int, items: list, prices: list):
    async with poll.acquire() as conn:
        poll_id = await conn.fetchval('''
            INSERT INTO polls (title, channel_id, message_id, creator_id)
            VALUES ($1, $2, $3, $4) RETURNING poll_id
        ''', title, channel_id, message_id, creator_id)
        
        await conn.executemany('''
                INSERT INTO items (name, poll_id, price)
                VALUES ($1, $2, $3)
            ''', [(item, poll_id, price) for item, price in zip(items, prices)])

        return poll_id


async def create_vote(user_id: int, poll_id: int, item: str, extra: dict):
    async with poll.acquire() as conn:
        need_single = extra.get("need_single", None) if extra is not None else None
        await conn.execute('''
            INSERT INTO votes (user_id, poll_id, name, need_single)
            VALUES ($1, $2, $3, $4)
        ''', user_id, poll_id, item, need_single)


async def get_not_ended_poll_id_in_channel(channel_id: int):
    async with poll.acquire() as conn:
        res = await conn.fetchval('''
            SELECT poll_id FROM polls WHERE channel_id = $1 AND status != 'Ended'
        ''', channel_id)
        return res


# This returns a list of tuples containing (poll_id, item name, and price)
async def get_poll_with_buttons():
    async with poll.acquire() as conn:
        results = await conn.fetch('''
            SELECT p.poll_id, i.name, i.price
            FROM polls p
            LEFT JOIN items i ON p.poll_id = i.poll_id
            WHERE p.status != 'Deleted'
        ''')
        return results


async def get_poll_title(poll_id: int):
    async with poll.acquire() as conn:
        res = await conn.fetchval('''
            SELECT title FROM polls WHERE poll_id = $1
        ''', poll_id)
        if not res:
            raise ValueError(f"Poll with ID {poll_id} does not exist.")
        return res


# 用戶投票明細
async def get_poll_results_for_users(poll_id: int):
    async with poll.acquire() as conn:
        rows = await conn.fetch('''
            SELECT v.user_id, SUM(i.price) AS total_price
            FROM votes v JOIN items i ON i.name = v.name AND i.poll_id = v.poll_id
            WHERE v.poll_id = $1
            GROUP BY v.user_id
            ORDER BY total_price DESC
        ''', poll_id)
        
        res = []
        for user_id, user_price in rows:
            items = await conn.fetch('''
                SELECT name, COUNT(*) FROM votes
                WHERE user_id = $1 AND poll_id = $2
                GROUP BY name
            ''', user_id, poll_id)

            res.append((user_id, items, user_price))
            
        return res


async def get_poll_results_for_items(poll_id: int):
    async with poll.acquire() as conn:
        res = await conn.fetch('''
            SELECT v.name, COUNT(*), SUM(CASE WHEN need_single THEN 1 ELSE 0 END)
            FROM votes v
            WHERE v.poll_id = $1
            GROUP BY v.name
        ''', poll_id)
        
        return res


async def get_votes_by_poll_and_user(poll_id: int, user_id: int):
    async with poll.acquire() as conn:
        res = await conn.fetch('''
            SELECT v.vote_id, v.name, i.price, v.need_single
            FROM votes v
            JOIN items i ON v.name = i.name AND v.poll_id = i.poll_id
            WHERE v.poll_id = $1 AND v.user_id = $2
        ''', poll_id, user_id)
        
        return res


async def delete_vote(vote_id: int):
    async with poll.acquire() as conn:
        await conn.execute('''
            DELETE FROM votes WHERE vote_id = $1
        ''', vote_id)


async def get_items_by_poll(poll_id: int):
    async with poll.acquire() as conn:
        res = await conn.fetch('''
            SELECT name, price FROM items WHERE poll_id = $1
        ''', poll_id)
        
        return res


async def add_items_to_poll(poll_id: int, items: list):
    async with poll.acquire() as conn:
        await conn.executemany('''
            INSERT INTO items (name, poll_id, price)
            VALUES ($1, $2, $3)
        ''', [(item, poll_id, price) for item, price in items])


async def get_poll_message_id(poll_id: int):
    async with poll.acquire() as conn:
        res = await conn.fetchval('''
            SELECT message_id FROM polls WHERE poll_id = $1
        ''', poll_id)
        
        if not res:
            raise ValueError(f"Poll with ID {poll_id} does not exist.")
        return res
        
    
async def get_poll_channel_id(poll_id: int):
    async with poll.acquire() as conn:
        res = await conn.fetchval('''
            SELECT channel_id FROM polls WHERE poll_id = $1
        ''', poll_id)
        
        if not res:
            raise ValueError(f"Poll with ID {poll_id} does not exist.")
        return res


async def get_my_votes_by_poll_and_user(poll_id: int, user_id: int):
    async with poll.acquire() as conn:
        res = await conn.fetch('''
            SELECT v.name, COUNT(*), SUM(i.price), SUM(CASE WHEN v.need_single THEN 1 ELSE 0 END)
            FROM votes v
            JOIN items i ON v.name = i.name AND v.poll_id = i.poll_id
            WHERE v.poll_id = $1 AND v.user_id = $2
            GROUP BY v.name
        ''', poll_id, user_id)
        
        return res


async def get_poll_creator(poll_id: int):
    async with poll.acquire() as conn:
        res = await conn.fetchval('''
            SELECT creator_id FROM polls WHERE poll_id = $1
        ''', poll_id)
        
        if not res:
            raise ValueError(f"Poll with ID {poll_id} does not exist.")
        return res


async def update_poll_item(poll_id: int, item_name: str, new_name:str, new_price: int):
    async with poll.acquire() as conn:
        await conn.execute('''
            UPDATE items
            SET name = $1, price = $2
            WHERE poll_id = $3 AND name = $4
        ''', new_name, new_price, poll_id, item_name)
        
        # if cursor.rowcount == 0:
        #     raise ValueError(f"Item '{item_name}' in poll {poll_id} does not exist.")
    

async def get_poll_status(poll_id: int):
    async with poll.acquire() as conn:
        res = await conn.fetchval('''
            SELECT status FROM polls WHERE poll_id = $1
        ''', poll_id)
        
        if not res:
            raise ValueError(f"Poll with ID {poll_id} does not exist.")
        return res


async def delete_item_from_poll(poll_id: int, item_name: str):
    async with poll.acquire() as conn:
        await conn.execute('''
            DELETE FROM items WHERE poll_id = $1 AND name = $2
        ''', poll_id, item_name)
        
        # if cursor.rowcount == 0:
        #     raise ValueError(f"Item '{item_name}' in poll {poll_id} does not exist.")
    

async def update_poll_status(poll_id: int, new_status: str):
    async with poll.acquire() as conn:
        await conn.execute('''
            UPDATE polls
            SET status = $1
            WHERE poll_id = $2
        ''', new_status, poll_id)
        
        # if cursor.rowcount == 0:
        #     raise ValueError(f"Poll with ID {poll_id} does not exist.")


async def get_active_polls():
    async with poll.acquire() as conn:
        res = await conn.fetch('''
            SELECT poll_id, title, channel_id, message_id, creator_id FROM polls WHERE status = 'Active'
            ORDER BY poll_id ASC
        ''')
        rtn = [(poll_id, title, int(channel_id), int(message_id), int(creator_id))
            for poll_id, title, channel_id, message_id, creator_id in res]

        return rtn


async def get_paused_polls():
    async with poll.acquire() as conn:
        res = await conn.fetch('''
            SELECT poll_id, title, channel_id, message_id, creator_id FROM polls WHERE status = 'Paused'
            ORDER BY poll_id ASC
        ''')
        rtn = [(poll_id, title, int(channel_id), int(message_id), int(creator_id))
            for poll_id, title, channel_id, message_id, creator_id in res]

        return rtn

async def swap_poll_channel_message(poll_id1: int, poll_id2: int):
    async with poll.acquire() as conn:
        await conn.execute('''
            UPDATE polls
            SET channel_id = (CASE poll_id
                                WHEN $1 THEN (SELECT channel_id FROM polls WHERE poll_id = $2)
                                WHEN $2 THEN (select channel_id FROM polls WHERE poll_id = $1)
                            END)
              , message_id = (CASE poll_id
                                WHEN $1 THEN (SELECT message_id FROM polls WHERE poll_id = $2)
                                WHEN $2 THEN (select message_id FROM polls WHERE poll_id = $1)
                            END)
            WHERE poll_id IN ($1, $2);
        ''', poll_id1, poll_id2)


async def set_delete_poll_by_channel_id(channel_id: int):
    async with poll.acquire() as conn:
        await conn.execute('''
            UPDATE polls
            SET status = 'Deleted'
            WHERE channel_id = $1
        ''', channel_id)
    

async def get_all_votes_by_user(user_id: int, hall: str = None, day: int = None):

    extra_query = ""
    extra_param = tuple()

    if hall is not None:
        extra_query += f" AND c.hall = ${len(extra_param)+3}"
        extra_param += (hall,)

    if day is not None:
        extra_query += f" AND c.day = ${len(extra_param)+3}"
        extra_param += (day,)

    curr_event = os.environ.get("CURR_EVENT")

    async with poll.acquire() as conn:
        res = await conn.fetch(f'''
            SELECT p.poll_id, p.channel_id, i.name, COUNT(*), i.price, SUM(CASE WHEN v.need_single THEN 1 ELSE 0 END)
            FROM votes v
            JOIN items i ON v.name = i.name AND v.poll_id = i.poll_id
            JOIN polls p ON v.poll_id = p.poll_id
            JOIN circles c ON p.channel_id = c.channel_id
            WHERE c.event_name = $1 AND v.user_id = $2 AND p.status != 'Deleted'{extra_query}
            GROUP BY p.poll_id, p.channel_id, i.name, i.price
        ''', *((curr_event, user_id,) + extra_param))
        
        return res


async def get_myorder_export(user_id: int):
    curr_event = os.environ.get("CURR_EVENT")

    async with poll.acquire() as conn:
        res = await conn.fetch('''
            SELECT p.channel_id, c.event_name, c.day, c.hall, c.block, c.space_no, c.circle_name, c.author_name, i.name, i.price, COUNT(*), SUM(CASE WHEN v.need_single THEN 1 ELSE 0 END)
            FROM votes v
            JOIN items i ON v.name = i.name AND v.poll_id = i.poll_id
            JOIN polls p ON v.poll_id = p.poll_id
            LEFT JOIN circles c ON p.channel_id = c.channel_id
            WHERE c.event_name = $1 AND v.user_id = $2 AND p.status != 'Deleted'
            GROUP BY p.poll_id, c.event_name, c.day, c.hall, c.block, c.space_no, c.circle_name, c.author_name, i.name, i.price
        ''', curr_event, user_id)
        
        return res


async def get_all_votes():
    async with poll.acquire() as conn:
        res = await conn.fetch('''
            SELECT p.poll_id, p.title, i.name, COUNT(*), i.price, SUM(CASE WHEN v.need_single THEN 1 ELSE 0 END)
            FROM votes v
            JOIN items i ON v.name = i.name AND v.poll_id = i.poll_id
            JOIN polls p ON v.poll_id = p.poll_id
            GROUP BY p.poll_id, p.title, i.name, i.price
        ''')
        
        return res



# ==============================================================


async def add_circle(circle_data: twitter_utils.CircleForm, channel_id: int):
    async with poll.acquire() as conn:
        await conn.execute('''
            INSERT INTO circles (event_name, day, block, space_no, circle_id, circle_name, author_name, hall, space_cat, social_link, remarks, channel_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        ''',
            os.environ.get("CURR_EVENT"),
            circle_data.day,
            circle_data.row,
            circle_data.booth,
            circle_data.circle_id,
            circle_data.circle_name,
            circle_data.author_name,
            circle_data.hall,
            circle_data.space_cat,
            circle_data.social_link,
            circle_data.remarks,
            channel_id
        )


async def delete_circle_by_channel_id(channel_id: int):
    async with poll.acquire() as conn:
        await conn.execute('''
            DELETE FROM circles WHERE channel_id = $1
        ''', channel_id)


async def get_circle_by_event_day_row_booth(event_name: str, day: int, row: str, booth: str):
    async with poll.acquire() as conn:
        row = await conn.fetchrow('''
            SELECT * FROM circles WHERE event_name = $1 AND day = $2 AND block = $3 AND space_no = $4
        ''', event_name, day, row, booth)

        if row:
            rowDict = row
            res = twitter_utils.CircleForm()
            res.circle_name = rowDict['circle_name']
            res.author_name = rowDict['author_name']
            res.row = rowDict['block']
            res.booth = rowDict['space_no']
            res.circle_id = rowDict['circle_id']
            res.hall = rowDict['hall']
            res.remarks = rowDict['remarks']
            res.day = rowDict['day']
            res.social_link = rowDict['social_link']
            res.space_cat = rowDict['space_cat']
            res.channel_id = int(rowDict['channel_id'])
            
            return res
        
        return None


async def get_circle_by_channel_id(channel_id: int):
    async with poll.acquire() as conn:
        row = await conn.fetchrow('''
            SELECT * FROM circles WHERE channel_id = $1
        ''', channel_id)

        if row:
            rowDict = row
            res = twitter_utils.CircleForm()
            res.circle_name = rowDict['circle_name']
            res.author_name = rowDict['author_name']
            res.row = rowDict['block']
            res.booth = rowDict['space_no']
            res.circle_id = rowDict['circle_id']
            res.hall = rowDict['hall']
            res.remarks = rowDict['remarks']
            res.day = rowDict['day']
            res.social_link = rowDict['social_link']
            res.space_cat = rowDict['space_cat']
            res.channel_id = int(rowDict['channel_id'])
            
            return res
        
        return None


async def update_circle_remarks_by_channel_id(channel_id: int, new_remarks: str):
    async with poll.acquire() as conn:
        await conn.execute('''
            UPDATE circles
            SET remarks = $1
            WHERE channel_id = $2
        ''', new_remarks, channel_id)


async def get_circles_by_day_hall(event_name: str, day: int, hall: str):
    async with poll.acquire() as conn:
        rows = await conn.fetch('''
            SELECT * FROM circles WHERE event_name = $1 AND day = $2 AND hall = $3 ORDER BY block, space_no
        ''', event_name, day, hall)

        res = []
        for row in rows:
            rowDict = row
            circle_data = twitter_utils.CircleForm()
            circle_data.circle_name = rowDict['circle_name']
            circle_data.author_name = rowDict['author_name']
            circle_data.row = rowDict['block']
            circle_data.booth = rowDict['space_no']
            circle_data.circle_id = rowDict['circle_id']
            circle_data.hall = rowDict['hall']
            circle_data.remarks = rowDict['remarks']
            circle_data.day = rowDict['day']
            circle_data.social_link = rowDict['social_link']
            circle_data.space_cat = rowDict['space_cat']
            circle_data.channel_id = int(rowDict['channel_id'])
            
            res.append(circle_data)
        
        return res