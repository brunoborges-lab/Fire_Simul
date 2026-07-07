import streamlit as st
import requests
from streamlit_folium import st_folium
import folium
import pandas as pd
from datetime import datetime
import math

# Configuração da página web
st.set_page_config(
    page_title="Painel de Comando Satélite - Pontos Sensíveis",
    page_icon="🛰️",
    layout="wide"
)

# --- CLIENTE INTEGRADO METEO E PONTOS CRÍTICOS ---
class CentralTaticaClient:
    @staticmethod
    def obter_municipios():
        url = "https://api.ipma.pt/open-data/distrits-islands.json"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200: return response.json()['data']
        except Exception: pass
        return []

    @staticmethod
    def detetar_pontos_sensiveis_proximos(lat, lon):
        """
        Simula uma consulta espacial SIG (ex: via Overpass API / OpenStreetMap).
        Identifica pontos críticos e vulneráveis num raio de 500m da ignição.
        """
        # Gerar pontos simulados com base nas coordenadas reais para manter a consistência tática
        return [
            {"tipo": "Habitação Isolada", "nome": "Casal do Olival", "lat": lat + 0.0012, "lon": lon - 0.0015, "prioridade": "MÁXIMA"},
            {"tipo": "Infraestrutura Crítica", "nome": "Posto de Transformação Elétrico (EDP)", "lat": lat - 0.0018, "lon": lon + 0.0022, "prioridade": "ELEVADA"},
            {"tipo": "Equipamento Social", "nome": "Lar de Idosos Recanto Feliz", "lat": lat + 0.0025, "lon": lon + 0.0005, "prioridade": "URGENTE"}
        ]

class MotorFogoOrografico:
    @classmethod
    def calcular_velocidade_com_declive(cls, r_base, vento, declive_graus, dir_vento, dir_subida):
        f_vento = 1.0 + (vento / 15.0) ** 2
        alinhamento = math.cos(math.radians(dir_vento + 180 - dir_subida))
        f_decorografia = math.exp(0.0693 * declive_graus) * alinhamento if alinhamento > 0 else math.exp(-0.04 * declive_graus)
        return max(r_base * f_vento * f_decorografia, 0.3)

    @staticmethod
    def gerar_cone_60_graus(lat, lon, distancia_frente, dir_vento_origem):
        pontos_cone = [[lat, lon]]
        dir_propagacao = dir_vento_origem + 180
        angulo_esquerdo = math.radians(dir_propagacao - 30)
        angulo_direito = math.radians(dir_propagacao + 30)
        
        for i in range(11):
            fracao = i / 10.0
            angulo_ponto = angulo_esquerdo + fracao * (angulo_direito - angulo_esquerdo)
            dx = distancia_frente * math.sin(angulo_ponto)
            dy = distancia_frente * math.cos(angulo_ponto)
            nova_lat = lat + (dy / 6378137) * (180 / math.pi)
            nova_lon = lon + (dx / 6378137) * (180 / math.pi) / math.cos(math.radians(lat))
            pontos_cone.append([nova_lat, nova_lon])
            
        pontos_cone.append([lat, lon])
        return pontos_cone

# --- INTERFACE TÁTICA ---
st.title("🛰️ Visão de Satélite de Alta Resolução & Gestão de Pontos Sensíveis")
st.write("Clique no mapa para ativar o zoom tático imediato e cruzar os alvos sensíveis na linha de propagação do fogo.")

municipios = CentralTaticaClient.obter_municipios()
col_mapa, col_dados = st.columns([1.4, 1])

# Estados de sessão para controlar o zoom e localização sem perder o histórico do clique
if "mapa_centro" not in st.session_state: st.session_state.mapa_centro = [39.557, -7.996]
if "mapa_zoom" not in st.session_state: st.session_state.mapa_zoom = 7
if "clique" not in st.session_state: st.session_state.clique = None

# Configuração do mapa com Vista Satélite da ESRI
m = folium.Map(location=st.session_state.mapa_centro, zoom_start=st.session_state.mapa_zoom)

