import datetime

from database import return_from
time=datetime.datetime.now().time()

def write_log(user_id,text,mode='a'):
	with open(f'logs/{user_id}.log',mode,encoding='utf-8') as log:
		log.write(f'{time.isoformat('seconds')} | {text}\n')

def everyday_logs():
	if time!=time.min:
		return
	for member in return_from('Members'):
		write_log(member['id'],f"Новый лог для {member['id']} ({member['nick']})",mode='w')

def view_logs(user_id):
	with open(f'logs/{user_id}.log','r',encoding='utf-8') as log:
		return log.read()

for member in return_from('Members'):
	write_log(member['id'],f"Новый лог для {member['id']} ({member['nick']})",mode='w')

while True:
	everyday_logs()