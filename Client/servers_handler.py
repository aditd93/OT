import psutil
import json
import time
import datetime
import requests
import logging
import redis

# define info and error logs for post requests
logging.basicConfig(level=logging.INFO, filename="/var/log/OT/servers_handler.log", filemode="w", format='%(asctime)s - %(levelname)s - %(message)s')

# define remote redis cluster / container
redis_host = 'eesgi10.ee.bgu.ac.il'
redis_port=6379
redis_index='servershandler'
try:
    r = redis.Redis(host=redis_host,port=redis_port,decode_responses=True)
    logging.info(f"Info: Connection to redis container {redis_host}:{redis_port} has established")
except redis.ConnectionError as e:
    logging.error(f"Error: Redis connection has failed: {e}")
    exit(1)

def monitor(prev):
	current = set()
	for conn in psutil.net_connections():
		if conn.status=='ESTABLISHED' and conn.raddr.port==502:
			current.add((conn.raddr.ip, conn.laddr.port))
	new_servers = current - prev
	to_remove_servers = prev - current
	current_details=[{"IP": ip, "Port": port} for ip, port in current]
	current_servers_json = {
		"message_type": "repetetive_check",
		"servers_count": len(current),
		"servers_details": current_details,
		"timestamp": datetime.datetime.now().isoformat()
	}
	print(json.dumps(current_servers_json)) # debug
	if(len(new_servers)):
		new_servers_add(new_servers)
	if(len(to_remove_servers)):
		old_servers_removal(to_remove_servers)
	post_to_redis(current_servers_json)
	return list(current)

def new_servers_add(new):
	new_details=[{"IP": ip, "Port": port} for ip, port in new]
	new_servers_json = {
		"message_type": "new_servers_added",
		"servers_count_diff": len(new),
		"servers_details_diff": new_details,
		"timestamp": datetime.datetime.now().isoformat()
	}
	logging.info(f"Info: New servers:{new_details} are connected")
	post_to_redis(new_servers_json)


def old_servers_removal(old):
	old_details=[{"IP": ip, "Port": port} for ip, port in old]
	old_servers_json = {
		"message_type": "server_disconnected",
		"servers_count_diff": len(old),
		"servers_details_diff": old_details,
		"timestamp": datetime.datetime.now().isoformat()
	}
	logging.info(f"Info: Servers:{old_details} have disconnected")
	post_to_redis(old_servers_json)

def post_to_redis(payload):
	try:
		r.lpush(redis_index,json.dumps(payload))
		logging.info(f"INFO: Posted to redis: {redis_host}:{redis_port} to index:{redis_index} is complete")
	except Exception as e:
		logging.error(f"Error: Post to redis: {redis_host}:{redis_port} to index: {redis_index} failed")


def main():
	current_servers = set()
	for conn in psutil.net_connections():
		if conn.status == 'ESTABLISHED' and conn.raddr.port==502:
			current_servers.add((conn.raddr.ip, conn.laddr.port))
	while True:
		time.sleep(10)
		update = monitor(current_servers)
		current_servers.clear()
		current_servers.update(update)


if __name__ == "__main__":
	main()
