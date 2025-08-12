import os
import sqlite3

db_path = os.environ.get("DB_PATH") 
# 檢查環境變數 DB_PATH 是否設置
if os.environ.get("DB_PATH") is None:
    raise ValueError("DB_PATH environment variable is not set.")

print(f"Using database path: {db_path}")
conn = sqlite3.connect(db_path)


# 初始化資料庫
def init_db():
    
    cursor = conn.cursor()

    # 啟用外鍵約束
    cursor.execute('''
        PRAGMA foreign_keys = ON
    ''')

    # 創建 users 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL
        )
    ''')

    # 創建 polls 和 items 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS polls (
            poll_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            message_id TEXT NOT NULL,
            creator_id TEXT NOT NULL,
            status TEXT DEFAULT 'Active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            name TEXT NOT NULL,
            poll_id INTEGER NOT NULL,
            price INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (name, poll_id),
            FOREIGN KEY(poll_id) REFERENCES polls(poll_id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS votes (
            vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            poll_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            need_single BOOLEAN DEFAULT NULL,
            voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(name, poll_id) REFERENCES items(name, poll_id) ON DELETE CASCADE
        )
    ''')

    conn.commit()


def update_username(user_id: str, display_name: str):
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, display_name)
        VALUES (?, ?)
    ''', (user_id, display_name))
    conn.commit()


def get_next_poll_id():
    cursor = conn.cursor()
    cursor.execute("SELECT seq FROM sqlite_sequence WHERE name = 'polls'")
    result = cursor.fetchone()
    return result[0] + 1 if result is not None else 1


# 創建新的投票
def create_poll(title: str, channel_id: int, message_id: int, creator_id: int, items: list, prices: list):
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO polls (title, channel_id, message_id, creator_id)
        VALUES (?, ?, ?, ?)
    ''', (title, channel_id, message_id, creator_id))
    conn.commit()

    poll_id = cursor.lastrowid

    for item, price in zip(items, prices):
        cursor.execute('''
            INSERT INTO items (name, poll_id, price)
            VALUES (?, ?, ?)
        ''', (item, poll_id, price))
    conn.commit()

    return poll_id


def create_vote(user_id: int, poll_id: int, item: str, extra: dict):
    need_single = extra.get("need_single", None) if extra is not None else None
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO votes (user_id, poll_id, name, need_single)
        VALUES (?, ?, ?, ?)
    ''', (user_id, poll_id, item, need_single))
    conn.commit()


# This returns a list of tuples containing (poll_id, item name, and price)
def get_poll_with_buttons():
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.poll_id, i.name, i.price
        FROM polls p
        JOIN items i ON p.poll_id = i.poll_id
    ''')
    results = cursor.fetchall()
    return results


def get_poll_title(poll_id: int):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT title FROM polls WHERE poll_id = ?
    ''', (poll_id,))
    row = cursor.fetchone()
    if row:
        return row[0]
    else:
        raise ValueError(f"Poll with ID {poll_id} does not exist.")


# 用戶投票明細
def get_poll_results_for_users(poll_id: int):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT v.user_id, SUM(i.price) AS total_price
        FROM votes v JOIN items i ON i.name = v.name AND i.poll_id = v.poll_id
        WHERE v.poll_id = ?
        GROUP BY v.user_id
        ORDER BY total_price DESC
    ''', (poll_id,))
    
    row = cursor.fetchall()

    res = []
    for user_id, user_price in row:
        cursor.execute('''
            SELECT display_name FROM users WHERE user_id = ?
        ''', (user_id,))
        display_name = cursor.fetchone()[0]

        cursor.execute('''
            SELECT name, COUNT(*) FROM votes
            WHERE user_id = ? AND poll_id = ?
            GROUP BY name
        ''', (user_id, poll_id))

        items = cursor.fetchall()
        res.append((display_name, items, user_price))
        
    return res


def get_poll_results_for_items(poll_id: int):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT v.name, COUNT(*), SUM(need_single)
        FROM votes v
        WHERE v.poll_id = ?
        GROUP BY v.name
    ''', (poll_id,))
    
    return cursor.fetchall()


def get_votes_by_poll_and_user(poll_id: int, user_id: int):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT v.vote_id, v.name, i.price, v.need_single
        FROM votes v
        JOIN items i ON v.name = i.name AND v.poll_id = i.poll_id
        WHERE v.poll_id = ? AND v.user_id = ?
    ''', (poll_id, user_id))
    
    return cursor.fetchall()


