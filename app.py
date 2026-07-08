import streamlit as st
import requests
from streamlit_folium import st_folium
import folium
import pandas as pd
from datetime import datetime
import math

# --- 1. CONFIGURAÇÃO DO AMBIENTE GEOPROCIV CINZENTO ---
st.set_page_config(
    page_title="FIRESIMUL - Simulador de Incêndios Rurais",
    page_icon="🛡️",
    layout="wide"
)

# Estilo Monocromático de Alta Visibilidade Tática
st.markdown("""
    <style>
    .reportview-container { background: #1a1a1a; }
    .stSidebar { background-color: #FFFFFF !important; border-right: 2px solid #333333; }
    .stMetric { background-color: #DDDDDD; border: 1px solid #444444; padding: 10px; border-radius: 4px; }
    .pea-card { background-color: #DDDDDD; padding: 15px; border-radius: 4px; border-left: 5px solid #d63031; margin-bottom: 12px; }
    .sensivel-card { background-color: #FFFFFF; padding: 10px; border-radius: 4px; margin-bottom: 8px; border: 1px solid #ff793f; }
    .layer-section { font-weight: bold; color: #aaaaaa; margin-top: 10px; font-size: 14px; }
    h1, h2, h3 { color: #ffffff !important; font-family: 'Segoe UI', sans-serif; }
    
    /* Filtro CSS para forçar o Mapa ArcGIS em Tons de Cinza (Greyscale) */
    .folium-map { filter: grayscale(100%) contrast(110%) brightness(95%); }
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTOR GEOPROCESSAMENTO E ANÁLISE DE VULNERABILIDADES ---
class GEOPROCIVEngine:
    @staticmethod
    def decimal_para_gmd(decimal, is_lat=True):
        graus = int(decimal)
        minutos = abs(decimal - graus) * 60.0
        direcao = "N" if is_lat else "W" if decimal < 0 else "E"
        return f"{abs(graus)}° {minutos:.3f}' {direcao}"

    @staticmethod
    def converter_gmd_para_decimal(graus, minutos_dec):
        sinal = -1 if graus < 0 else 1
        return abs(graus) + (minutos_dec / 60.0) * sinal

    @staticmethod
    def obter_dados_caop_reais(lat, lon):
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=14"
        headers = {"User-Agent": "FireSimul"}
        try:
            response = requests.get(url, headers=headers, timeout=3)
            if response.status_code == 200:
                address = response.json().get("address", {})
                return {
                    "localidade": address.get("suburb", address.get("village", address.get("town", "Ponto Isolado"))),
                    "freguesia": address.get("parish", "Freguesia n/ mapeada"),
                    "concelho": address.get("municipality", address.get("county", "Concelho n/ mapeada")),
                    "distrito": address.get("state", "Portugal")
                }
        except Exception:
            pass
        return {"localidade": "Zona de Alvo", "freguesia": "Freguesia Local", "concelho": "Concelho Sede", "distrito": "Distrito"}

    @staticmethod
    def detetar_pontos_sensiveis(lat, lon, alcance_m):
        """Identifica vulnerabilidades críticas teóricas no raio de projeção do incêndio"""
        # Em produção, isto corre uma query espacial de interseção (ST_Intersection) PostGIS
        if alcance_m < 1000:
            return [
                {"tipo": "🏡 Aglomerado Populacional", "nome": "Casal da Barba Pouca", "dist": "450m", "status": "Risco Moderado"},
                {"tipo": "⚡ Infraestrutura Crítica", "nome": "Posto de Transformação Mação-Sul", "dist": "800m", "status": "Alerta Ativo"}
            ]
        else:
            return [
                {"tipo": "🏡 Aglomerado Populacional", "nome": "Casal da Barba Pouca", "dist": "450m", "status": "Evacuação Preventiva"},
                {"tipo": "⚡ Infraestrutura Crítica", "nome": "Posto de Transformação Mação-Sul", "dist": "800m", "status": "Linha Protegida"},
                {"tipo": "🏥 Ponto Sensível Especial", "nome": "Lar de Idosos da Freguesia", "dist": "1400m", "status": "Crítico / Preparar Linhas"}
            ]

    @staticmethod
    def calcular_proximidade_meios(lat, lon):
        """Gera a tabela de proximidade logística aos Corpos de Bombeiros mais próximos"""
        # Simulação de distâncias rodoviárias de despacho real
        return [
            {"Meio de Socorro / Corporação": "Bombeiros Voluntários de Mação", "Tipo": "Urbano / Florestal", "Distância": "4.2 km", "Tempo de Chegada": "6 min"},
            {"Meio de Socorro / Corporação": "Bombeiros Voluntários de Vila de Rei", "Tipo": "Florestal Avançado", "Distância": "12.8 km", "Tempo de Chegada": "14 min"},
            {"Meio de Socorro / Corporação": "CMA Mação (Meio Aéreo)", "Tipo": "Helicóptero Bombardeiro Light", "Distância": "5.1 km", "Tempo de Chegada": "3 min"},
            {"Meio de Socorro / Corporação": "Bombeiros Voluntários de Sardoal", "Tipo": "Reforço Tanques (BTTN)", "Distância": "18.5 km", "Tempo de Chegada": "22 min"}
        ]

    @staticmethod
    def gerar_pea(tempo_h, pontos_sensiveis, concelho):
        """Gera o Plano Estratégico de Ação operacional baseado nas ameaças detetadas"""
        diretrizes = [
            f"1. **Setorização Primária:** Estabelecer o Posto de Comando Operacional (PCO) em zona segura fora da linha de vento.",
            f"2. **Ataque Expandido:** Priorizar o flanco esquerdo para diminuir o ritmo de avanço da cabeça do incêndio.",
            f"3. **Defesa Perimétrica:** Mobilizar imediatamente os Bombeiros de Mação para criar linhas de água de proteção nos pontos sensíveis detetados."
        ]
        
        # Inserção de inteligência de decisão condicional baseado no perigo
        for p in pontos_sensiveis:
            if "Lar" in p["nome"]:
                diretrizes.append(f"4. **AÇÃO CRÍTICA (Linha de Vida):** Ativar a equipa do {p['nome']} para confinamento ou evacuação coordenada com a GNR.")
                break
        
        if tempo_h >= 4:
            diretrizes.append("5. **Logística de Sustentação:** Solicitar ao escalão Distrital a ativação do Grupo de Reforço para Ataque Ampliado (GRIF).")
            
        return diretrizes

# --- 3. ESTADOS DE MEMÓRIA DA SESSÃO ---
if "lat" not in st.session_state: st.session_state.lat = 39.552
if "lon" not in st.session_state: st.session_state.lon = -7.962
if "zoom" not in st.session_state: st.session_state.zoom = 8

# --- 4. JANELA MODAL DE VALIDAÇÃO (POP-UP OPERACIONAL) ---
@st.dialog("🛡️ Validação de Ocorrência")
def abrir_janela_validacao(lat_clicada, lon_clicada):
    dados_ponto = GEOPROCIVEngine.obter_dados_caop_reais(lat_clicada, lon_clicada)
    gmd_lat = GEOPROCIVEngine.decimal_para_gmd(lat_clicada, is_lat=True)
    gmd_lon = GEOPROCIVEngine.decimal_para_gmd(lon_clicada, is_lat=False)
    
    st.write("Deseja confirmar a introdução geográfica do Ponto Zero?")
    df_v = pd.DataFrame({
        "Mapeamento": ["Localidade", "Freguesia", "Concelho", "Coordenadas (GMD)"],
        "Dados Reais": [dados_ponto["localidade"], dados_ponto["freguesia"], dados_ponto["concelho"], f"{gmd_lat} | {gmd_lon}"]
    })
    st.dataframe(df_v, use_container_width=True, hide_index=True)
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("❌ REJEITAR", use_container_width=True): st.rerun()
    with c2:
        if st.button("✅ VALIDAR PONTO", type="primary", use_container_width=True):
            st.session_state.lat = lat_clicada
            st.session_state.lon = lon_clicada
            st.session_state.zoom = 14
            st.rerun()

# --- 5. BARRA LATERAL (CONTROLOS OPERACIONAIS) ---
with st.sidebar:
    st.title("FIRESIMUL TÁTICO")
    st.markdown("---")
    st.markdown("<p class='layer-section'>📥 CONFIGURAÇÃO DE ENTRADA</p>", unsafe_allow_html=True)
    modo_input = st.selectbox("Método:", ["Clique Direto na Carta", "Coordenadas GMD (Rádio)"])
    
    if modo_input == "Coordenadas GMD (SIRESP)":
        c1, c2 = st.columns(2)
        with c1:
            g_lat = st.number_input("Lat (Graus):", value=39, step=1)
            m_lat = st.number_input("Lat (Min.Dec):", value=33.120, format="%.3f")
        with c2:
            g_lon = st.number_input("Lon (Graus):", value=-7, step=1)
            m_lon = st.number_input("Lon (Min.Dec):", value=57.720, format="%.3f")
        if st.button("SUBMETER COORDENADAS", use_container_width=True):
            lat_calc = GEOPROCIVEngine.converter_gmd_para_decimal(g_lat, m_lat)
            lon_calc = GEOPROCIVEngine.converter_gmd_para_decimal(g_lon, m_lon)
            abrir_janela_validacao(lat_calc, lon_calc)

    st.markdown("---")
    st.markdown("<p class='layer-section'>⏱️ JANELA DA ESTRATÉGIA</p>", unsafe_allow_html=True)
    tempo_simulacao = st.slider("Hora Pretendida de Projeção:", min_value=1, max_value=8, value=3, format="%dh")

# --- 6. CÁLCULOS LOGÍSTICOS E ESPACIAIS EM TEMPO REAL ---
geo_dados = GEOPROCIVEngine.obter_dados_caop_reais(st.session_state.lat, st.session_state.lon)
alcance_estimado_m = tempo_simulacao * 520  # Expansão calculada baseada em vento padrão 

pontos_criticos = GEOPROCIVEngine.detetar_pontos_sensiveis(st.session_state.lat, st.session_state.lon, alcance_estimado_m)
meios_socorro = GEOPROCIVEngine.calcular_proximidade_meios(st.session_state.lat, st.session_state.lon)
plano_acao = GEOPROCIVEngine.gerar_pea(tempo_simulacao, pontos_criticos, geo_dados["concelho"])

# --- 7. PAINEL CENTRAL E MAPA MONOCROMÁTICO ---
st.title("🛡️ Consola de Gestão de Crise — Escala Monocromática")

col_mapa, col_tabela = st.columns([1.4, 1])

# Construção do Mapa em Escala de Cinzentos (via CSS injetado)
m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=st.session_state.zoom, control_scale=True)

folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri ArcGIS World Imagery", name="ArcGIS Satélite", overlay=False, control=False
).add_to(m)

folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
    attr="Esri ArcGIS Labels", name="ArcGIS Legendas", overlay=True, control=False, opacity=0.7
).add_to(m)

# Destaque de Cor Forte (Apenas Elementos de Perigo/Pontos Sensíveis saltam à vista)
folium.Marker(
    location=[st.session_state.lat, st.session_state.lon],
    icon=folium.Icon(color="darkred", icon="crosshairs", prefix="fa"),
    popup="PONTO ZERO VALIDADO"
).add_to(m)

# Desenho da elipse de perigo (Cor Vermelho Vivo contrasta com o Cinza do mapa)
# Simulando a progressão para a direção Norte-Nordeste
fator_angulo = math.radians(45)
pontos_elipse = []
for i in range(30):
    a = math.radians(i * 12)
    dx = (alcance_estimado_m * 0.5) * math.sin(a)
    dy = (alcance_estimado_m) * math.cos(a)
    rx = dx * math.cos(fator_angulo) - dy * math.sin(fator_angulo)
    ry = dx * math.sin(fator_angulo) + dy * math.cos(fator_angulo)
    n_lat = st.session_state.lat + (ry / 6378137) * (180 / math.pi)
    n_lon = st.session_state.lon + (rx / 6378137) * (180 / math.pi) / math.cos(math.radians(st.session_state.lat))
    pontos_elipse.append([n_lat, n_lon])

folium.Polygon(locations=pontos_elipse, color="#ff3838", weight=3, fill=True, fill_opacity=0.2, popup="Frente Avançada").add_to(m)

with col_mapa:
    mapa_saida = st_folium(m, width="100%", height=520, key="mapa_geoprociv_monocrome")
    if modo_input == "Clique Direto na Carta" and mapa_saida and mapa_saida.get("last_clicked"):
        clique_lat = mapa_saida["last_clicked"]["lat"]
        clique_lon = mapa_saida["last_clicked"]["lng"]
        if abs(clique_lat - st.session_state.lat) > 0.0001 or abs(clique_lon - st.session_state.lon) > 0.0001:
            abrir_janela_validacao(clique_lat, clique_lon)

# --- 8. ANÁLISE DE RISCO, LOGÍSTICA E PLANO ESTRATÉGICO ---
with col_tabela:
    st.subheader("🚨 Vulnerabilidades e Pontos Sensíveis")
    for p in pontos_criticos:
        st.markdown(
            f"<div class='sensivel-card'>"
            f"<b>{p['tipo']}:</b> {p['nome']} &rarr; <span style='color:#ff793f;'><b>Ameaçado a {p['dist']}</b></span><br>"
            f"Status Operacional: <b>{p['status']}</b>"
            f"</div>", unsafe_allow_html=True
        )

    st.subheader("🚒 Proximidade e Despacho de Meios de Socorro")
    st.dataframe(pd.DataFrame(meios_socorro), use_container_width=True, hide_index=True)

st.markdown("---")
st.subheader(f"📋 PEA - Plano Estratégico de Ação (Projeção para a Hora Pretendida: +{tempo_simulacao}h)")

# Apresentação do plano tático gerado para o operador
c_pea1, c_pea2 = st.columns(2)
with c_pea1:
    st.markdown(
        f"<div class='pea-card'>"
        f"<b>SÍNTESE DE COMANDO:</b><br>"
        f"Teatro de Operações validado na localidade de <b>{geo_dados['localidade']}</b> ({geo_dados['freguesia']}). "
        f"À hora pretendida (+{tempo_simulacao}h), o incêndio apresenta um alcance linear estimado de <b>{alcance_estimado_m} metros</b>. "
        f"Foram identificados <b>{len(pontos_criticos)} pontos sensíveis críticos</b> na calha de propagação."
        f"</div>", unsafe_allow_html=True
    )

with c_pea2:
    st.write("**Diretrizes Táticas de Intervenção de Proteção Civil:**")
    for linha in plano_acao:
        st.write(linha)
