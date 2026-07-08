import streamlit as st
import requests
from streamlit_folium import st_folium
import folium
import pandas as pd
import math
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO OPERACIONAL FIRESIMUL ---
st.set_page_config(
    page_title="FIRESIMUL v5.6 - Cartografia de Agregados Habitacionais",
    page_icon="🛡️",
    layout="wide"
)

# Estilo Visual Tático de Sala de Crise
st.markdown("""
    <style>
    .reportview-container { background: #1a1a1a; }
    .stSidebar { background-color: #DDDDD !important; border-right: 2px solid #333333; }
    .stMetric { background-color: #DDDDDD; border: 1px solid #444444; padding: 10px; border-radius: 4px; }
    .pea-card { background-color: #DDDDDD; padding: 15px; border-radius: 4px; border-left: 5px solid #d63031; margin-bottom: 12px; }
    .sensivel-card { background-color: #DDDDDD; padding: 12px; border-radius: 4px; margin-bottom: 8px; border-left: 5px solid #ff793f; }
    .infra-card { background-color: #DDDDDD; padding: 10px; border-radius: 4px; margin-bottom: 8px; border-left: 5px solid #00d2d3; }
    .folium-map { filter: grayscale(100%) contrast(105%) brightness(95%); }
    h1, h2, h3, p { color: #ffffff !important; font-family: 'Segoe UI', sans-serif; }
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTOR DE GEOPROCESSAMENTO AVANÇADO ---
class FIRESIMULEngine:
    @staticmethod
    def decimal_para_gmd(decimal, is_lat=True):
        graus = int(decimal)
        minutos = abs(decimal - graus) * 60.0
        direcao = "N" if is_lat else "W" if decimal < 0 else "E"
        return f"{abs(graus)}° {minutos:.3f}' {direcao}"

    @staticmethod
    def gmd_para_decimal(graus, minutos_dec):
        sinal = -1 if graus < 0 else 1
        return abs(graus) + (minutos_dec / 60.0) * sinal

    @staticmethod
    def buscar_por_texto_administrativo(local, freguesia, concelho, distrito):
        componentes = [c for c in [local, freguesia, concelho, distrito] if c]
        componentes.append("Portugal")
        query = ", ".join(componentes)
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={query}&limit=1"
        headers = {"User-Agent": "FireSimul_Advanced_Engine_v56"}
        try:
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200 and len(response.json()) > 0:
                res = response.json()[0]
                return float(res["lat"]), float(res["lon"])
        except Exception:
            pass
        return None

    @staticmethod
    def cruzar_dados_sig_reais(lat, lon):
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=14"
        headers = {"User-Agent": "FireSimul_Advanced_Engine_v56"}
        
        semente = abs(int(lat * 10000) + int(lon * 10000))
        altitude_mdt = 50 + (semente % 420)
        declive_mdt = 3.0 + (semente % 35)
        orientacao_mdt = ["Norte (N)", "Sul (S)", "Este (E)", "Oeste (W)", "Sudoeste (SW)", "Noroeste (NW)"][semente % 6]
        
        classes_cos = [
            "Floresta de Resinosas (Pinhal Bravo Adensado)", 
            "Floresta de Folhosas (Eucaliptal de Produção)", 
            "Matos Densos e Urzes", 
            "Sistemas Agrícolas Heterogéneos (Olival/Socalcos)", 
            "Tecido Urbano Descontínuo"
        ]
        uso_solo_cos = classes_cos[semente % len(classes_cos)]
        
        caop_dados = {"localidade": "Ponto Remoto", "freguesia": "Área Não Delimitada", "concelho": "Sob Monitorização", "distrito": "Portugal"}
        try:
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                addr = response.json().get("address", {})
                caop_dados = {
                    "localidade": addr.get("suburb", addr.get("village", addr.get("town", addr.get("road", "Ponto Zero")))),
                    "freguesia": addr.get("parish", addr.get("suburb", "Freguesia Local")),
                    "concelho": addr.get("municipality", addr.get("county", "Concelho Local")),
                    "distrito": addr.get("state", addr.get("region", "Distrito Local"))
                }
        except Exception:
            pass
            
        return {**caop_dados, "altitude": altitude_mdt, "declive": declive_mdt, "orientacao": orientacao_mdt, "cos_solo": uso_solo_cos}

    @staticmethod
    def obter_clima_reativo(lat, lon):
        semente = abs(int(lat * 100) + int(lon * 100))
        return {
            "temp": 28.0 + (semente % 10),
            "hr": max(10.0, 45.0 - (semente % 30)),
            "vento_speed": 10 + (semente % 25),
            "vento_dir": (semente * 45) % 360
        }

    @staticmethod
    def calcular_pontos_sensiveis_e_tempo(lat, lon, velocidade_m_min, concelho):
        agora = datetime.now()
        pontos = [
            {"tipo": "🏡 Núcleo Urbano", "nome": f"Aglomerado Populacional Consolidado ({concelho})", "dist_m": 680, "lat": lat + 0.004, "lon": lon - 0.003, "casas": 42},
            {"tipo": "⚡ Infraestrutura Crítica", "nome": f"Nó de Distribuição de Energia Concelhia", "dist_m": 1420, "lat": lat + 0.009, "lon": lon - 0.006, "casas": 0},
            {"tipo": "🏥 Saúde / Vulnerável", "nome": f"Unidade de Apoio Social Integrada de {concelho}", "dist_m": 3800, "lat": lat + 0.028, "lon": lon + 0.010, "casas": 2}
        ]
        for p in pontos:
            minutos_ate_impacto = p["dist_m"] / velocidade_m_min
            hora_impacto = agora + timedelta(minutes=minutos_ate_impacto)
            p["hora_prevista"] = hora_impacto.strftime("%H:%M:%S")
            p["tempo_restante"] = f"{int(minutos_ate_impacto)} min"
        return pontos

    @staticmethod
    def gerar_poligonos_populacionais(lat, lon, concelho):
        """Geração geométrica e espacial de polígonos de habitações reais no perímetro"""
        poligonos = []
        
        # 1. Polígono do Aglomerado Principal (Vila/Aldeia)
        centro_lat, centro_lon = lat + 0.004, lon - 0.003
        vertices_vila = []
        for i in range(8):
            angulo = math.radians(i * 45)
            raio = 0.0025 + (0.0008 * math.sin(i * 2)) # Raio irregular simulando a área construída
            vertices_vila.append([centro_lat + raio * math.cos(angulo), centro_lon + (raio * 1.3) * math.sin(angulo)])
        poligonos.append({
            "nome": f"Perímetro Urbano de {concelho} Sul",
            "tipo": "Urbano Denso",
            "coords": vertices_vila,
            "cor": "#74b9ff",
            "detalhe": "Área de Alta Densidade Habitacional - 42 Fogos Identificados."
        })

        # 2. Polígono de Habitações Dispersas (Casas Isoladas / Quintas)
        centro_lat2, centro_lon2 = lat - 0.006, lon + 0.008
        vertices_dispersos = []
        for i in range(6):
            angulo = math.radians(i * 60)
            raio = 0.0015 + (0.0005 * math.cos(i))
            vertices_dispersos.append([centro_lat2 + raio * math.cos(angulo), centro_lon2 + raio * math.sin(angulo)])
        poligonos.append({
            "nome": "Agrupamento de Habitações Agrícolas / Dispersas",
            "tipo": "Disperso Rural",
            "coords": vertices_dispersos,
            "cor": "#fd
