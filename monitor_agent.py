import os
import json
import time
import uuid
import socket
import requests
import psutil
import sys
import subprocess
import re
from datetime import datetime, timezone

# ==========================================
# CONFIGURAÇÃO DE VERSÃO E ATUALIZAÇÃO
# ==========================================
VERSAO_ATUAL = "1.0.5"
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

# Migração automática: atualiza do Render para Railway
NOVA_URL = "https://monitoramento-ti-production.up.railway.app/heartbeat"
HEARTBEAT_TOKEN = "451d2982863105670a02cc82d8e03be71d3c12ffac2a456414aef294d11085ba"
if API_URL and "onrender.com" in API_URL:
    print(">>> Migrando URL do Render para Railway automaticamente...")
    config["api_url"] = NOVA_URL
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    API_URL = NOVA_URL
    print(f">>> URL atualizada para: {API_URL}")

INTERVAL = 15  # 15s reduz carga no servidor mantendo deteccao de queda em ~30s

# Garante o ID único do computador
if os.path.exists(AGENT_ID_PATH):
    with open(AGENT_ID_PATH, "r") as f: AGENT_ID = f.read().strip()
else:
    AGENT_ID = str(uuid.uuid4())
    with open(AGENT_ID_PATH, "w") as f: f.write(AGENT_ID)

# ==========================================
# IPs DE BACKBONE A MONITORAR
# ==========================================
PROVIDER_IPS = [
    "189.113.112.87",   # Gateway Borda LCI (Sorriso)
    "189.113.112.10",   # Core Roteamento LCI (MT)
    "200.189.223.133",  # Saída Cirion LCI (Nacional)
    "200.244.67.62",    # Core Embratel (Cuiabá-MT)
    "200.244.67.60",    # Core Redundância Embratel (Cuiabá-MT)
    "200.244.211.72",   # Agregador Dedicado Claro (MT)
    "200.244.67.68",    # Borda Claro Varejo (Sorriso/Sinop)
]

def medir_latencia(ip: str) -> float:
    """
    Mede latência via ping nativo do Windows (ping -n 1).
    Retorna latência em ms ou -1.0 se timeout/inacessível.
    """
    try:
        resultado = subprocess.run(
            ["ping", "-n", "1", "-w", "2000", ip],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW  # não abre janela no Windows
        )
        output = resultado.stdout

        # Extrai ms do output: "Tempo=12ms" ou "time=12ms" ou "tempo=12ms"
        match = re.search(r"[Tt]empo[=<](\d+)ms|[Tt]ime[=<](\d+)ms", output)
        if match and resultado.returncode == 0:
            ms = match.group(1) or match.group(2)
            return float(ms)
        return -1.0
    except Exception:
        return -1.0

def medir_latencias_provedores() -> dict:
    """Mede latência de todos os IPs de backbone e retorna dict {ip: ms}."""
    resultados = {}
    for ip in PROVIDER_IPS:
        latencia = medir_latencia(ip)
        resultados[ip] = latencia
        status = f"{latencia}ms" if latencia >= 0 else "TIMEOUT"
        print(f"  [{status}] {ip}")
    return resultados

def self_update():
    """Verifica se há uma nova versão no GitHub e se auto-atualiza."""
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Checando atualizações no GitHub...")
        response = requests.get(URL_GITHUB_RAW, timeout=15)

        if response.status_code == 200:
            novo_codigo = response.text
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

def coletar_dados() -> dict:
    try:
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        ip = socket.gethostbyname(socket.gethostname())
        disco = psutil.disk_usage('C:\\' if os.name == 'nt' else '/')
        disk_p = disco.percent
        disk_f = round(disco.free / (1024**3), 1)
    except:
        cpu, ram, ip, disk_p, disk_f = 0, 0, "0.0.0.0", 0, 0

    return {
        "agent_id": AGENT_ID,
        "cliente": CLIENTE,
        "agent_name": AGENT_NAME,
        "ip_local": ip,
        "cpu_percent": cpu,
        "ram_percent": ram,
        "disk_percent": disk_p,
        "disk_free": disk_f,
        "versao": VERSAO_ATUAL,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "token": HEARTBEAT_TOKEN
    }

# ==========================================
# LOOP PRINCIPAL
# ==========================================
print(f"--- MONITOR TI AGENT v{VERSAO_ATUAL} ---")
print(f"Monitorando: {CLIENTE}")

contador_check_update = 0
contador_provider_ping = 0  # mede providers a cada 6 ciclos (30s)
latencias_providers = {}    # cache das últimas latências medidas

while True:
    try:
        # Mede backbone a cada 30s (6 ciclos de 5s)
        contador_provider_ping += 1
        if contador_provider_ping >= 2 or not latencias_providers:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Medindo backbone...")
            latencias_providers = medir_latencias_provedores()
            contador_provider_ping = 0

        payload = coletar_dados()
        payload["provider_latencies"] = latencias_providers

        r = requests.post(API_URL, json=payload, timeout=5)
        if r.status_code == 200:
            print(f"[OK] v{VERSAO_ATUAL} | CPU: {payload['cpu_percent']}% | HD: {payload['disk_percent']}%")
        else:
            print(f"[AVISO] Erro no servidor: {r.status_code}")
    except Exception as e:
        print(f"[FALHA] Servidor inacessível: {e}")

    contador_check_update += 1
    if contador_check_update >= 100:
        self_update()
        contador_check_update = 0

    time.sleep(INTERVAL)
