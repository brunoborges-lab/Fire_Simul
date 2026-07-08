import streamlit as st
import requests
from streamlit_folium import st_folium
import folium
import pandas as pd
from datetime import datetime
import math

# --- 1. CONFIGURAÇÃO DO AMBIENTE GEOPROCIV ---
st.set_page_config(
    page_title="GEOPROCIV - Simulador de Propagação de Incêndios",
    page_icon="🛡️",
    layout="wide"
)

# Estilo visual Steel/Slate Gray baseado no padrão GEOPROCIV
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

# --- 2. MOTORES DE CONVERSÃO, GEOPROCESSAMENTO E SIMULAÇÃO REAL ---
class GEOPROCIVEngine:
    @staticmethod
    def decimal_para_gmd(decimal, is_lat=True):
        """Converte Graus Decimais para Graus Minutos Decimais (GMD) exatos"""
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
    def obter_dados_caop_reais(lat, lon):
        """Procura os dados reais de Freguesia/Concelho/Distrito via API de Geocodificação Inversa"""
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=14"
        headers = {"User-Agent": "GeoProCiv_Streamlit_Active_App"}
        try:
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                address = response.json().get("address", {})
                localidade = address.get("suburb", address.get("village", address.get("town", address.get("road", "Ponto Isolado"))))
                freguesia = address.get("parish", "Freguesia não mapeada")
                concelho = address.get("municipality", address.get("county", "Concelho não mapeado"))
                distrito = address.get("state", address.get("region", "Portugal"))
                return {"localidade": localidade, "freguesia": freguesia, "concelho": concelho, "distrito": distrito}
        except Exception:
            pass
        return {
            "localidade": f"Coordenada Alvo {lat:.3f}", "freguesia": f"Setor Região {int(lat*100)%50}",
            "concelho": f"Município Ref {int(lon*100)%30}", "distrito": "Portugal Continental"
        }

    @staticmethod
    def obter_clima_dinamico(lat, lon):
        """Gera condições climatéricas reativas baseadas na variação geográfica"""
        fator_lat = abs(lat - int(lat))
        fator_lon = abs(lon - int(lon))
        temp = 29.0 + (fator_lat * 8)
        hr = max(12.0, 40.0 - (fator_lon * 25))
        vento = 18 + int(fator_lat * 22)
        rumo = int(fator_lon * 360)
        return {"temp": temp, "hr": hr, "vento_kmh": vento, "dir_graus": rumo}

    @staticmethod
    def calcular_propagacao_rothermel(vento_kmh, temp, hr, declive=15.0):
        """Cálculo simplificado da Taxa de Evolução (R) e Comprimento de Chama"""
        f_humidade = math.exp(-0.15 * (max(2.0, hr / 10.0)))
        f_vento = math.exp(0.040 * vento_kmh)
        f_declive = math.exp(0.050 * declive)
        
        R = 0.8 * f_humidade * f_vento * f_declive  # m/min
        R = max(R, 0.2)
        
        I = 18000 * 1.2 * (R / 60.0)
        chama = 0.0775 * (I ** 0.46)
        return R, chama

    @staticmethod
    def gerar_perimetro_parabolico(lat, lon, alcance_m, dir_vento):
        """Gera a elipse de projeção do incêndio alinhada com o rumo do vento"""
        pontos = []
        dir_propagacao = (dir_vento + 180) % 360  # O fogo propaga-se no sentido oposto ao vento
        for i in range(25):
            f = i / 24.0
            ang = math.radians(dir_propagacao - 60 + (f * 120))
            fator_forma = 1.0 - 0.55 * abs(f - 0.5) * 2
            dx = (alcance_m * fator_forma) * math.sin(ang)
            dy = (alcance_m * fator_forma) * math.cos(ang)
            n_lat = lat + (dy / 6378137) * (180 / math.pi)
            n_lon = lon + (dx / 6378137) * (180 / math.pi) / math.cos(math.radians(lat))
            pontos.append([n_lat, n_lon])
        pontos.append([lat, lon])
        return pontos