def delete_vote(vote_id: int):
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM votes WHERE vote_id = ?
    ''', (vote_id,))
    conn.commit()


def get_items_by_poll(poll_id: int):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT name, price FROM items WHERE poll_id = ?
    ''', (poll_id,))
    
    return cursor.fetchall()


def add_items_to_poll(poll_id: int, items: list):
    cursor = conn.cursor()
    cursor.executemany('''
        INSERT INTO items (name, poll_id, price)
        VALUES (?, ?, ?)
    ''', [(item, poll_id, price) for item, price in items])
    conn.commit()


def get_poll_message_id(poll_id: int):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT message_id FROM polls WHERE poll_id = ?
    ''', (poll_id,))
    
    row = cursor.fetchone()
    if row:
        return int(row[0])
    else:
        raise ValueError(f"Poll with ID {poll_id} does not exist.")
    

def get_poll_channel_id(poll_id: int):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT channel_id FROM polls WHERE poll_id = ?
    ''', (poll_id,))
    
    row = cursor.fetchone()
    if row:
        return int(row[0])
    else:
        raise ValueError(f"Poll with ID {poll_id} does not exist.")


def get_my_votes_by_poll_and_user(poll_id: int, user_id: int):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT v.name, COUNT(*), SUM(i.price), SUM(v.need_single)
        FROM votes v
        JOIN items i ON v.name = i.name AND v.poll_id = i.poll_id
        WHERE v.poll_id = ? AND v.user_id = ?
        GROUP BY v.name
    ''', (poll_id, user_id))
    
    return cursor.fetchall()


def get_poll_creator(poll_id: int):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT creator_id FROM polls WHERE poll_id = ?
    ''', (poll_id,))
    
    row = cursor.fetchone()
    if row:
        return row[0]
    else:
        raise ValueError(f"Poll with ID {poll_id} does not exist.")


def update_poll_item(poll_id: int, item_name: str, new_name:str, new_price: int):
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE items
        SET name = ?, price = ?
        WHERE poll_id = ? AND name = ?
    ''', (new_name, new_price, poll_id, item_name))
    conn.commit()
    
    if cursor.rowcount == 0:
        raise ValueError(f"Item '{item_name}' in poll {poll_id} does not exist.")
    

def get_poll_status(poll_id: int):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT status FROM polls WHERE poll_id = ?
    ''', (poll_id,))
    
    row = cursor.fetchone()
    if row:
        return row[0]
    else:
        raise ValueError(f"Poll with ID {poll_id} does not exist.")


def delete_item_from_poll(poll_id: int, item_name: str):
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM items WHERE poll_id = ? AND name = ?
    ''', (poll_id, item_name))
    conn.commit()
    
    if cursor.rowcount == 0:
        raise ValueError(f"Item '{item_name}' in poll {poll_id} does not exist.")
    

def update_poll_status(poll_id: int, new_status: str):
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE polls
        SET status = ?
        WHERE poll_id = ?
    ''', (new_status, poll_id))
    conn.commit()
    
    if cursor.rowcount == 0:
        raise ValueError(f"Poll with ID {poll_id} does not exist.")


def get_active_polls():
    cursor = conn.cursor()
    cursor.execute('''
        SELECT poll_id, title, channel_id, message_id, creator_id FROM polls WHERE status = 'Active'
        ORDER BY poll_id ASC
    ''')
    res = cursor.fetchall()
    rtn = [(poll_id, title, int(channel_id), int(message_id), int(creator_id))
           for poll_id, title, channel_id, message_id, creator_id in res]

    return rtn


def get_all_votes_by_user(user_id: int):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.poll_id, p.title, i.name, COUNT(*), i.price, SUM(v.need_single)
        FROM votes v
        JOIN items i ON v.name = i.name AND v.poll_id = i.poll_id
        JOIN polls p ON v.poll_id = p.poll_id
        WHERE v.user_id = ?
        GROUP BY v.poll_id, v.name
    ''', (user_id,))
    
    return cursor.fetchall()


def get_all_votes():
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.poll_id, p.title, i.name, COUNT(*), i.price, SUM(v.need_single)
        FROM votes v
        JOIN items i ON v.name = i.name AND v.poll_id = i.poll_id
        JOIN polls p ON v.poll_id = p.poll_id
        GROUP BY v.poll_id, v.name
    ''')
    
    return cursor.fetchall()