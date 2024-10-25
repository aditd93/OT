import os
import pyshark
import yara
import json
import argparse
import redis
import logging

rule1_path='/home/kali/Desktop/OT/Kali/YARA/rules/read_coils.yar'
rule2_path='/home/kali/Desktop/OT/Kali/YARA/rules/write_single_coil.yar'
rules = yara.compile(filepaths={
    'namespace1': rule1_path,
    'namespace2': rule2_path
    })

# define log file
logging.basicConfig(level=logging.INFO, filename="/var/log/OT/raw_packet_capture.log", filemode="w", format='%(asctime)s - %(levelname)s - %(message)s')

# define remote redis cluster / container
redis_host = 'eesgi10.ee.bgu.ac.il'
redis_port=6379
redis_index='packetscapture'
try:
    r = redis.Redis(host=redis_host,port=redis_port,decode_responses=True)
    logging.info(f"Info: Connection to redis container {redis_host}:{redis_port} has established")
except redis.ConnectionError as e:
    logging.error(f"Error: Redis connection has failed: {e}")
   

def capture_packets(interface, bpf_filter,port):
    capture = pyshark.LiveCapture(interface=interface,bpf_filter=bpf_filter, decode_as={f'tcp.port=={port}': 'mbtcp'},use_json=True,include_raw=True)
    print(f"Start capturing packets on interface {interface}, press CTRL+C to stop.")
    try:
        capture.apply_on_packets(packet_callback)
    except:
        print("\nCapture stopped.")
    finally:
        capture.close()


def packet_callback(packet):
    try:
        if packet['MBTCP']:
            packet_bytes = packet.get_raw_packet()
            match = rules.match(data=packet_bytes)
            if match:
                # print(match)
                packet_report(packet,match)
        else:
            print("Packet isn't Modbus type")

    except Exception as e:
        pass

def packet_report(packet,match):
    timestamp = packet.sniff_time.isoformat()
    packet_info = {
        "timestamp": timestamp,
        "src_ip": f'{packet.ip.src}',
        "src_port": f'{packet.tcp.srcport}',
        "dst_ip": f'{packet.ip.dst}',
        "dst_port": f'{packet.tcp.dstport}',
        "matching_rule": f'{match}'
     }
    post_to_redis(packet_info)
    

def post_to_redis(payload):
     try:
        r.lpush(redis_index,json.dumps(payload))
        logging.info(f"Info: Post to: {redis_index} in redis complete")
     except Exception as e:
          logging.error(f"Error: {e}")

def main():
    parser = argparse.ArgumentParser(description="Adi")
    parser.add_argument('--port',type=int,default=502)
    args = parser.parse_args()
    interface = 'eth1'
    bpf_filter = f'tcp port {args.port}'
    capture_packets(interface,bpf_filter,args.port)

if __name__ == '__main__':
    main()




