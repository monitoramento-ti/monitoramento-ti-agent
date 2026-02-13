import os, json, time, uuid, socket, platform, requests, psutil
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
AGENT_ID_PATH = os.path.join(BASE_DIR, "agent_id.txt")

# Carrega config
with open(CONFIG_PATH, 'r', encoding='latin-1') as f:
    config = json.load(f)

API_URL = config.get("api_url")
CLIENTE = config.get("cliente")
AGENT_NAME = config.get("agent_name")
INTERVAL = int(config.get("interval_seconds", 10))

# Gerencia ID único
if os.path.exists(AGENT_ID_PATH):
    with open(AGENT_ID_PATH, "r") as f: AGENT_ID = f.read().strip()
else:
    AGENT_ID = str(uuid.uuid4())
    with open(AGENT_ID_PATH, "w") as f: f.write(AGENT_ID)

def coletar():
    return {
        "agent_id": AGENT_ID,
        "cliente": CLIENTE,
        "agent_name": AGENT_NAME,
        "ip_local": socket.gethostbyname(socket.gethostname()),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "ram_percent": psutil.virtual_memory().percent,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

print(f"Monitorando: {CLIENTE}... Envio a cada {INTERVAL}s.")

while True:
    try:
        r = requests.post(API_URL, json=coletar(), timeout=10)
        print(f"[OK] {datetime.now().strftime('%H:%M:%S')}")
    except Exception as e:
        print(f"[ERRO] {e}")
    time.sleep(INTERVAL)
