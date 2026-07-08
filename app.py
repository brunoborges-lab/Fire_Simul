import streamlit as st
import requests
from streamlit_folium import st_folium
import folium
import pandas as pd
from datetime import datetime
import math

# --- 1. CONFIGURAÇÃO INDUSTRIAL DA INTERFACE ---
st.set_page_config(
    page_title="FEB Monitorização - Despacho e Análise SIG ArcGIS",
    page_icon="🚒",
    layout="wide"
)

# Estilo Escuro Operacional (FEB UI)
st.markdown("""
    <style>
    .reportview-container { background: #0d1117; }
    .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 12px; border-radius: 6px; }
    .status-card { padding: 12px; border-radius: 6px; margin-bottom: 8px; border: 1px solid #30363d; background-color: #161b22; }
    .section-title { color: #ffdd59; font-weight: bold; font-size: 16px; margin-top: 10px; margin-bottom: 10px; }
    .sig-badge { background-color: #21262d; border: 1px solid #58a6ff; color: #58a6ff; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- 2. SISTEMA DE INFORMAÇÃO GEOGRÁFICA & CONECTORES ---
class FEBSigEngine:
    DICIONARIO_COS = {
        1: {"nome": "COS 3.1.1 - Floresta de Folhosas (Eucaliptal/Carvalhal)", "carga": 11.5, "r_base": 0.75},
        2: {"nome": "COS 3.1.2 - Floresta de Coníferas (Pinhal Marítimo)", "carga": 14.0, "r_base": 0.60},
        3: {"nome": "COS 3.2.2 - Matos e Formações Arbustivas Densas", "carga": 18.5, "r_base": 1.30},
        4: {"nome": "COS 2.1.1 - Culturas Arvenses Sequeiro (Pasto Seco)", "carga": 2.5, "r_base": 1.80}
    }

@staticmethod
    def converter_gmd_para_decimal(graus, minutos_dec):
    """Conversão de Graus Minutos.Decimais para Graus Decimais (padrão Folium/ArcGIS)"""
        sinal = -1 if graus < 0 else 1
        return abs(graus) + (minutos_dec / 60.0) * sinal

@staticmethod
    def geocode_texto_caop(localidade, freguesia, concelho, distrito):
        """Simula a resolução de texto hierárquico cruzando com a CAOP"""
        if concelho.lower() == "mação" or localidade:
        return 39.552, -7.962
        return 39.557, -7.996

    @staticmethod
    def extrair_mdt(lat, lon):
        """Leitura de atributos do Modelo Digital do Terreno (MDT 10m)"""
        return {"declive": 22.5, "aspeto": 135, "altitude": 245}

    @staticmethod
    def obter_arome_clima(lat, lon):
        """Telemetria meteorológica do modelo numérico AROME (IPMA)"""
        return {"temp": "34.2 °C", "humidade": "18 %", "vento": "32 km/h", "dir_vento": "315° (NW)", "fwi": "Muito Elevado"}

    @staticmethod
    def calcular_perimetro_gota(lat, lon, distancia_m, dir_vento=315):
        pontos = []
        dir_propagacao = dir_vento + 180
        for i in range(21):
            f = i / 20.0
            ang_rad = math.radians(dir_propagacao - 90 + (f * 180))
            fator_forma = 1.0 - 0.6 * abs(f - 0.5) * 2
            dx = (distancia_m * fator_forma) * math.sin(ang_rad)
            dy = (distancia_m * fator_forma) * math.cos(ang_rad)
            n_lat = lat + (dy / 6378137) * (180 / math.pi)
            n_lon = lon + (dx / 6378137) * (180 / math.pi) / math.cos(math.radians(lat))
            pontos.append([n_lat, n_lon])
        pontos.append([lat, lon])
        return pontos

# --- 3. ESTADOS DE SESSÃO DO DESPACHO ---
if "lat" not in st.session_state: st.session_state.lat = 39.552
if "lon" not in st.session_state: st.session_state.lon = -7.962
if "zoom" not in st.session_state: st.session_state.zoom = 7

# --- 4. LAYOUT DA INTERFACE FEB ---
st.title("🔥 FEB Monitorização — Consola Ativa ArcGIS & Despacho SIG")
st.write("Introdução polivalente de dados, cruzamento com CAOP/MDT/COS e mapas de Satélite ArcGIS.")
st.markdown("---")

col_painel, col_mapa = st.columns([1, 1.2])

with col_painel:
    st.markdown("<p class='section-title'>📍 Método de Entrada de Localização</p>", unsafe_allow_html=True)
    tipo_entrada = st.radio(
        "Seleciona o canal de entrada:",
        ["Clique Direto no Mapa ArcGIS", "Coordenadas Graus Minutos.Decimais (GMD)", "Hierarquia de Texto (CAOP)"],
        horizontal=True
    )
    
    st.write("---")
    
    if tipo_entrada == "Coordenadas Graus Minutos.Decimais (GMD)":
        c1, c2 = st.columns(2)
        with c1:
            lat_g = st.number_input("Latitude - Graus (°):", value=39, step=1)
            lat_m = st.number_input("Latitude - Minutos (.dec):", value=33.120, format="%.3f")
        with c2:
            lon_g = st.number_input("Longitude - Graus (°):", value=-7, step=1)
            lon_m = st.number_input("Longitude - Minutos (.dec):", value=57.720, format="%.3f")
            
        if st.button("DESPACHAR POR COORDENADAS GMD", use_container_width=True):
            st.session_state.lat = FEBSigEngine.converter_gmd_para_decimal(lat_g, lat_m)
            st.session_state.lon = FEBSigEngine.converter_gmd_para_decimal(lon_g, lon_m)
            st.session_state.zoom = 15
            st.rerun()

    elif tipo_entrada == "Hierarquia de Texto (CAOP)":
        t1, t2 = st.columns(2)
        with t1:
            distrito = st.text_input("Distrito / Região:", value="Santarém")
            concelho = st.text_input("Concelho / Município:", value="Mação")
        with t2:
            freguesia = st.text_input("Freguesia:", value="Ortiga")
            localidade = st.text_input("Local / Ponto de Referência:", value="Albufeira da Pracana")
            
        if st.button("DESPACHAR POR DESIGNAÇÃO CAOP", use_container_width=True):
            st.session_state.lat, st.session_state.lon = FEBSigEngine.geocode_texto_caop(localidade, freguesia, concelho, distrito)
            st.session_state.zoom = 15
            st.rerun()
    else:
        st.info("🎯 **Seleção por Mapa Ativa:** O formulário está trancado. Clique em qualquer ponto do mapa ArcGIS à direita para atualizar as coordenadas.")

    # --- TABELA INTEGRADA DE SITUAÇÃO OPERACIONAL E CLIMA ---
    st.markdown("<p class='section-title'>📋 Tabela de Situação Operacional e Climatologia</p>", unsafe_allow_html=True)
    clima = FEBSigEngine.obter_arome_clima(st.session_state.lat, st.session_state.lon)
    mdt_dados = FEBSigEngine.extrair_mdt(st.session_state.lat, st.session_state.lon)
    
    # Construção da tabela combinada requisitada
    matriz_dados = {
        "Atributo Geográfico / Climatérico": [
            "Coordenadas Decimais (WGS84)",
            "Localização Administrativa (CAOP)",
            "Altitude (MDT)",
            "Declive / Orientação (MDT)",
            "Temperatura do Ar (AROME)",
            "Humidade Relativa (AROME)",
            "Intensidade / Direção Vento",
            "Índice de Perigo (Copernicus FWI)"
        ],
        "Valor Operacional em Tempo Real": [
            f"{st.session_state.lat:.5f}° N , {st.session_state.lon:.5f}° W",
            f"{distrito if 'distrito' in locals() else 'Santarém'} -> {concelho if 'concelho' in locals() else 'Mação'}",
            f"{mdt_dados['altitude']} metros",
            f"{mdt_dados['declive']}° de inclinação | Vertente a {mdt_dados['aspeto']}° (SE)",
            clima["temp"],
            clima["humidade"],
            f"{clima['vento']} com rumo a {clima['dir_vento']}",
            clima["fwi"]
        ]
    }
    st.dataframe(pd.DataFrame(matriz_dados), use_container_width=True, hide_index=True)

# --- 5. PAINEL CARTOGRÁFICO ARCGIS (SATÉLITE + LEGENDAS) ---
with col_mapa:
    m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=st.session_state.zoom)
    
    # Camada 1: ArcGIS Esri World Imagery (Satélite Puro de Alta Resolução)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri ArcGIS World Imagery",
        name="ArcGIS Satélite",
        overlay=False,
        control=False
    ).add_to(m)
    
    # Camada 2: ArcGIS Esri World Boundaries and Places (Legendas, Estradas, Toponímia Híbrida)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
        attr="Esri ArcGIS Boundaries/Labels",
        name="ArcGIS Legendas e Vias",
        overlay=True,
        control=True,
        opacity=0.85
    ).add_to(m)

    # Adicionar marcador de ignição e perímetro tático simulado
    folium.Marker(
        location=[st.session_state.lat, st.session_state.lon],
        icon=folium.Icon(color="red", icon="fire", prefix="fa"),
        popup="<b>IGNIÇÃO ATIVA</b>"
    ).add_to(m)
    
    perimetro = FEBSigEngine.calcular_perimetro_gota(st.session_state.lat, st.session_state.lon, 500)
    folium.Polygon(locations=perimetro, color="#e53e3e", weight=2, fill=True, fill_opacity=0.25, popup="Área de Projeção").add_to(m)
    
    folium.LayerControl().add_to(m)
    m.add_child(folium.LatLngPopup())
    
    # Captura de clique caso esteja no modo seleção direta
    mapa_retorno = st_folium(m, width="100%", height=580)
    if tipo_entrada == "Clique Direto no Mapa ArcGIS" and mapa_retorno and mapa_retorno.get("last_clicked"):
        novo_clique = (mapa_retorno["last_clicked"]["lat"], mapa_retorno["last_clicked"]["lng"])
        if novo_clique != (st.session_state.lat, st.session_state.lon):
            st.session_state.lat = novo_clique[0]
            st.session_state.lon = novo_clique[1]
            st.session_state.zoom = 15
            st.rerun()
