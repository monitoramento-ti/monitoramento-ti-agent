import requests
import json
import time
import os
import socket
import psutil
import subprocess
from datetime import datetime, UTC
import smtplib
from email.mime.text import MIMEText

# ===============================
# PATHS
# ===============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
CACHE_DIR = os.path.join(BASE_DIR, "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "offline.json")
STATE_FILE = os.path.join(CACHE_DIR, "state.json")

os.makedirs(CACHE_DIR, exist_ok=True)

# ===============================
# LOAD CONFIG
# ===============================
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

API_URL = config["api_url"]
INTERVAL = int(config.get("interval_seconds", 60))

CLIENTE = config.get("cliente", "SEM_CLIENTE")
AGENT_NAME = config.get("agent_name", socket.gethostname())

EMAIL_ALERTA = config.get("email_alerta")
ALERTA_OFFLINE = config.get("alertar_offline", False)
ALERTA_ONLINE = config.get("alertar_online", False)

# ===============================
# EMAIL CONFIG (GMAIL)
# ===============================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_REMETENTE = "alissonbrunoom@gmail.com"
EMAIL_SENHA = "SUA_SENHA_DE_APP_AQUI"

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

def ping(host):
    if not host:
        return None
    try:
        result = subprocess.run(
            ["ping", "-n", "1", host],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3
        )
        return result.returncode == 0
    except:
        return False

# ===============================
# EMAIL
# ===============================
def enviar_email(assunto, mensagem):
    if not EMAIL_ALERTA:
        return

    try:
        msg = MIMEText(mensagem)
        msg["From"] = EMAIL_REMETENTE
        msg["To"] = EMAIL_ALERTA
        msg["Subject"] = assunto

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_REMETENTE, EMAIL_SENHA)
        server.send_message(msg)
        server.quit()

        log(f"📧 Email enviado: {assunto}")
    except Exception as e:
        log(f"❌ Erro ao enviar email: {e}")

# ===============================
# ESTADO ONLINE / OFFLINE
# ===============================
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"online": True}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

# ===============================
# COLETA
# ===============================
def coletar_status():
    ram = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=1)

    try:
        disco = psutil.disk_usage("C:")
        disk_free = round(100 - disco.percent, 2)
    except:
        disk_free = None

    return {
        "cliente": CLIENTE,
        "agent_name": AGENT_NAME,
        "hostname": socket.gethostname(),
        "ip_local": get_ip_local(),
        "cpu_percent": cpu,
        "ram_percent": ram.percent,
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
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
        except:
            cache = []

    cache.append(dados)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

def enviar_cache():
    if not os.path.exists(CACHE_FILE):
        return

    with open(CACHE_FILE, "r") as f:
        cache = json.load(f)

    enviados = 0
    for item in cache:
        try:
            r = requests.post(API_URL, json=item, timeout=5)
            if r.status_code == 200:
                enviados += 1
        except:
            break

    if enviados == len(cache):
        os.remove(CACHE_FILE)
        log("🧹 Cache offline enviado")

# ===============================
# LOOP PRINCIPAL
# ===============================
def main():
    log("🚀 Monitor Agent iniciado")

    state = load_state()

    while True:
        dados = coletar_status()

        try:
            r = requests.post(API_URL, json=dados, timeout=5)

            if r.status_code == 200:
                if not state.get("online"):
                    if ALERTA_ONLINE:
                        enviar_email(
                            f"🟢 ONLINE - {AGENT_NAME}",
                            f"O servidor {AGENT_NAME} voltou a ficar ONLINE."
                        )
                    state["online"] = True
                    save_state(state)

                enviar_cache()
                log("✅ Heartbeat enviado")

            else:
                raise Exception("API erro")

        except:
            if state.get("online"):
                if ALERTA_OFFLINE:
                    enviar_email(
                        f"🔴 OFFLINE - {AGENT_NAME}",
                        f"O servidor {AGENT_NAME} ficou OFFLINE."
                    )
                state["online"] = False
                save_state(state)

            salvar_cache(dados)
            log("❌ API offline")

        time.sleep(INTERVAL)

# ===============================
# ENTRYPOINT
# ===============================
if __name__ == "__main__":
    main()
