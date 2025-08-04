import sqlite3
connection = sqlite3.connect('users.db')
cursor = connection.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS Users (
id INTEGER PRIMARY KEY,
nick TEXT NOT NULL,
age INTEGER,
admin INTEGER,
member INTEGER
)
''')


def new_user(user_id,nick,age) -> None | int:
    cursor.execute('SELECT id FROM Users Where id = ?', (user_id,))
    if not cursor.fetchall():
        cursor.execute('INSERT INTO Users (id,nick,age,admin,member) VALUES (?, ?, ?,0,0)', (user_id, nick, age))
        connection.commit()
        return None
    else:
        return 0

def return_database() -> list:
    cursor.execute('SELECT * FROM Users')
    return cursor.fetchall()

def return_members()-> list:
    cursor.execute('SELECT id,nick FROM Users WHERE member = 1')
    return cursor.fetchall()

def return_requests() -> list:
    cursor.execute('SELECT id,nick,age FROM Users WHERE member = 0')
    return cursor.fetchall()

def return_admins() -> list:
    cursor.execute('SELECT id FROM Users WHERE admin = 1')
    return [i[0] for i in cursor.fetchall()]

def make_admin(user_id) -> None:
    cursor.execute('UPDATE Users SET admin = 1 WHERE id = ? AND member = 1', (user_id,))
    connection.commit()

def is_admin(user_id) -> bool:
    cursor.execute('SELECT admin FROM Users Where id = ?',(user_id,))
    admin : tuple[int] | None = cursor.fetchone()
    if not admin: return False
    return bool(admin[0])

def make_member(user_id) -> None:
    cursor.execute('UPDATE Users SET member = 1 WHERE id = ? AND member = 0', (user_id,))
    connection.commit()

def is_member(user_id) -> bool:
    cursor.execute('SELECT member FROM Users Where id = ?', (user_id,))
    admin: tuple[int] | None = cursor.fetchone()
    if not admin: return False
    return bool(admin[0])

def remove_member(user_id) -> None:
    cursor.execute('DELETE FROM Users WHERE id = ?', (user_id,))
    connection.commit()

def remove_admin(user_id) -> None:
    cursor.execute('UPDATE Users SET admin = 0 WHERE id = ?', (user_id,))
    connection.commit()