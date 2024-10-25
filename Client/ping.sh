#!/bin/bash

# vms file must be provided in same folder - can be fixed as an input
if [ ! -f "modbusvms.txt" ] || [ ! -s "modbusvms.txt" ]; then
	echo "ERROR: File 'modbusvms.txt not found, or file is empty."
	exit 1
fi

# Grab IP addresses from modbusvms.txt file

mapfile -t REMOTE_HOSTS < <(awk '{print $2}' modbusvms.txt)

host="132.72.48.20"
json_file="pings.log"
current_time=$(TZ="GMT-3" date +"%Y-%m-%d %H:%M:%SZ")
ELK_URL="132.72.48.18:9200"
http_certificate="/home/server/Desktop/http_ca.crt"
pings=5

for remote_host in "${REMOTE_HOSTS[@]}"; do
	echo "Start ping $remote_host $pings times:"

	avg=$(ping -c $pings $remote_host | grep 'rtt' | cut -d'/' -f5)
	formatted_avg=$(printf "%.3f" $avg)

	json_obj=$(cat <<EOF
	{
		"host": "$host",
		"remote_host": "$remote_host",
		"total_pings": $pings,
		"average_ms": $formatted_avg,
		"timestamp": "$current_time"
	}
EOF
	)
	echo "$json_obj" >> $json_file
	curl -k --cacert $http_certificate -X 'POST' -u elastic:$ELASTIC_PASSWORD "https://$ELK_URL/pings/_doc?pipeline=add_date" -H 'Content-Type: application/json' -d "$json_obj"
	echo "\n"
done



