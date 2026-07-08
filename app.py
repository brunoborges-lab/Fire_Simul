import streamlit as st
import requests
from streamlit_folium import st_folium
import folium
import pandas as pd
from datetime import datetime, timedelta
import math

# --- 1. CONFIGURAÇÃO DO AMBIENTE GEOPROCIV ---
st.set_page_config(
    page_title="Simulação de Incêndio Rural",
    page_icon="🛡️",
    layout="wide"
)

# Customização CSS para emular a palete de cores "Steel/Slate Gray" do GEOPROCIV
st.markdown("""
    <style>
    .reportview-container { background: #1e2530; }
    .stSidebar { background-color: #161c24 !important; border-right: 2px solid #2d3748; }
    .stMetric { background-color: #242e3d; border: 1px solid #3e4b5e; padding: 10px; border-radius: 4px; }
    .geoprociv-card { background-color: #242e3d; padding: 12px; border-radius: 4px; border-left: 5px solid #ff793f; margin-bottom: 10px; }
    .layer-section { font-weight: bold; color: #74b9ff; margin-top: 10px; font-size: 14px; }
    h1, h2, h3 { color: #ffffff !important; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTORES DE CONVERSÃO E BASES DE DADOS ---
class GEOPROCIVEngine:
    @staticmethod
    def converter_gmd_para_decimal(graus, minutos_dec):
        sinal = -1 if graus < 0 else 1
        return abs(graus) + (minutos_dec / 60.0) * sinal

    @staticmethod
    def simular_caop_e_mdt(lat, lon):
        # Simulação do cruzamento geográfico nativo do GEOPROCIV
        return {
            "distrito": "Santarém", "concelho": "Mação", "freguesia": "Ortiga",
            "altitude": 210, "declive": 18.5, "aspeto": "Noroeste (NW)"
        }

    @staticmethod
    def obter_clima_arome(lat, lon):
        return {"temp": "31.8 °C", "hr": "24 %", "vento": "28 km/h", "dir": 135, "fwi": "Muito Elevado"}

    @staticmethod
    def projetar_frente_fogo(lat, lon, dist_m, dir_vento):
        pontos = []
        dir_propagacao = (dir_vento + 180) % 360
        # Geração vetorial da elipse de área afetada (Modelo de Fluido GEOPROCIV)
        for i in range(25):
            f = i / 24.0
            ang = math.radians(dir_propagacao - 60 + (f * 120))
            fator_eixo = 1.0 - 0.5 * abs(f - 0.5) * 2
            dx = (dist_m * fator_eixo) * math.sin(ang)
            dy = (dist_m * fator_eixo) * math.cos(ang)
            n_lat = lat + (dy / 6378137) * (180 / math.pi)
            n_lon = lon + (dx / 6378137) * (180 / math.pi) / math.cos(math.radians(lat))
            pontos.append([n_lat, n_lon])
        pontos.append([lat, lon])
        return pontos

# --- 3. ESTADOS DE MEMÓRIA DA SALA DE CRISE ---
if "lat" not in st.session_state: st.session_state.lat = 39.552
if "lon" not in st.session_state: st.session_state.lon = -7.962
if "zoom" not in st.session_state: st.session_state.zoom = 8

# --- 4. BARRA LATERAL (CONTROLOS DE CAMADAS E DESPACHO DO GEOPROCIV) ---
with st.sidebar:
    st.image("https://img.icons8.com/color/96/shield-with-a-sparkle.png", width=50) # Ícone representativo de Proteção Civil
    st.title("GEOPROCIV v4.2")
    st.markdown("---")
    
    st.markdown("<p class='layer-section'>📥 ENTRADA DE ALERTA (PONTO ZERO)</p>", unsafe_allow_html=True)
    modo_input = st.selectbox("Método de Georreferenciação:", ["Clique Direto na Carta", "Coordenadas GMD (Rádio)", "Pesquisa Administrativa"])
    
    if modo_input == "Coordenadas GMD (Rádio)":
        c1, c2 = st.columns(2)
        with c1:
            g_lat = st.number_input("Lat (Graus):", value=39, step=1)
            m_lat = st.number_input("Lat (Min.Dec):", value=33.120, format="%.3f")
        with c2:
            g_lon = st.number_input("Lon (Graus):", value=-7, step=1)
            m_lon = st.number_input("Lon (Min.Dec):", value=57.720, format="%.3f")
        if st.button("SUBMETER PARA DESPACHO", use_container_width=True):
            st.session_state.lat = GEOPROCIVEngine.converter_gmd_para_decimal(g_lat, m_lat)
            st.session_state.lon = GEOPROCIVEngine.converter_gmd_para_decimal(g_lon, m_lon)
            st.session_state.zoom = 14
            st.rerun()
            
    st.markdown("---")
    st.markdown("<p class='layer-section'>🗺️ ÁRVORE DE CAMADAS (LAYERS)</p>", unsafe_allow_html=True)
    show_arcgis_labels = st.checkbox("Toponímia e Linhas de Água (ArcGIS)", value=True)
    show_effis = st.checkbox("Risco de Incêndio FWI (Copernicus WMS)", value=False)
    show_projection = st.checkbox("Vetor de Projeção Parabólica (Rothermel)", value=True)
    
    st.markdown("---")
    st.markdown("<p class='layer-section'>⏱️ PARÂMETROS TEMPORAIS</p>", unsafe_allow_html=True)
    tempo_projeção = st.slider("Janela de Previsão Dinâmica:", min_value=1, max_value=6, value=2, postfix="h")

# --- 5. PAINEL CENTRAL E TABELA DE SITUAÇÃO COMBINADA ---
st.title("🛡️ Consola Operacional GEOPROCIV — ANPC / Municípios")
st.write("Plataforma Integrada de Comando e Controlo de Emergências Médias e Graves.")

col_mapa, col_tabela = st.columns([1.5, 1])

# Cálculo de variáveis em tempo de execução
geo_dados = GEOPROCIVEngine.simular_caop_e_mdt(st.session_state.lat, st.session_state.lon)
clima_dados = GEOPROCIVEngine.obter_clima_arome(st.session_state.lat, st.session_state.lon)

# Geração do mapa tático baseado em ArcGIS
m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=st.session_state.zoom)

# Camada Base Obrigatória: ArcGIS Imagens de Satélite
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri ArcGIS World Imagery", name="ArcGIS Satélite", overlay=False, control=False
).add_to(m)

# Ativação condicional das legendas e vias ArcGIS baseadas na árvore de camadas lateral
if show_arcgis_labels:
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
        attr="Esri ArcGIS Labels", name="ArcGIS Legendas", overlay=True, control=False, opacity=0.85
    ).add_to(m)

# Ativação condicional do WMS Copernicus
if show_effis:
    folium.WmsTileLayer(
        url="https://effis-gwis-wms.apps.vgt.vito.be/geoserver/effis/wms",
        layers="modis.fwi", fmt="image/png", transparent=True, version="1.1.1",
        name="Copernicus FWI", overlay=True, control=False, opacity=0.4
    ).add_to(m)

# Marcadores táticos padrão GEOPROCIV
folium.Marker(
    location=[st.session_state.lat, st.session_state.lon],
    icon=folium.Icon(color="orange", icon="exclamation-triangle", prefix="fa"),
    popup="<b>GEOPROCIV: Alerta Registado</b>"
).add_to(m)

if show_projection:
    extensao_metros = tempo_projeção * 450 # Velocidade média de avanço estimada
    poligono_fogo = GEOPROCIVEngine.projetar_frente_fogo(st.session_state.lat, st.session_state.lon, extensao_metros, clima_dados["dir"])
    folium.Polygon(locations=poligono_fogo, color="#d63031", weight=2, fill=True, fill_opacity=0.25, popup="Isócrona Estimada").add_to(m)

# Adicionar rede de coordenadas flutuante
m.add_child(folium.LatLngPopup())

with col_mapa:
    mapa_saida = st_folium(m, width="100%", height=560)
    if modo_input == "Clique Direta na Carta" and mapa_saida and mapa_saida.get("last_clicked"):
        novo_ponto = (mapa_saida["last_clicked"]["lat"], mapa_saida["last_clicked"]["lng"])
        if novo_ponto != (st.session_state.lat, st.session_state.lon):
            st.session_state.lat = novo_ponto[0]
            st.session_state.lon = novo_ponto[1]
            st.session_state.zoom = 14
            st.rerun()

with col_tabela:
    st.subheader("📋 Matriz de Despacho e Fusiamento de Dados SIG")
    
    # Construção da tabela unificada com georreferenciação e meteorologia
    dados_totais_geoprociv = {
        "Atributo Técnico do Evento": [
            "Localização Administrativa (CAOP)",
            "Identificador DICOFRE",
            "Cota de Altitude Terrestre (MDT)",
            "Análise de Declive / Vertente (MDT)",
            "Temperatura Ambiente (AROME)",
            "Humidade Relativa do Ar (AROME)",
            "Intensidade / Vetor do Vento",
            "Classificação de Risco Associada"
        ],
        "Registo de Sala de Crise": [
            f"{geo_dados['distrito']} / {geo_dados['concelho']} / {geo_dados['freguesia']}",
            "141303 (Ortiga)",
            f"{geo_dados['altitude']} metros de altitude",
            f"{geo_dados['declive']}% de inclinação | Encosta voltada a {geo_dados['aspeto']}",
            clima_dados["temp"],
            clima_dados["hr"],
            f"{clima_dados['vento']} com rumo a {clima_dados['dir']}°",
            clima_dados["fwi"]
        ]
    }
    st.dataframe(pd.DataFrame(dados_totais_geoprociv), use_container_width=True, hide_index=True)
    
    st.write("---")
    st.subheader("🚨 Síntese para Missão de Socorro")
    st.markdown(
        f"<div class='geoprociv-card'>"
        f"<b>DESPACHO IMEDIATO:</b> Alerta confirmado no concelho de <b>{geo_dados['concelho']}</b>. "
        f"As projeções matemáticas do motor indicam uma progressão potencial de <b>{tempo_projeção * 450} metros</b> nas próximas {tempo_projeção} horas "
        f"devido ao alinhamento do vento com a encosta em {geo_dados['aspeto']}.<br>"
        f"</div>", unsafe_allow_html=True
    )
