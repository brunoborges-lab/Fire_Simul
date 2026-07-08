import streamlit as st
import requests
from streamlit_folium import st_folium
import folium
import pandas as pd
from datetime import datetime
import math

# --- CONFIGURAÇÃO DA INTERFACE ---
st.set_page_config(
    page_title="FEB Monitorização - Despacho de Ocorrências",
    page_icon="🚒",
    layout="wide"
)

# Estilo Dark Mode Tático FEB
st.markdown("""
    <style>
    .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 12px; border-radius: 6px; }
    .status-card { padding: 12px; border-radius: 6px; margin-bottom: 8px; border: 1px solid #30363d; background-color: #161b22; }
    h3 { margin-top: 20px !important; color: #ffdd59 !important; }
    </style>
""", unsafe_allow_html=True)

# --- CLIENTES DE DADOS & GEOPROCESSAMENTO ---
class FEBEngine:
    @staticmethod
    def obter_municipios():
        url = "https://api.ipma.pt/open-data/distrits-islands.json"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200: return response.json()['data']
        except Exception: pass
        return []

    @staticmethod
    def arome_clima(lat, lon):
        # Fallback de telemetria meteorológica estável para a simulação
        return {"temp": "33.5 °C", "humidade": "21 %", "vento": "29 km/h", "dir_vento": "315° (NW)", "fwi_copernicus": "Extremo"}

    @staticmethod
    def converter_gmd_para_decimal(graus, minutos_dec):
        """Converte Graus Minutos Decimais para Graus Decimais (Padrão SIG)"""
        sinal = -1 if graus < 0 else 1
        return graus + (minutos_dec / 60.0) * sinal

    @staticmethod
    def geocode_texto(localidade, freguesia, concelho, distrito):
        """Simula a resolução de texto para coordenadas via API de Geocodificação"""
        # Coordenadas base de referência em Portugal Continental dependendo do input
        if concelho:
            # Hash determinístico simples para simular coordenadas diferentes por concelho
            hash_val = sum(ord(c) for c in concelho) % 100
            return 37.0 + (hash_val * 0.05), -9.0 + (hash_val * 0.04)
        return 39.557, -7.996

    @staticmethod
    def gerar_cone_60(lat, lon, distancia_m, dir_vento=315):
        pontos = [[lat, lon]]
        dir_propagacao = dir_vento + 180
        ang_esq = math.radians(dir_propagacao - 30)
        ang_dir = math.radians(dir_propagacao + 30)
        for i in range(11):
            f = i / 10.0
            ang = ang_esq + f * (ang_dir - ang_esq)
            fator_flanco = 1.0 - 0.6 * abs(f - 0.5) * 2
            dx = (distancia_m * fator_flanco) * math.sin(ang)
            dy = (distancia_m * fator_flanco) * math.cos(ang)
            n_lat = lat + (dy / 6378137) * (180 / math.pi)
            n_lon = lon + (dx / 6378137) * (180 / math.pi) / math.cos(math.radians(lat))
            pontos.append([n_lat, n_lon])
        pontos.append([lat, lon])
        return pontos

# --- INICIALIZAÇÃO DE ESTADOS DE SESSÃO ---
if "lat" not in st.session_state: st.session_state.lat = 39.557
if "lon" not in st.session_state: st.session_state.lon = -7.996
if "zoom" not in st.session_state: st.session_state.zoom = 7
if "trigger_render" not in st.session_state: st.session_state.trigger_render = False

# --- LAYOUT PRINCIPAL DO PAINEL FEB ---
st.title("🔥 FEB Monitorização — Módulo de Despacho e Geolocalização")
st.markdown("---")

# Barra Superior: Opções de preenchimento da localização
tipo_entrada = st.radio(
    "MÉTODO DE ENTRADA DA LOCALIZAÇÃO DA IGNITION:",
    ["Seleção Direta no Mapa", "Coordenadas Graus Minutos.Decimais (GMD)", "Endereço / Texto CNEPC"],
    horizontal=True
)

col_esquerda, col_direita = st.columns([1.1, 1.3])

