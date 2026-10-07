"""Start the image over stdio as an MCP client would and call list_states.

Usage: python3 .github/scripts/check_image.py IMAGE
"""

import json
import subprocess
import sys

server = subprocess.Popen(
    ["docker", "run", "-i", "--rm", "--network", "none", "--read-only", "--tmpfs", "/tmp", sys.argv[1]],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
)

def send(message):
    server.stdin.write(json.dumps({"jsonrpc": "2.0", **message}) + "\n")
    server.stdin.flush()

def reply(id):
    for line in server.stdout:
        message = json.loads(line)
        if message.get("id") == id:
            return message["result"]
    raise SystemExit("server exited without replying")

send({"id": 1, "method": "initialize", "params": {
    "protocolVersion": "2025-11-25", "capabilities": {},
    "clientInfo": {"name": "image-check", "version": "0"}}})
assert reply(1)["serverInfo"]["name"] == "sdo-forecast"
send({"method": "notifications/initialized"})
send({"id": 2, "method": "tools/call", "params": {"name": "list_states", "arguments": {}}})
result = reply(2)["structuredContent"]
server.stdin.close()
server.wait(timeout=30)
assert len(result["states"]) == 50, sorted(result["states"])
print(f"{len(result['states'])} states, database release {result['database_release']}")
