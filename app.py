import streamlit as st
import requests
from streamlit_folium import st_folium
import folium
import pandas as pd
from datetime import datetime
import math

# --- 1. CONFIGURAÇÃO DO AMBIENTE GEOPROCIV ---
st.set_page_config(
    page_title="GEOPROCIV - Sistema de Gestão de Emergências e Proteção Civil",
    page_icon="🛡️",
    layout="wide"
)

# Estilo visual Steel/Slate Gray do GEOPROCIV
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

# --- 2. MOTORES DE CONVERSÃO E GEOPROCESSAMENTO ---
class GEOPROCIVEngine:
    @staticmethod
    def decimal_para_gmd(decimal, is_lat=True):
        """Converte Graus Decimais para a string formatada em Graus Minutos Decimais (GMD)"""
        graus = int(decimal)
        minutos = abs(decimal - graus) * 60.0
        direcao = ""
        if is_lat:
            direcao = "N" if graus >= 0 else "S"
        else:
            direcao = "E" if graus >= 0 else "W"
        return f"{abs(graus)}° {minutos:.3f}' {direcao}"

    @staticmethod
    def converter_gmd_para_decimal(graus, minutos_dec):
        sinal = -1 if graus < 0 else 1
        return abs(graus) + (minutos_dec / 60.0) * sinal

    @staticmethod
    def obter_dados_caop_locais(lat, lon):
        """Simulação de intersecção espacial WFS com a CAOP e Toponímia"""
        # Em produção, isto cruza as coordenadas com polígonos reais
        return {
            "localidade": "Cruizamento de Mação",
            "freguesia": "Ortiga",
            "concelho": "Mação",
            "distrito": "Santarém",
            "altitude": 210, "declive": 18.5, "aspeto": "Noroeste (NW)"
        }

    @staticmethod
    def obter_clima_arome(lat, lon):
        return {"temp": "31.8 °C", "hr": "24 %", "vento": "28 km/h", "dir": 135, "fwi": "Muito Elevado"}

    @staticmethod
    def projetar_frente_fogo(lat, lon, dist_m, dir_vento):
        pontos = []
        dir_propagacao = (dir_vento + 180) % 360
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

# --- 4. JANELA MODAL DE VALIDAÇÃO (POP-UP OPERACIONAL) ---
@st.dialog("🛡️ GEOPROCIV - Validação de Ponto de Ignição")
def abrir_janela_validacao(lat_clicada, lon_clicada):
    # Extrair metadados geográficos imediatos do ponto clicado
    dados_ponto = GEOPROCIVEngine.obter_dados_caop_locais(lat_clicada, lon_clicada)
    gmd_lat = GEOPROCIVEngine.decimal_para_gmd(lat_clicada, is_lat=True)
    gmd_lon = GEOPROCIVEngine.decimal_para_gmd(lon_clicada, is_lat=False)
    
    st.write("Confirme os dados extraídos da cartografia oficial (CAOP) para o local selecionado:")
    
    # Desenhar tabela de verificação dentro do popup
    df_validar = pd.DataFrame({
        "Campo Cartográfico": ["Localidade", "Freguesia", "Concelho", "Distrito", "Latitude (GMD)", "Longitude (GMD)"],
        "Informação Detetada": [dados_ponto["localidade"], dados_ponto["freguesia"], dados_ponto["concelho"], dados_ponto["distrito"], gmd_lat, gmd_lon]
    })
    st.dataframe(df_validar, use_container_width=True, hide_index=True)
    
    st.warning("⚠️ Ao validar, este ponto passará a ser o Ponto Zero ativo para projeções e despacho de meios.")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("❌ REJEITAR", use_container_width=True):
            st.rerun()
    with c2:
        if st.button("✅ VALIDAR PONTO", type="primary", use_container_width=True):
            # Efetivar as novas coordenadas no estado global da aplicação
            st.session_state.lat = lat_clicada
            st.session_state.lon = lon_clicada
            st.session_state.zoom = 14
            st.success("Ponto validado com sucesso!")
            st.rerun()

