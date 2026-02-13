import os
import json
import time
import uuid
import socket
import platform
import requests
import psutil
from datetime import datetime, timezone

# =========================
# Configurações de Caminho
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
AGENT_ID_PATH = os.path.join(BASE_DIR, "agent_id.txt")

# =========================
# Carrega config
# =========================
if not os.path.exists(CONFIG_PATH):
    print(f"[ERRO] config.json não encontrado em {CONFIG_PATH}")
    exit(1)

try:
    with open(CONFIG_PATH, 'r', encoding='latin-1') as f:
        config = json.load(f)
except Exception as e:
    print(f"[ERRO] Falha ao ler config.json: {e}")
    exit(1)

API_URL = config.get("api_url")
CLIENTE = config.get("cliente")
AGENT_NAME = config.get("agent_name", "SERVIDOR")
# Agora ele lê os 10 segundos do seu JSON, ou usa 15 se não encontrar
INTERVAL = int(config.get("interval_seconds", 15)) 

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

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except: return "0.0.0.0"

def coletar_dados():
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    try:
        # Tenta pegar o disco C: no Windows
        uso_disco = psutil.disk_usage('C:\\' if platform.system() == 'Windows' else '/')
        disco_livre_pct = (uso_disco.free / uso_disco.total) * 100
    except: disco_livre_pct = 0

    return {
        "agent_id": AGENT_ID,
        "cliente": CLIENTE,
        "agent_name": AGENT_NAME,
        "hostname": platform.node(),
        "ip_local": get_ip(),
        "cpu_percent": cpu,
        "ram_percent": ram,
        "disk_free_percent": disco_livre_pct,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

print("===================================")
print(" Monitoramento TI - Agent Ativo    ")
print(f" Monitorando: {CLIENTE}            ")
print(f" Intervalo  : {INTERVAL}s          ")
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
