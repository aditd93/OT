import time
import json
from datetime import datetime
import os
import logging
import redis
from elasticsearch import Elasticsearch, helpers
import requests
from urllib3.exceptions import InsecureRequestWarning

# init clients from outside list and remote registers define
file_path='ModbusServers.txt'
WATER_LEVEL_ADDR = 0        # input register address for tank's water level
HIGH_MARK_ADDR = 0          # discrete input and holding register addresses for HIGH mark state and threshold value 
LOW_MARK_ADDR = 1           # discrete input and holding register addresses for LOW mark state and threshold value
WATER_PUMP_ADDR = 0         # Coils address for water tank's pump status

# define log file
logging.basicConfig(level=logging.INFO, filename="/var/log/OT/redis2es.log", filemode="w", format='%(asctime)s - %(levelname)s - %(message)s')

# ignore Insecure warnings
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# define remote redis cluster / container
redis_host = 'eesgi10.ee.bgu.ac.il'
redis_port=6379
redis_index= ['modbusclientsreports', 'databank','packetscapture','servershandler'] # list of the indexes stored on redis - must be lowercases only!

# define elasticsearch remote container
es_host = 'https://eesgi10.ee.bgu.ac.il:9200'
es_username = 'elastic'
es_pass = os.getenv('ELASTIC_PASSWORD')
es_pipeline = 'add_date'

# Establish connections with redis and elasticsearch containerized services
try:
    r = redis.Redis(host=redis_host,port=redis_port,decode_responses=True)
    es = Elasticsearch([es_host], basic_auth=(es_username,es_pass), verify_certs=False)
    logging.info(f"Info: Connection to redis container {redis_host}:{redis_port} has established")
    logging.info(f"Info: Connection to Elasticsearch container {es.info()} has established")
except redis.ConnectionError as e:
    logging.error(f"Error: Redis connection has failed: {e}")
    exit(1)

def fetch_logs(index):
    # fetch logs from redis-index to new index for processing, and append docs to local list
    docs = []
    index_process = index+'process'
    while True:
        # each doc transfered to new index for processing and pop out of index's list
        doc = r.brpoplpush(index,index_process, timeout=0.5)
        if not doc:
            break
        docs.append(doc)
    return docs


def post_to_es(docs,index):
    # load each doc to actions
    actions = [
        {
            "_index": index,
            "_source": json.loads(doc),
            "pipeline": es_pipeline
        }
        for doc in docs
    ]
    try:
        helpers.bulk(es, actions) # use bulk API to post data to elasticsearch DB
        print(f"Posted {len(docs)} to index: {index} in Elasticsearch")
        logging.info(f"Info: Posted {len(docs)} new docs to {index} :Elasticsearch")
        # remove docs from processing index
        for doc in docs:
            r.lrem(index+'process',1,doc)
    except Exception as e:
        print(f"Error: posting logs failed: {e}")
        logging.error(f"Error: posting docs failed: {e}")


def main():
    while True:
        for index in redis_index:
            docs = fetch_logs(index)
            if not docs:
                print(f"no new docs for index: {index}")
                logging.info(f"Info: no new docs for index: {index}")
            else:
                post_to_es(docs, index)
            time.sleep(5)



if __name__ == "__main__":
   main()





