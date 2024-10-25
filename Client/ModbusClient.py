from pyModbusTCP.client import ModbusClient
import time
import threading
import json
from datetime import datetime
import logging
import redis
from elasticsearch import Elasticsearch, helpers

# init clients from outside list and remote registers define
file_path='ModbusServers.txt'
WATER_LEVEL_ADDR = 0        # input register address for tank's water level
HIGH_MARK_ADDR = 0          # discrete input and holding register addresses for HIGH mark state and threshold value 
LOW_MARK_ADDR = 1           # discrete input and holding register addresses for LOW mark state and threshold value
WATER_PUMP_ADDR = 0         # Coils address for water tank's pump status

# define log file
logging.basicConfig(level=logging.INFO, filename="/var/log/OT/ModbusClient.log", filemode="w", format='%(asctime)s - %(levelname)s - %(message)s')

# define remote redis cluster / container
redis_host = 'eesgi10.ee.bgu.ac.il'
redis_port=6379
redis_index='modbusclientsreports'
try:
    r = redis.Redis(host=redis_host,port=redis_port,decode_responses=True)
    logging.info(f"Info: Connection to redis container {redis_host}:{redis_port} has established")
except redis.ConnectionError as e:
    logging.error(f"Error: Redis connection has failed: {e}")
    exit(1)

class Session(threading.Thread):
    def __init__(self,server_ip,server_port,unit_id):
        super().__init__()
        self.server_ip = server_ip
        self.server_port = server_port
        self.unit_id = unit_id
        self.client = ModbusClient(host=server_ip,port=server_port,unit_id=unit_id)
    
    def connect(self):
        while not self.client.is_open:
            if not self.client.open():
                print(f"    Failed to open session with server: {self.server_ip}, ID: {self.unit_id}")
                logging.warning(f"Warning: Failed to open session with server: {self.server_ip}, ID: {self.unit_id} ")
                print(f"try again connecting server: {self.server_ip}, ID: {self.unit_id} in 5 seconds...")
                time.sleep(5)
            else:
                print(f"    Connected to server: {self.server_ip}, ID: {self.unit_id}")
                logging.info(f"Info: connected to server: {self.server_ip}, ID: {self.unit_id}")

    def post_to_redis(self, water_level, high_mark_state, low_mark_state,pump_state):
        # post to redis whenever a water pump status changes
        data = {
            'timestamp': datetime.now().isoformat(),
            'Server_IP': self.server_ip,
            'Server_port': self.server_port,
            'Unit_id': self.unit_id,
            'Water_level': water_level,
            'High_threshold_sensor': high_mark_state,
            'Low_threshold_sensor': low_mark_state,
            'Water_pump_status': pump_state
        }
        try:
            r.lpush(redis_index,json.dumps(data))
            logging.info(f"Info: Post to redis complete")
        except redis.PubSubError as e:
            logging.error(f"Error: {e}")



    def run(self):
        self.connect()
        while True:
            try:
                if self.client.is_open:
                    # Read Water level
                    water_level = self.client.read_input_registers(WATER_LEVEL_ADDR,1)[0]
                    if water_level>=0:
                        print(f"IP: {self.server_ip}, ID: {self.unit_id} Current water level is: {water_level}")
                        high_mark_state = self.client.read_discrete_inputs(HIGH_MARK_ADDR,1)[0]
                        low_mark_state = self.client.read_discrete_inputs(LOW_MARK_ADDR,1)[0]
                        pump_state = self.client.read_coils(WATER_PUMP_ADDR,1)[0]
                        # turn on/off water pump according to water level sensors
                        match (high_mark_state, low_mark_state, pump_state):
                            # turn on pump
                            case (high_mark_state, low_mark_state, pump_state) if not low_mark_state and not high_mark_state:
                                if pump_state == False:
                                    self.client.write_single_coil(WATER_PUMP_ADDR,True)
                                    print(f"Turn IP: {self.server_ip}, ID: {self.unit_id} water pump ON")
                                    logging.info(f"Info: Turn IP: {self.server_ip}, ID: {self.unit_id} water pump ON")
                                    self.post_to_redis(water_level,high_mark_state,low_mark_state,pump_state)
                            # turn off pump
                            case (high_mark_state, low_mark_state, pump_state) if high_mark_state and low_mark_state:
                                if pump_state == True:
                                    self.client.write_single_coil(WATER_PUMP_ADDR,False)
                                    print(f"Turn IP: {self.server_ip}, ID: {self.unit_id} water pump OFF")
                                    logging.info(f"Info: Turn IP: {self.server_ip}, ID: {self.unit_id} water pump OFF")
                                    self.post_to_redis(water_level,high_mark_state,low_mark_state,pump_state)

                    else:
                        print("Can't read water level input register from server")
                        logging.error(f"Error: Can't read server's IP: {self.server_ip}, ID: {self.unit_id} water level")
                    time.sleep(1)
                else:
                    self.connect() # try to reconnect server
            except Exception as e:
                logging.error(f"Error: {e}")
                self.connect()

def start_modbus_client(file_path):
    servers_list = []
    f = open(file_path,"r")
    for line in f:
        parts = line.split()
        if len(parts) == 3:
            servers_list.append((parts[1],int(parts[2]))) # append (ip_address, unit_id)
    print(servers_list)
    sessions = [Session(ip,502,unit_id) for (ip,unit_id) in servers_list]
    for session in sessions:
        session.start()

    for session in sessions:
        session.join()

if __name__ == "__main__":
    start_modbus_client(file_path)