# --- 5. BARRA LATERAL CONTROLE DE CAMADAS ---
with st.sidebar:
    st.image("https://img.icons8.com/color/96/shield-with-a-sparkle.png", width=50)
    st.title("GEOPROCIV v4.2")
    st.markdown("---")
    
    st.markdown("<p class='layer-section'>📥 ENTRADA DE ALERTA</p>", unsafe_allow_html=True)
    modo_input = st.selectbox("Método de Georreferenciação:", ["Clique Direto na Carta", "Coordenadas GMD (Rádio)", "Pesquisa Administrativa"])
    
    if modo_input == "Coordenadas GMD (Rádio)":
        c1, c2 = st.columns(2)
        with c1:
            g_lat = st.number_input("Lat (Graus):", value=39, step=1)
            m_lat = st.number_input("Lat (Min.Dec):", value=33.120, format="%.3f")
        with c2:
            g_lon = st.number_input("Lon (Graus):", value=-7, step=1)
            m_lon = st.number_input("Lon (Min.Dec):", value=57.720, format="%.3f")
        if st.button("ANALISAR COORDENADAS", use_container_width=True):
            lat_calc = GEOPROCIVEngine.converter_gmd_para_decimal(g_lat, m_lat)
            lon_calc = GEOPROCIVEngine.converter_gmd_para_decimal(g_lon, m_lon)
            abrir_janela_validacao(lat_calc, lon_calc)
            
    st.markdown("---")
    st.markdown("<p class='layer-section'>🗺️ ÁRVORE DE CAMADAS (LAYERS)</p>", unsafe_allow_html=True)
    show_arcgis_labels = st.checkbox("Toponímia e Linhas de Água (ArcGIS)", value=True)
    show_projection = st.checkbox("Vetor de Projeção Parabólica (Rothermel)", value=True)
    
    st.markdown("---")
    st.markdown("<p class='layer-section'>⏱️ PARÂMETROS TEMPORAIS</p>", unsafe_allow_html=True)
    tempo_projecao = st.slider("Janela de Previsão Dinâmica:", min_value=1, max_value=6, value=2, format="%dh")

# --- 6. PAINEL CENTRAL E TABELA DE SITUAÇÃO COMBINADA ---
st.title("🛡️ Consola Operacional GEOPROCIV — ANPC / Municípios")
st.write("Plataforma Integrada de Comando e Controlo com Validação de Alertas Geográficos.")

col_mapa, col_tabela = st.columns([1.5, 1])

geo_dados = GEOPROCIVEngine.obter_dados_caop_locais(st.session_state.lat, st.session_state.lon)
clima_dados = GEOPROCIVEngine.obter_clima_arome(st.session_state.lat, st.session_state.lon)

# Construção do Mapa ArcGIS
m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=st.session_state.zoom)

folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri ArcGIS World Imagery", name="ArcGIS Satélite", overlay=False, control=False
).add_to(m)

if show_arcgis_labels:
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
        attr="Esri ArcGIS Labels", name="ArcGIS Legendas", overlay=True, control=False, opacity=0.85
    ).add_to(m)

# Ponto Zero Ativo e Validado
folium.Marker(
    location=[st.session_state.lat, st.session_state.lon],
    icon=folium.Icon(color="red", icon="exclamation-triangle", prefix="fa"),
    popup=f"<b>PONTO VALIDADO</b><br>{geo_dados['localidade']}"
).add_to(m)

if show_projection:
    extensao_metros = tempo_projecao * 450
    poligono_fogo = GEOPROCIVEngine.projetar_frente_fogo(st.session_state.lat, st.session_state.lon, extensao_metros, clima_dados["dir"])
    folium.Polygon(locations=poligono_fogo, color="#d63031", weight=2, fill=True, fill_opacity=0.25).add_to(m)

m.add_child(folium.LatLngPopup())

with col_mapa:
    mapa_saida = st_folium(m, width="100%", height=560)
    # Se o utilizador clicar no mapa, captura o ponto e abre a Janela de Validação requisitada
    if modo_input == "Clique Direto na Carta" and mapa_saida and mapa_saida.get("last_clicked"):
        clique_lat = mapa_saida["last_clicked"]["lat"]
        clique_lon = mapa_saida["last_clicked"]["lng"]
        
        # Abre o popup se o clique for diferente do ponto atualmente validado
        if abs(clique_lat - st.session_state.lat) > 0.0001 or abs(clique_lon - st.session_state.lon) > 0.0001:
            abrir_janela_validacao(clique_lat, clique_lon)

with col_tabela:
    st.subheader("📋 Matriz Atual de Situação Operacional (Ponto Validado)")
    
    dados_totais_geoprociv = {
        "Atributo Técnico do Evento": [
            "Localidade de Referência",
            "Freguesia (CAOP)",
            "Concelho (CAOP)",
            "Distrito Administrativo",
            "Latitude (GMD)",
            "Longitude (GMD)",
            "Cota de Altitude Terrestre (MDT)",
            "Declive / Orientação (MDT)",
            "Temperatura Ambiente (AROME)",
            "Humidade Relativa do Ar (AROME)",
            "Intensidade / Vetor do Vento"
        ],
        "Registo de Sala de Crise": [
            geo_dados["localidade"],
            geo_dados["freguesia"],
            geo_dados["concelho"],
            geo_dados["distrito"],
            GEOPROCIVEngine.decimal_para_gmd(st.session_state.lat, is_lat=True),
            GEOPROCIVEngine.decimal_para_gmd(st.session_state.lon, is_lat=False),
            f"{geo_dados['altitude']} metros",
            f"{geo_dados['declive']}% | Encosta voltada a {geo_dados['aspeto']}",
            clima_dados["temp"],
            clima_dados["hr"],
            f"{clima_dados['vento']} com rumo a {clima_dados['dir']}°"
        ]
    }
    st.dataframe(pd.DataFrame(dados_totais_geoprociv), use_container_width=True, hide_index=True)