with col_esquerda:
    # Painéis condicionais de input de dados baseado na escolha do operador
    if tipo_entrada == "Coordenadas Graus Minutos.Decimais (GMD)":
        st.subheader("📍 Coordenadas de Rádio (GMD)")
        c1, c2 = st.columns(2)
        with c1:
            lat_g = st.number_input("Latitude (Graus):", value=39, step=1)
            lat_m = st.number_input("Latitude (Minutos.Dec):", value=31.380, format="%.3f")
        with c2:
            lon_g = st.number_input("Longitude (Graus):", value=-7, step=1)
            lon_m = st.number_input("Longitude (Minutos.Dec):", value=57.720, format="%.3f")
        
        if st.button("PROCESSAR COORDENADAS GMD", use_container_width=True):
            st.session_state.lat = FEBEngine.converter_gmd_para_decimal(lat_g, lat_m)
            st.session_state.lon = FEBEngine.converter_gmd_para_decimal(lon_g, lon_m)
            st.session_state.zoom = 15
            st.session_state.trigger_render = True
            st.rerun()

    elif tipo_entrada == "Endereço / Texto CNEPC":
        st.subheader("📝 Via Hierarquia Geográfica")
        t1, t2 = st.columns(2)
        with t1:
            distrito = st.text_input("Distrito:", value="Santarém")
            concelho = st.text_input("Concelho:", value="Mação")
        with t2:
            freguesia = st.text_input("Freguesia:", value="Carvoeiro")
            localidade = st.text_input("Local/Ponto de Referência:", value="Cruzamento do Vale")
            
        if st.button("GEOCODIFICAR LOCALIZAÇÃO", use_container_width=True):
            st.session_state.lat, st.session_state.lon = FEBEngine.geocode_texto(localidade, freguesia, concelho, distrito)
            st.session_state.zoom = 15
            st.session_state.trigger_render = True
            st.rerun()
            
    else:
        st.info("ℹ️ Módulo de clique ativo. Localize o foco de incêndio no mapa à direita e clique na zona para extração automática.")

    # Renderização da Tabela de Situação Solicitada
    st.subheader("📋 Tabela Integrada de Situação Operacional")
    clima = FEBEngine.arome_clima(st.session_state.lat, st.session_state.lon)
    
    dados_situacao = {
        "Parâmetro Operacional": [
            "Coordenadas Decimais", 
            "Temperatura (AROME)", 
            "Humidade Relativa", 
            "Velocidade do Vento", 
            "Rumo do Vento", 
            "Severidade Copernicus"
        ],
        "Valor em Tempo Real": [
            f"{st.session_state.lat:.5f} , {st.session_state.lon:.5f}",
            clima["temp"],
            clima["humidade"],
            clima["vento"],
            clima["dir_vento"],
            clima["fwi_copernicus"]
        ]
    }
    st.dataframe(pd.DataFrame(dados_situacao), use_container_width=True, hide_index=True)

# --- MAPA TÁTICO ---
with col_direita:
    m = folium.Map(location=[st.session_state.mapa_centro[0] if 'mapa_centro' in st.session_state else st.session_state.lat, 
                             st.session_state.mapa_centro[1] if 'mapa_centro' in st.session_state else st.session_state.lon], 
                   zoom_start=st.session_state.zoom)
    
    # Camada Satélite Esri
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri", name="Satélite Monitorização"
    ).add_to(m)
    
    # Marcador e Cone baseados no estado atual da localização
    folium.Marker(
        location=[st.session_state.lat, st.session_state.lon],
        icon=folium.Icon(color="red", icon="crosshairs", prefix="fa"),
        popup="<b>PONTO ZERO (IGNIÇÃO)</b>"
    ).add_to(m)
    
    cone_poligono = FEBEngine.gerar_cone_60(st.session_state.lat, st.session_state.lon, 600)
    folium.Polygon(locations=cone_poligono, color="#e53e3e", weight=2, fill=True, fill_opacity=0.3, popup="Projeção Frente").add_to(m)

    mapa_retorno = st_folium(m, width="100%", height=550)
    
    # Captura de clique caso o operador prefira a seleção manual
    if tipo_entrada == "Seleção Direta no Mapa" and mapa_retorno and mapa_retorno.get("last_clicked"):
        novo_clique = (mapa_retorno["last_clicked"]["lat"], mapa_retorno["last_clicked"]["lng"])
        if novo_clique != (st.session_state.lat, st.session_state.lon):
            st.session_state.lat = novo_clique[0]
            st.session_state.lon = novo_clique[1]
            st.session_state.zoom = 15
            st.rerun()
