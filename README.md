# OT network client project
## Repository from client role in a modbus-TCP based networks.

### ModbusClient.py
running Modbus client application, connects multiple servers running a modbus servers over TCP <br>
servers applications running a PLC connected to water tank system, detailed in a link attached to this repo. <br>

### servers_handler.py
running a servers monitoring for TCP connections over Modbus port. <br>
also, posts logs to elasticksearch DB on a remote container. <br>

### ping.sh
bash script that pings modbus clients/servers to determine average RTTs. <br>

### 