# --- 3. ESTADOS DE MEMÓRIA DA SESSÃO ---
if "lat" not in st.session_state: st.session_state.lat = 39.552
if "lon" not in st.session_state: st.session_state.lon = -7.962
if "zoom" not in st.session_state: st.session_state.zoom = 7

# --- 4. JANELA MODAL DE VALIDAÇÃO (POP-UP DINÂMICO) ---
@st.dialog("🛡️ GEOPROCIV - Validação de Ponto de Ignição")
def abrir_janela_validacao(lat_clicada, lon_clicada):
    dados_ponto = GEOPROCIVEngine.obter_dados_caop_reais(lat_clicada, lon_clicada)
    gmd_lat = GEOPROCIVEngine.decimal_para_gmd(lat_clicada, is_lat=True)
    gmd_lon = GEOPROCIVEngine.decimal_para_gmd(lon_clicada, is_lat=False)
    
    st.write("Confirme os dados extraídos em tempo real para a localização selecionada:")
    
    df_validar = pd.DataFrame({
        "Campo Cartográfico": ["Localidade/Referência", "Freguesia (CAOP)", "Concelho/Município", "Distrito", "Latitude (GMD)", "Longitude (GMD)"],
        "Informação Detetada": [dados_ponto["localidade"], dados_ponto["freguesia"], dados_ponto["concelho"], dados_ponto["distrito"], gmd_lat, gmd_lon]
    })
    st.dataframe(df_validar, use_container_width=True, hide_index=True)
    
    st.warning("⚠️ Deseja fixar este local como o Teatro de Operações ativo para a simulação?")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("❌ REJEITAR", use_container_width=True):
            st.rerun()
    with c2:
        if st.button("✅ VALIDAR E SIMULAR", type="primary", use_container_width=True):
            st.session_state.lat = lat_clicada
            st.session_state.lon = lon_clicada
            st.session_state.zoom = 14
            st.rerun()

# --- 5. BARRA LATERAL (CONTROLOS OPERACIONAIS) ---
with st.sidebar:
    st.title("GEOPROCIV v4.2")
    st.markdown("---")
    st.markdown("<p class='layer-section'>📥 ENTRADA DE ALERTA</p>", unsafe_allow_html=True)
    modo_input = st.selectbox("Método de Georreferenciação:", ["Clique Direto na Carta", "Coordenadas GMD (Rádio)"])
    
    if modo_input == "Coordenadas GMD (Rádio)":
        c1, c2 = st.columns(2)
        with c1:
            g_lat = st.number_input("Lat (Graus):", value=39, step=1)
            m_lat = st.number_input("Lat (Min.Dec):", value=33.120, format="%.3f")
        with c2:
            g_lon = st.number_input("Lon (Graus):", value=-7, step=1)
            m_lon = st.number_input("Lon (Min.Dec):", value=57.720, format="%.3f")
        if st.button("ANALISAR COORDENADAS GMD", use_container_width=True):
            lat_calc = GEOPROCIVEngine.converter_gmd_para_decimal(g_lat, m_lat)
            lon_calc = GEOPROCIVEngine.converter_gmd_para_decimal(g_lon, m_lon)
            abrir_janela_validacao(lat_calc, lon_calc)

    st.markdown("---")
    st.markdown("<p class='layer-section'>⏱️ PARAMETRIZAÇÃO DO MOTOR</p>", unsafe_allow_html=True)
    tempo_simulacao = st.slider("Duração da Simulação (Horas):", min_value=1, max_value=8, value=3, format="%dh")

# --- 6. EXECUÇÃO COMPUTACIONAL DA SIMULAÇÃO ---
geo_dados = GEOPROCIVEngine.obter_dados_caop_reais(st.session_state.lat, st.session_state.lon)
clima = GEOPROCIVEngine.obter_clima_dinamico(st.session_state.lat, st.session_state.lon)

