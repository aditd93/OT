from pyModbusTCP.server import ModbusServer, DataBank
import random
import time
from datetime import datetime
import logging
import redis
import json
import sys

# Server host and port prameters
host='192.168.56.104'
port=502
redis_host = 'eesgi10.ee.bgu.ac.il'
redis_port=6379
redis_index = 'databank'

# define log file 
logging.basicConfig(level=logging.INFO, filename="/var/log/OT-server/water_tank.log", filemode="w", format='%(asctime)s - %(levelname)s - %(message)s')

# Server define coils, discrete inputs and registers
WATER_PUMP_ADDR = 0         # coil address for water pump state 
WATER_LEVEL_ADDR = 0        # input register address for water level
WATER_MAX_ADDR = 1          # input register address stores the maximum water level ever reached
WATER_MIN_ADDR = 2          # input register address stores the minimum water level ever reached
HIGH_MARK_ADDR = 0          # discrete input address for high water mark sensor
LOW_MARK_ADDR = 1           # discrete input address for low water mark sensor
HIGH_LEVEL_THRESHOLD = 17   # hold register value for water tank overflow 17/20
LOW_LEVEL_THRESHOLD = 3     # hold register value for water tank near-empty tank 3/20
OPTIMAL_LEVEL = 10          # retore water tank level value when exceeding threshold
MAX_CAPACITY = 20           # Water tank full capacity
MIN_CAPACITY = 0            # Water tank is empty

def server_init(host,port):
    # initialize server's coils, input and registers to water tank
    serv_DB = DataBank(coils_size=2,d_inputs_size=2,h_regs_size=2,i_regs_size=3)
    serv_DB.set_input_registers(WATER_LEVEL_ADDR, [OPTIMAL_LEVEL,OPTIMAL_LEVEL,OPTIMAL_LEVEL])  # starting point is 10 cm
    serv_DB.set_holding_registers(HIGH_MARK_ADDR, [HIGH_LEVEL_THRESHOLD])
    serv_DB.set_holding_registers(LOW_MARK_ADDR, [LOW_LEVEL_THRESHOLD])
    server = ModbusServer(host=host,port=port,no_block=True,data_bank=serv_DB)
    return (serv_DB, server)

def update_water_tank(serv_DB):
    rand_shift = random.choice([0,1]) # randomly increase / decrease water tank by on level
    current_water_level = serv_DB.get_input_registers(WATER_LEVEL_ADDR,1)[0]
    if serv_DB.get_coils(WATER_PUMP_ADDR,1)[0] == 1: # pump is on
        serv_DB.set_input_registers(WATER_LEVEL_ADDR, [min(current_water_level+rand_shift,MAX_CAPACITY)])
    else: # pump is off
        serv_DB.set_input_registers(WATER_LEVEL_ADDR, [max(current_water_level-rand_shift,MIN_CAPACITY)])
        
def run_server(serv_DB):
    # sensors and registers are according to instrumentationblog.com/tank-water-level-measurement
    current_water_level = serv_DB.get_input_registers(WATER_LEVEL_ADDR,1)[0]
    match current_water_level:
        case current_water_level if MIN_CAPACITY <= current_water_level <=LOW_LEVEL_THRESHOLD:
            serv_DB.set_discrete_inputs(HIGH_MARK_ADDR,[False,False])
        case current_water_level if LOW_LEVEL_THRESHOLD < current_water_level < HIGH_LEVEL_THRESHOLD:
            serv_DB.set_discrete_inputs(HIGH_MARK_ADDR,[False,True])
        case current_water_level if HIGH_LEVEL_THRESHOLD <= current_water_level <= MAX_CAPACITY:
            serv_DB.set_discrete_inputs(HIGH_MARK_ADDR,[True,True])
        # If current level is out of range, inform
        case _:
            # print(f"current water level is Out of Range: {current_water_level}") # debug
            logging.error(f"Error: current water level is Out of Range {current_water_level}")

