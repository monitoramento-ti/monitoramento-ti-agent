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
VERSAO_ATUAL = "1.0.1"  # Toda vez que mudar o código no GitHub, aumente este número!
# URL do arquivo "raw" (puro texto) no seu GitHub Público
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
INTERVAL = 5 # Envio a cada 5 segundos para resposta rápida

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
            # Se a string da VERSAO_ATUAL no GitHub for diferente da minha, eu atualizo
            if f'VERSAO_ATUAL = "{VERSAO_ATUAL}"' not in novo_codigo:
                print(">>> NOVA VERSÃO DETECTADA! Baixando atualização... <<<")
                
                caminho_arquivo = os.path.abspath(__file__)
                with open(caminho_arquivo, 'w', encoding='utf-8') as f:
                    f.write(novo_codigo)
                
                print("Atualização concluída. Reiniciando agente...")
                time.sleep(2)
                # Comando para o Python se auto-reiniciar
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
    except:
        cpu, ram, ip = 0, 0, "0.0.0.0"

    return {
        "agent_id": AGENT_ID,
        "cliente": CLIENTE,
        "agent_name": AGENT_NAME,
        "ip_local": ip,
        "cpu_percent": cpu,
        "ram_percent": ram,
        "versao": VERSAO_ATUAL,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

print(f"--- MONITOR TI AGENT v{VERSAO_ATUAL} ---")
print(f"Monitorando: {CLIENTE} -> {API_URL}")

contador_check_update = 0

while True:
    # 1. Enviar Heartbeat para o Render
    try:
        payload = coletar_dados()
        r = requests.post(API_URL, json=payload, timeout=5)
        if r.status_code == 200:
            print(f"[OK] Heartbeat enviado v{VERSAO_ATUAL}")
        else:
            print(f"[AVISO] Erro no servidor: {r.status_code}")
    except Exception as e:
        print(f"[FALHA] Servidor inacessível: {e}")

    # 2. Checar atualização a cada 100 envios (aprox. a cada 8-10 minutos)
    contador_check_update += 1
    if contador_check_update >= 100:
        self_update()
        contador_check_update = 0

    time.sleep(INTERVAL)
