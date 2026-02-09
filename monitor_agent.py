import requests
import json
import time
import os
import socket
import psutil
import subprocess
from datetime import datetime, UTC

# ===============================
# PATHS
# ===============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
CACHE_DIR = os.path.join(BASE_DIR, "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "offline.json")

os.makedirs(CACHE_DIR, exist_ok=True)

# ===============================
# LOAD CONFIG
# ===============================
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

API_URL = config["api_url"]
INTERVAL = int(config.get("interval_seconds", 60))

CLIENTE = config.get("cliente", "SEM_CLIENTE")

# 👉 IDENTIDADE ÚNICA DO SERVIDOR
HOSTNAME = socket.gethostname().upper()
AGENT_NAME = HOSTNAME

# ===============================
# UTIL
# ===============================
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def get_ip_local():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "0.0.0.0"

# ===============================
# COLETA
# ===============================
def coletar_status():
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent

    try:
        disco = psutil.disk_usage("C:")
        disk_free = round(100 - disco.percent, 2)
    except:
        disk_free = 0

    return {
        "cliente": CLIENTE,
        "agent_name": AGENT_NAME,
        "hostname": HOSTNAME,
        "ip_local": get_ip_local(),
        "cpu_percent": cpu,
        "ram_percent": ram,
        "disk_free_percent": disk_free,
        "timestamp": datetime.now(UTC).isoformat()
    }

# ===============================
# CACHE OFFLINE
# ===============================
def salvar_cache(dados):
    cache = []

    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except:
            cache = []

    cache.append(dados)

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

def enviar_cache():
    if not os.path.exists(CACHE_FILE):
        return

    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        cache = json.load(f)

    if not cache:
        return

    log(f"📤 Enviando cache offline ({len(cache)})")

    enviados = 0
    for item in cache:
        try:
            r = requests.post(API_URL, json=item, timeout=5)
            if r.status_code == 200:
                enviados += 1
            else:
                break
        except:
            break

    if enviados == len(cache):
        os.remove(CACHE_FILE)
        log("🧹 Cache offline limpo")

# ===============================
# LOOP PRINCIPAL
# ===============================
def main():
    log("🚀 Monitor Agent iniciado")
    log(f"🏢 Cliente: {CLIENTE}")
    log(f"🖥️ Hostname: {HOSTNAME}")
    log(f"⏱️ Intervalo: {INTERVAL}s")
    log(f"🌐 API: {API_URL}")

    while True:
        try:
            dados = coletar_status()

            try:
                r = requests.post(API_URL, json=dados, timeout=5)

                if r.status_code == 200:
                    log("✅ Heartbeat enviado")
                    enviar_cache()
                else:
                    log(f"⚠️ API {r.status_code} — salvando cache")
                    salvar_cache(dados)

            except:
                log("❌ API indisponível — salvando cache")
                salvar_cache(dados)

        except Exception as e:
            log(f"❌ Erro interno: {e}")

        time.sleep(INTERVAL)

# ===============================
# ENTRYPOINT
# ===============================
if __name__ == "__main__":
    main()