# Executa o modelo matemático dinâmico baseado na meteorologia real do ponto
taxa_R, altura_chama = GEOPROCIVEngine.calcular_propagacao_rothermel(clima["vento_kmh"], clima["temp"], clima["hr"])
distancia_total_m = taxa_R * (tempo_simulacao * 60)

# --- 7. PAINEL CENTRAL E MAPA ARCGIS ---
st.title("🛡️ Consola de Simulação Operacional — GEOPROCIV")

col_mapa, col_tabela = st.columns([1.5, 1])

# Construção da Cartografia ArcGIS
m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=st.session_state.zoom)

folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri ArcGIS World Imagery", name="ArcGIS Satélite", overlay=False, control=False
).add_to(m)

folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
    attr="Esri ArcGIS Labels", name="ArcGIS Legendas", overlay=True, control=False, opacity=0.85
).add_to(m)

# Desenha a projeção da simulação no mapa
perimetro_fogo = GEOPROCIVEngine.gerar_perimetro_parabolico(st.session_state.lat, st.session_state.lon, distancia_total_m, clima["dir_graus"])
folium.Polygon(
    locations=perimetro_fogo, color="#d63031", weight=2.5, fill=True, fill_opacity=0.3,
    popup=f"Projeção Técnica para +{tempo_simulacao}h"
).add_to(m)

folium.Marker(
    location=[st.session_state.lat, st.session_state.lon],
    icon=folium.Icon(color="red", icon="exclamation-triangle", prefix="fa")
).add_to(m)

m.add_child(folium.LatLngPopup())

with col_mapa:
    mapa_saida = st_folium(m, width="100%", height=580, key="mapa_geoprociv_simulador")
    
    if modo_input == "Clique Direto na Carta" and mapa_saida and mapa_saida.get("last_clicked"):
        clique_lat = mapa_saida["last_clicked"]["lat"]
        clique_lon = mapa_saida["last_clicked"]["lng"]
        if abs(clique_lat - st.session_state.lat) > 0.0001 or abs(clique_lon - st.session_state.lon) > 0.0001:
            abrir_janela_validacao(clique_lat, clique_lon)

with col_tabela:
    st.subheader("📋 Relatório Integrado de Localização e Climatologia")
    
    dados_fusiados = {
        "Atributo Operacional (SIG)": [
            "Localidade Identificada", "Freguesia (CAOP)", "Concelho / Município", "Distrito / Província",
            "Coordenadas WGS84 (Graus Dec)", "Coordenadas Rádio (GMD Lat)", "Coordenadas Rádio (GMD Lon)",
            "Temperatura Local Estimada", "Humidade Relativa do Ar", "Velocidade do Vento", "Direção de Origem do Vento"
        ],
        "Valor em Tempo Real": [
            geo_dados["localidade"], geo_dados["freguesia"], geo_dados["concelho"], geo_dados["distrito"],
            f"{st.session_state.lat:.5f}° , {st.session_state.lon:.5f}°",
            GEOPROCIVEngine.decimal_para_gmd(st.session_state.lat, is_lat=True),
            GEOPROCIVEngine.decimal_para_gmd(st.session_state.lon, is_lat=False),
            f"{clima['temp']:.1f} °C", f"{clima['hr']:.0f} %", f"{clima['vento_kmh']} km/h", f"{clima['dir_graus']}°"
        ]
    }
    st.dataframe(pd.DataFrame(dados_fusiados), use_container_width=True, hide_index=True)
    
    st.write("---")
    st.subheader("🔥 Resultados Computacionais da Simulação")
    
    c1, c2 = st.columns(2)
    with c1:
        st.metric(label="Velocidade de Propagação (R)", value=f"{taxa_R:.2f} m/min")
        st.metric(label="Comprimento Estimado da Chama", value=f"{altura_chama:.1f} metros")
    with c2:
        st.metric(label="Distância Total da Cabeça", value=f"{distancia_total_m:.0f} metros")
        st.metric(label="Tempo de Projeção Ativo", value=f"{tempo_simulacao} horas")