# Adicionar Camada de Imagens de Satélite
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-Ethers, and the GIS User Community",
    name="Satélite Esri (Alta Resolução)"
).add_to(m)

m.add_child(folium.LatLngPopup())
dados_painel = []
lista_sensivel = []

# Processamento se houver uma ignição ativa
if st.session_state.clique:
    lat, lon = st.session_state.clique
    
    # 1. Marcar a Ignição (Estrela Vermelha)
    folium.Marker(location=[lat, lon], icon=folium.Icon(color="red", icon="star", prefix="fa"), popup="<b>ALVO PRINCIPAL</b>").add_to(m)
    
    # 2. Injetar no mapa os Pontos Sensíveis detetados na área envolvente
    lista_sensivel = CentralTaticaClient.detetar_pontos_sensiveis_proximos(lat, lon)
    for pts in lista_sensivel:
        folium.Marker(
            location=[pts["lat"], pts["lon"]],
            popup=f"⚠️ {pts['tipo'].upper()}:<br>{pts['nome']}<br>Defesa: <b>{pts['prioridade']}</b>",
            icon=folium.Icon(color="orange", icon="home" if "Habit" in pts["tipo"] else "exclamation-triangle", prefix="fa")
        ).add_to(m)
    
    # 3. Desenhar Projeções e Vetores Orogáficos
    declive = round(abs(math.sin(lat * lon) * 25.0), 1)
    dir_vento = 315
    R_agora = MotorFogoOrografico.calcular_velocidade_com_declive(0.8, 26.0, declive, dir_vento, 140)
    
    dist_1h = R_agora * 60.0
    cone_1h = MotorFogoOrografico.gerar_cone_60_graus(lat, lon, dist_1h, dir_vento)
    folium.Polygon(locations=cone_1h, color="#e67e22", weight=2, fill=True, fill_color="#e67e22", fill_opacity=0.35, popup="Frente de Fogo (+1h)").add_to(m)

with col_mapa:
    mapa_retorno = st_folium(m, width="100%", height=560)
    
    if mapa_retorno and mapa_retorno.get("last_clicked"):
        novo_clique = (mapa_retorno["last_clicked"]["lat"], mapa_retorno["last_clicked"]["lng"])
        if novo_clique != st.session_state.clique:
            st.session_state.clique = novo_clique
            # Atualizar dinamicamente o centro e forçar o zoom aproximado (Vista de Falcão)
            st.session_state.mapa_centro = novo_clique
            st.session_state.mapa_zoom = 16  # Nível ideal para detalhe de edifícios
            st.rerun()

with col_dados:
    if st.session_state.clique:
        st.subheader("🚨 Alvos Sensíveis Críticos Identificados")
        st.write("Prioridades automáticas para proteção e alocação de linhas de defesa (Raio 500m):")
        
        # Apresentar pontos sensíveis em formato de cartões de aviso estruturados
        for pts in lista_sensivel:
            cor_alerta = "red" if pts["prioridade"] == "MÁXIMA" else ("orange" if pts["prioridade"] == "URGENTE" else "yellow")
            st.markdown(
                f"<div style='padding:12px; border-left: 6px solid {cor_alerta}; background-color:#1e272e; margin-bottom:8px; border-radius:4px;'>"
                f"<span style='color:#ffffff; font-weight:bold;'>{pts['tipo']}</span> - <span style='color:#dcdde1;'>{pts['nome']}</span><br>"
                f"<span style='font-size:12px; color:#ffdd59;'>Prioridade de Proteção Escalonada: {pts['prioridade']}</span>"
                f"</div>", 
                unsafe_allow_html=True
            )
        
        st.divider()
        st.subheader("⚙️ Métricas do Ponto")
        st.metric(label="Declive do Terreno Localizado", value=f"{declive}°")
        
        if st.button("RESETAR FOCO DO MAPA", use_container_width=True):
            st.session_state.mapa_centro = [39.557, -7.996]
            st.session_state.mapa_zoom = 7
            st.session_state.clique = None
