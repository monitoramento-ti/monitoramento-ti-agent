import os
import json
import time
import uuid
import socket
import requests
import psutil
import sys
from datetime import datetime, timezone

# ==========================================
# CONFIGURAÇÃO DE VERSÃO E ATUALIZAÇÃO
# ==========================================
VERSAO_ATUAL = "1.0.2"  # Aumentei para 1.0.2 para disparar o update
URL_GITHUB_RAW = "https://raw.githubusercontent.com/monitoramento-ti/monitoramento-ti-agent/main/monitor_agent.py"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
AGENT_ID_PATH = os.path.join(BASE_DIR, "agent_id.txt")

# Carrega configurações locais
try:
    with open(CONFIG_PATH, 'r', encoding='latin-1') as f:
        config = json.load(f)
except Exception as e:
    print(f"ERRO: config.json não encontrado ou inválido: {e}")
    time.sleep(10)
    sys.exit()

API_URL = config.get("api_url")
CLIENTE = config.get("cliente")
AGENT_NAME = config.get("agent_name")
INTERVAL = 5 

# Garante o ID único do computador
if os.path.exists(AGENT_ID_PATH):
    with open(AGENT_ID_PATH, "r") as f: AGENT_ID = f.read().strip()
else:
    AGENT_ID = str(uuid.uuid4())
    with open(AGENT_ID_PATH, "w") as f: f.write(AGENT_ID)

def self_update():
    """Verifica se há uma nova versão no GitHub e se auto-atualiza"""
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Checando atualizações no GitHub...")
        response = requests.get(URL_GITHUB_RAW, timeout=15)
        
        if response.status_code == 200:
            novo_codigo = response.text
            # Se a versão no GitHub for diferente da atual, atualiza
            if f'VERSAO_ATUAL = "{VERSAO_ATUAL}"' not in novo_codigo:
                print(">>> NOVA VERSÃO DETECTADA! Baixando atualização... <<<")
                
                caminho_arquivo = os.path.abspath(__file__)
                with open(caminho_arquivo, 'w', encoding='utf-8') as f:
                    f.write(novo_codigo)
                
                print("Atualização concluída. Reiniciando agente...")
                time.sleep(2)
                os.execv(sys.executable, ['python'] + sys.argv)
            else:
                print("Agente já está na versão mais recente.")
        else:
            print(f"Falha ao checar update. Status: {response.status_code}")
    except Exception as e:
        print(f"Erro durante o auto-update: {e}")

def coletar_dados():
    try:
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        ip = socket.gethostbyname(socket.gethostname())
        
        # --- NOVA PARTE: COLETA DE DISCO ---
        disco = psutil.disk_usage('C:\\' if os.name == 'nt' else '/')
        disk_p = disco.percent
        disk_f = round(disco.free / (1024**3), 1) # GB livres
        # ----------------------------------
        
    except:
        cpu, ram, ip, disk_p, disk_f = 0, 0, "0.0.0.0", 0, 0

    return {
        "agent_id": AGENT_ID,
        "cliente": CLIENTE,
        "agent_name": AGENT_NAME,
        "ip_local": ip,
        "cpu_percent": cpu,
        "ram_percent": ram,
        "disk_percent": disk_p, # NOVO
        "disk_free": disk_f,    # NOVO
        "versao": VERSAO_ATUAL,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

print(f"--- MONITOR TI AGENT v{VERSAO_ATUAL} ---")
print(f"Monitorando: {CLIENTE}")

contador_check_update = 0

while True:
    try:
        payload = coletar_dados()
        r = requests.post(API_URL, json=payload, timeout=5)
        if r.status_code == 200:
            print(f"[OK] Heartbeat v{VERSAO_ATUAL} | CPU: {payload['cpu_percent']}% | HD: {payload['disk_percent']}%")
        else:
            print(f"[AVISO] Erro no servidor: {r.status_code}")
    except Exception as e:
        print(f"[FALHA] Servidor inacessível: {e}")

    contador_check_update += 1
    if contador_check_update >= 100:
        self_update()
        contador_check_update = 0

    time.sleep(INTERVAL)
