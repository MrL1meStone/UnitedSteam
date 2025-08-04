import sqlite3
connection = sqlite3.connect('users.db')
cursor = connection.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS Members (
id INTEGER PRIMARY KEY,
nick TEXT NOT NULL,
age INTEGER
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS Requests (
id INTEGER PRIMARY KEY,
nick TEXT NOT NULL,
age INTEGER
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS Admins (
id INTEGER PRIMARY KEY,
nick TEXT NOT NULL,
age INTEGER
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS Bans (
id INTEGER PRIMARY KEY,
nick TEXT NOT NULL,
age INTEGER
)
''')


def new_user(user_id,nick,age) -> None | int:
	cursor.execute('INSERT INTO Requests (id,nick,age) VALUES (?, ?, ?)', (user_id, nick, age))
	connection.commit()

def return_from(return_type)-> list:
	cursor.execute(f"SELECT * FROM {return_type}")
	return cursor.fetchall()

def make_admin(user_id) -> None:
	cursor.execute("SELECT id,nick,age FROM Members WHERE id=?",(user_id,))
	user_id,nick,age=cursor.fetchone()
	cursor.execute('INSERT INTO Admins (id,nick,age) VALUES (?, ?, ?)', (user_id,nick,age))
	connection.commit()

def is_admin(user_id) -> bool:
	cursor.execute("SELECT * FROM Admins WHERE id=?",(user_id,))
	return bool(cursor.fetchone())

def make_member(user_id) -> None:
	cursor.execute("SELECT id,nick,age FROM Requests WHERE id=?", (user_id,))
	user_id, nick, age = cursor.fetchone()
	cursor.execute('INSERT INTO Members (id,nick,age) VALUES (?, ?, ?)', (user_id, nick, age))
	cursor.execute('DELETE FROM Requests WHERE id = ?', (user_id,))
	connection.commit()

def is_member(user_id) -> bool:
	cursor.execute('SELECT * FROM Members Where id = ?', (user_id,))
	return bool(cursor.fetchone())

def remove_member(user_id) -> None:
	cursor.execute('DELETE FROM Users WHERE id = ?', (user_id,))
	cursor.execute('DELETE FROM Admins WHERE id = ?', (user_id,))
	cursor.execute('DELETE FROM Requests WHERE id = ?', (user_id,))
	connection.commit()

def remove_admin(user_id) -> None:
	cursor.execute('DELETE FROM Admins WHERE id = ?', (user_id,))
	connection.commit()

def ban(user_id) -> None:
	if not is_member(user_id):
		cursor.execute(f"SELECT nick,age FROM Requests WHERE id=?", (user_id,))
		nick,age=cursor.fetchone()
	else:
		cursor.execute(f"SELECT nick,age FROM Members WHERE id=?", (user_id,))
		nick, age = cursor.fetchone()

	cursor.execute('INSERT INTO Bans (id,nick,age) VALUES (?, ?, ?)', (user_id, nick, age))
	remove_member(user_id)
	connection.commit()

def is_banned(user_id) -> bool:
	cursor.execute(f"SELECT * FROM Bans WHERE id=?", (user_id,))
	return bool(cursor.fetchone())

def unban(user_id) -> None:
	cursor.execute('DELETE FROM Bans WHERE id = ?', (user_id,))
	connection.commit()