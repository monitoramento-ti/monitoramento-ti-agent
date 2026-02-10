import os
import json
import time
import uuid
import socket
import platform
import requests
import psutil
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
AGENT_ID_PATH = os.path.join(BASE_DIR, "agent_id.txt")

# =========================
# Carrega config
# =========================
if not os.path.exists(CONFIG_PATH):
    print("[ERRO] config.json não encontrado")
    exit(1)

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

API_URL = config.get("api_url")
CLIENTE = config.get("cliente")
AGENT_NAME = config.get("agent_name", "SERVIDOR")
INTERVAL = int(config.get("interval_seconds", 60))
EMAIL = config.get("email_alerta")

if not API_URL or not CLIENTE:
    print("[ERRO] config.json incompleto")
    exit(1)

# =========================
# Gera / carrega ID único
# =========================
if os.path.exists(AGENT_ID_PATH):
    with open(AGENT_ID_PATH, "r") as f:
        AGENT_ID = f.read().strip()
else:
    AGENT_ID = str(uuid.uuid4())
    with open(AGENT_ID_PATH, "w") as f:
        f.write(AGENT_ID)

# =========================
# Funções
# =========================
def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "0.0.0.0"

def coletar_dados():
    return {
        "agent_id": AGENT_ID,
        "cliente": CLIENTE,
        "agent_name": AGENT_NAME,
        "hostname": platform.node(),
        "ip_local": get_ip(),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "ram_percent": psutil.virtual_memory().percent,
        "disk_free_percent": psutil.disk_usage("/").free / psutil.disk_usage("/").total * 100,
        "email_alerta": EMAIL,
        "timestamp": datetime.utcnow().isoformat()
    }

# =========================
# Loop principal
# =========================
print("===================================")
print(" Monitoramento TI - Agent Iniciado ")
print("===================================")
print(f"Cliente  : {CLIENTE}")
print(f"Servidor : {AGENT_NAME}")
print(f"Agent ID : {AGENT_ID}")
print(f"Endpoint : {API_URL}")
print("===================================")

while True:
    try:
        payload = coletar_dados()
        r = requests.post(API_URL, json=payload, timeout=10)

        if r.status_code == 200:
            print(f"[OK] Heartbeat enviado - {datetime.now().strftime('%H:%M:%S')}")
        else:
            print(f"[ERRO] HTTP {r.status_code}")

    except Exception as e:
        print(f"[FALHA] {e}")

    time.sleep(INTERVAL)
