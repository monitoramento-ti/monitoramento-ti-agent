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
VERSAO_ATUAL = "1.0.6"
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

# Chave pública RSA para verificação de assinatura
CHAVE_PUBLICA_PEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEArJbH3tzaa1HaeFKW6NYw
FJEZ/6SNpdC0w9muAPKeIYN5Z3qp5zftbEw6Y96NvwR1FovOVqI6WPwMXfCMHl2r
JGERBDHn9rozNehRj3/SM/I3Y5V1U3q1ufp5nbTnjr1fB6o1tnRvf/Fy7ayn+6n3
ZfrHtUNhM4rXsVLDl3TC4TW7sxLvskBqY5+wzWs4IvPLBA4JnDxFgz3tSD9jmxVC
EpbWU/LW7MK0+ehWJWlTMjhVKRLUmo6xKWnmecTL9EJAw04HHchUXvLqgkFidRdC
Z0oPlEsH4MEEdoMpiAK27IySa4ju8m0yUQMQ2i0BEhNANvGboznwh/aQ3KjB5lLQ
DwIDAQAB
-----END PUBLIC KEY-----"""

URL_GITHUB_SIG = "https://raw.githubusercontent.com/monitoramento-ti/monitoramento-ti-agent/main/monitor_agent.sig"

def verificar_assinatura(codigo_bytes: bytes, assinatura_bytes: bytes) -> bool:
    """Verifica se o código foi assinado pela chave privada da Yalla."""
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.exceptions import InvalidSignature

        chave_publica = serialization.load_pem_public_key(CHAVE_PUBLICA_PEM)
        chave_publica.verify(
            assinatura_bytes,
            codigo_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except InvalidSignature:
        return False
    except Exception as e:
        print(f"Erro ao verificar assinatura: {e}")
        return False

def self_update():
    """Verifica se há uma nova versão no GitHub, valida assinatura e auto-atualiza."""
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Checando atualizações no GitHub...")
        response = requests.get(URL_GITHUB_RAW, timeout=15)

        if response.status_code != 200:
            print(f"Falha ao checar update. Status: {response.status_code}")
            return

        novo_codigo = response.text

        if f'VERSAO_ATUAL = "{VERSAO_ATUAL}"' in novo_codigo:
            print("Agente já está na versão mais recente.")
            return

        print(">>> NOVA VERSÃO DETECTADA! Verificando assinatura... <<<")

        # Baixa a assinatura
        sig_response = requests.get(URL_GITHUB_SIG, timeout=15)
        if sig_response.status_code != 200:
            print("❌ ATUALIZAÇÃO REJEITADA: arquivo de assinatura não encontrado!")
            return

        # Verifica assinatura
        codigo_bytes = novo_codigo.encode('utf-8')
        assinatura_bytes = sig_response.content

        if not verificar_assinatura(codigo_bytes, assinatura_bytes):
            print("❌ ATUALIZAÇÃO REJEITADA: assinatura inválida! Possível código malicioso.")
            return

        print("✅ Assinatura válida! Instalando atualização...")
        caminho_arquivo = os.path.abspath(__file__)
        with open(caminho_arquivo, 'w', encoding='utf-8') as f:
            f.write(novo_codigo)

        print("Atualização concluída. Reiniciando agente...")
        time.sleep(2)
        os.execv(sys.executable, ['python'] + sys.argv)

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
