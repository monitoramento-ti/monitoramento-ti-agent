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
# Configurações
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
AGENT_ID_PATH = os.path.join(BASE_DIR, "agent_id.txt")

# Tenta carregar config ou usa padrões
try:
    with open(CONFIG_PATH, 'r', encoding='latin-1') as f:
        config = json.load(f)
except:
    print("ERRO: config.json não encontrado ou inválido.")
    time.sleep(10)
    exit()

API_URL = config.get("api_url")
CLIENTE = config.get("cliente")
AGENT_NAME = config.get("agent_name")
# FORÇAMOS 5 SEGUNDOS PARA SER RÁPIDO
INTERVAL = 5 

# ID Único
if os.path.exists(AGENT_ID_PATH):
    with open(AGENT_ID_PATH, "r") as f:
        AGENT_ID = f.read().strip()
else:
    AGENT_ID = str(uuid.uuid4())
    with open(AGENT_ID_PATH, "w") as f:
        f.write(AGENT_ID)

def coletar():
    try:
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        ip = socket.gethostbyname(socket.gethostname())
    except:
        cpu, ram, ip = 0, 0, "0.0.0.0"

    return {
        "agent_id": AGENT_ID,
        "cliente": CLIENTE,
        "agent_name": AGENT_NAME,
        "ip_local": ip,
        "cpu_percent": cpu,
        "ram_percent": ram,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

print(f"--- AGENTE INICIADO ---")
print(f"Cliente: {CLIENTE}")
print(f"Envio: A cada {INTERVAL} segundos")
print(f"Destino: {API_URL}")

while True:
    try:
        payload = coletar()
        r = requests.post(API_URL, json=payload, timeout=5)
        if r.status_code == 200:
            print(f"[OK] Enviado às {datetime.now().strftime('%H:%M:%S')}")
        else:
            print(f"[ERRO] Servidor retornou código {r.status_code}")
    except requests.exceptions.ConnectionError:
        print("[FALHA] Não foi possível conectar ao servidor (Servidor Offline?)")
    except Exception as e:
        print(f"[ERRO] {e}")
    
    time.sleep(INTERVAL)
