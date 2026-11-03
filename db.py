import sqlite3, json

DB = "chef.db"

def init():
    with sqlite3.connect(DB) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS recipes(
            id INTEGER PRIMARY KEY, user_id INTEGER, name TEXT,
            data TEXT, photo BLOB)""")
        c.execute("""CREATE TABLE IF NOT EXISTS prices(
            user_id INTEGER, ingredient TEXT, price_kg REAL,
            PRIMARY KEY(user_id, ingredient))""")

def save_recipe(user_id, recipe, photo=None):
    with sqlite3.connect(DB) as c:
        cur = c.execute("INSERT INTO recipes(user_id,name,data,photo) VALUES(?,?,?,?)",
                        (user_id, recipe["name"], json.dumps(recipe, ensure_ascii=False), photo))
        return cur.lastrowid

def get_recipe(user_id, rid):
    with sqlite3.connect(DB) as c:
        row = c.execute("SELECT data, photo FROM recipes WHERE id=? AND user_id=?",
                        (rid, user_id)).fetchone()
    return (json.loads(row[0]), row[1]) if row else (None, None)

def list_recipes(user_id):
    with sqlite3.connect(DB) as c:
        return c.execute("SELECT id, name FROM recipes WHERE user_id=?", (user_id,)).fetchall()

def set_price(user_id, ing, price):
    with sqlite3.connect(DB) as c:
        c.execute("INSERT OR REPLACE INTO prices VALUES(?,?,?)", (user_id, ing.lower(), price))

def get_prices(user_id):
    with sqlite3.connect(DB) as c:
        return dict(c.execute("SELECT ingredient, price_kg FROM prices WHERE user_id=?", (user_id,)))
