#!/usr/bin/env python3
import json
import sys

# Path to the workflow JSON
workflow_path = "/home/june/trading/workflows/n8n/daily_trading_workflow_v1.import.json"

with open(workflow_path, 'r', encoding='utf-8') as f:
    workflow = json.load(f)

# Find the highest position x and y to avoid overlap? We'll just append at the end.
# But we need to assign unique ids.

# Determine next available ID numbers for cron and exec.
existing_ids = set(node['id'] for node in workflow['nodes'])
def next_id(prefix):
    i = 1
    while f"{prefix}{i}" in existing_ids:
        i += 1
    return f"{prefix}{i}"

# We'll add a cron that runs every 30 minutes from 9:00 to 15:00 on weekdays.
# In n8n cron node, we can set triggerTimes to multiple items.
# However, easier: create multiple cron nodes? Or use a single cron with multiple times.
# We'll create a single cron node with multiple triggerTimes for each half hour.

# Generate triggerTimes for 9:00, 9:30, 10:00, ..., 15:00 (interval 30 minutes)
trigger_times = []
for hour in range(9, 16):  # 9 to 15 inclusive
    for minute in (0, 30):
        trigger_times.append({"hour": hour, "minute": minute})

cron_id = next_id("cron-")
exec_id = next_id("exec-")

# Add cron node
cron_node = {
    "parameters": {
        "triggerTimes": {
            "item": trigger_times
        }
    },
    "id": cron_id,
    "name": "Profit exit monitor (every 30m)",
    "type": "n8n-nodes-base.cron",
    "typeVersion": 1,
    "position": [
        -620,  # x position, we can adjust
        1000   # y position, we'll place it lower
    ]
}

# Add exec node
exec_node = {
    "parameters": {
        "command": "cd /home/june/trading && python3 monitor_profit_exit.py"
    },
    "id": exec_id,
    "name": "Run profit exit monitor",
    "type": "n8n-nodes-base.executeCommand",
    "typeVersion": 1,
    "position": [
        -360,
        1000
    ]
}

workflow['nodes'].append(cron_node)
workflow['nodes'].append(exec_node)

# Write back
with open(workflow_path, 'w', encoding='utf-8') as f:
    json.dump(workflow, f, indent=2, ensure_ascii=False)

print(f"Updated workflow: added {cron_id} and {exec_id}")