def update_h_regs(serv_DB,water_pump_state):
    current_water_level = serv_DB.get_input_registers(WATER_LEVEL_ADDR,1)[0]
    current_water_pump_state = serv_DB.get_coils(WATER_PUMP_ADDR,1)[0]
    match current_water_level:
        case current_water_level if current_water_level > serv_DB.get_input_registers(WATER_MAX_ADDR,1)[0]:
            serv_DB.set_input_registers(WATER_MAX_ADDR,[current_water_level])
            logging.info(f"Info: Maximum water level updated to {current_water_level}")
        case current_water_level if current_water_level < serv_DB.get_input_registers(WATER_MIN_ADDR,1)[0]:
            serv_DB.set_input_registers(WATER_MIN_ADDR,[current_water_level])
            logging.info(f"Info: Minimum water level updated to {current_water_level}")
        case _:
            pass # both holding registers remian the same
    if current_water_pump_state != water_pump_state:
        # print(f"Water pump state has changed from {water_pump_state} to {current_water_pump_state}") # debug
        logging.info(f"Info: Water pump state changed from: {water_pump_state} to {current_water_pump_state}")

def post_to_redis(serv_DB):
    current_state = serv_DB.get_input_registers(0,3)
    water_pump_status = serv_DB.get_coils(WATER_PUMP_ADDR,1)[0]
    thresholds = serv_DB.get_discrete_inputs(0,2)
    high, low = thresholds
    curr_tank,max_tank,min_tank = current_state
    data = {    
        'timestamp': datetime.now().isoformat(),
        'Server_IP': host,
        'Water_level': curr_tank,
        'High_threshold_sensor': high,
        'Low_threshold_sensor': low,
        'Water_pump_status': water_pump_status,
        'Water_tank_MAX': max_tank,
        'Water_tank_MIN': min_tank
    }
    try:
        r.lpush(redis_index,json.dumps(data))
        logging.info(f"Info: posted water tank update to redis container")
    except redis.PubSubError as e:
        logging.info(f"Error: {e}")


def print_tank_status(serv_DB):
    current_state = serv_DB.get_input_registers(0,3)
    water_pump_status = serv_DB.get_coils(WATER_PUMP_ADDR,1)[0]
    thresholds = serv_DB.get_discrete_inputs(0,2)
    high, low = thresholds
    curr_tank,max_tank,min_tank = current_state
    status_message = (
        f"| Water Tank Status: \n"
        f"| Water tank current level: {curr_tank} cm \n"
        f"| Water pump status is : {water_pump_status} \n"
        f"| Water level exceeded High Threshold: {high} \n"
        f"| Water level exceeded Low Threshold: {low}  \n"
        f"| Water tank MAX: {max_tank} \n"
        f"| Water tank MIN: {min_tank} \n"
        f"=============================================\n"
    )
    sys.stdout.write("\033[9F")
    sys.stdout.write("\033[J")
    print(status_message)


# Modbus Server object 
serv_DB, server = server_init(host,port)
try:
    r = redis.Redis(host=redis_host,port=redis_port,decode_responses=True) # connect to redis remote container
    logging.info(f"Info: Connection to redis container {redis_host}:{redis_port} established")
except redis.ConnectionError as e:
    logging.error(f"Error: failed to connect to Redis container {redis_host}:{redis_port}, fail: {e}")
    exit(1)

server.start()
water_pump_state = False
print(f"server start\n"
      f"Server's IP: {host}\n"
      f"Server's Port: {port}\n")
print("=============================================\n")
print("\n" *7)

try:
    while True:
        update_water_tank(serv_DB)
        run_server(serv_DB)
        update_h_regs(serv_DB,water_pump_state)
        post_to_redis(serv_DB)
        print_tank_status(serv_DB)
        water_pump_state = serv_DB.get_coils(WATER_PUMP_ADDR,1)[0]
        time.sleep(1)
except KeyboardInterrupt:
    print("Server is stopping...")
    server.stop()
    print("Server stopped")


