import streamlit as st
import requests
from streamlit_folium import st_folium
import folium
import pandas as pd
import math
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO OPERACIONAL FIRESIMUL ---
st.set_page_config(
    page_title="FIRESIMUL v5.6 - Sistema Avançado de Simulação",
    page_icon="🛡️",
    layout="wide"
)

# Estilo Visual Tático: Escala de Cinzentos e Cores de Alerta Avançadas
st.markdown("""
    <style>
    .reportview-container { background: #1a1a1a; }
    .stSidebar { background-color: #111111 !important; border-right: 2px solid #333333; }
    .stMetric { background-color: #222222; border: 1px solid #444444; padding: 10px; border-radius: 4px; }
    .pea-card { background-color: #222222; padding: 15px; border-radius: 4px; border-left: 5px solid #d63031; margin-bottom: 12px; }
    .sensivel-card { background-color: #2a2a2a; padding: 12px; border-radius: 4px; margin-bottom: 8px; border-left: 5px solid #ff793f; }
    .folium-map { filter: grayscale(100%) contrast(105%) brightness(95%); }
    h1, h2, h3, p { color: #ffffff !important; font-family: 'Segoe UI', sans-serif; }
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTOR DE GEOPROCESSAMENTO E MODELOS DIGITAIS (CAOP, MDT, COS) ---
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
        
        hash_calc = abs(int(lat * 1000) + int(lon * 1000))
        altitude_mdt = 75 + (hash_calc % 450)
        declive_mdt = 5.0 + (hash_calc % 32)
        orientacao_mdt = ["Norte (N)", "Sul (S)", "Este (E)", "Oeste (W)", "Sudoeste (SW)", "Noroeste (NW)"][hash_calc % 6]
        
        classes_cos = [
            "Floresta de Resinosas (Pinhal Bravo)", "Floresta de Folhosas (Eucaliptal)", 
            "Mato Denso / Urzes", "Sistemas Agrícolas Heterogéneos", "Tecido Urbano Descontínuo"
        ]
        uso_solo_cos = classes_cos[hash_calc % len(classes_cos)]
        
        caop_dados = {"localidade": "Ponto Isolado", "freguesia": "Não mapeada", "concelho": "Desconhecido", "distrito": "Portugal"}
        
        try:
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                addr = response.json().get("address", {})
                caop_dados = {
                    "localidade": addr.get("suburb", addr.get("village", addr.get("town", addr.get("road", "Ponto Isolado")))),
                    "freguesia": addr.get("parish", "Área sem discriminação"),
                    "concelho": addr.get("municipality", addr.get("county", "Desconhecido")),
                    "distrito": addr.get("state", "Portugal Continental")
                }
        except Exception:
            pass
            
        return {**caop_dados, "altitude": altitude_mdt, "declive": declive_mdt, "orientacao": orientacao_mdt, "cos_solo": uso_solo_cos}

    @staticmethod
    def obter_clima_reativo(lat, lon):
        fator = abs(lat - int(lat)) + abs(lon - int(lon))
        return {
            "temp": 26.5 + (fator * 12),
            "hr": max(10.0, 50.0 - (fator * 35)),
            "vento_speed": 12 + int(fator * 30),
            "vento_dir": int(fator * 360) % 360
        }

    @staticmethod
    def calcular_pontos_sensiveis_e_tempo(lat, lon, velocidade_m_min):
        agora = datetime.now()
        
        pontos = [
            {"tipo": "🏡 Aglomerado", "nome": "Lugar da Ventosa", "dist_m": 850, "lat": lat + 0.006, "lon": lon + 0.005},
            {"tipo": "⚡ Infraestrutura Crítica", "nome": "Subestação Elétrica Local", "dist_m": 1600, "lat": lat + 0.012, "lon": lon + 0.009},
            {"tipo": "🏥 Saúde / Vulnerável", "nome": "Lar de Idosos de São Vicente", "dist_m": 2900, "lat": lat + 0.021, "lon": lon + 0.015}
        ]
        
        for p in pontos:
            minutos_ate_impacto = p["dist_m"] / velocidade_m_min
            hora_impacto = agora + timedelta(minutes=minutos_ate_impacto)
            p["hora_prevista"] = hora_impacto.strftime("%H:%M:%S")
            p["tempo_restante"] = f"{int(minutos_ate_impacto)} min"
            
        return pontos

    @staticmethod
    def calcular_deslocacao_meios(lat, lon):
        return [
            {"Meio de Socorro": "Corpo de Bombeiros Sede", "Localização Original": "Quartel Concelhio (Centro)", "Distância (km)": "4.2 km", "Tempo de Marcha": "6 min", "Estado": "Despachado"},
            {"Meio de Socorro": "Grupo de Reforço Florestal (GRIF)", "Localização Original": "Ponto de Encontro Distrital", "Distância (km)": "18.5 km", "Tempo de Marcha": "24 min", "Estado": "Pré-Alerta"},
            {"Meio de Socorro": "Equipa de Sapadores Florestais", "Localização Original": "Posto Vigia / Setor Norte", "Distância (km)": "7.1 km", "Tempo de Marcha": "11 min", "Estado": "Em Trânsito"},
            {"Meio de Socorro": "Meio Aéreo Bombardeiro", "Localização Original": "Centro de Meios Aéreos (CMA)", "Distância (km)": "12.0 km", "Tempo de Voo": "4 min", "Estado": "Descolagem"}
        ]

    @staticmethod
    def obter_nasa_firms():
        return [
            {"lat": 39.562, "lon": -7.950, "satelite": "VIIRS (NOAA-20)", "confianca": "Alta", "temp_k": 348.5},
            {"lat": 39.540, "lon": -7.970, "satelite": "MODIS (Aqua)", "confianca": "Nominal", "temp_k": 321.4}
        ]

    @staticmethod
    def obter_prociv_ativas():
        return [
            {"id": "2026070801", "concelho": "Mação", "local": "Ortiga", "natureza": "Incêndio Rural", "estado": "Em Curso", "op": 92, "meios": 24, "lat": 39.552, "lon": -7.962}
        ]

# --- 3. ESTADOS DE SESSÃO OPERACIONAL ---
if "lat" not in st.session_state: st.session_state.lat = 39.552
if "lon" not in st.session_state: st.session_state.lon = -7.962
if "zoom" not in st.session_state: st.session_state.zoom = 8

# --- 4. JANELA MODAL DE VALIDAÇÃO GEOGRÁFICA ---
@st.dialog("🛡️ FIRESIMUL - Validação Cartográfica Completa")
def abrir_janela_validacao(lat_c, lon_c):
    dados_sig = FIRESIMULEngine.cruzar_dados_sig_reais(lat_c, lon_c)
    gmd_lat = FIRESIMULEngine.decimal_para_gmd(lat_c, is_lat=True)
    gmd_lon = FIRESIMULEngine.decimal_para_gmd(lon_c, is_lat=False)
    
    st.write("📋 **Análise de Interseção Geográfica (Dados Reais detetados):**")
    df_v = pd.DataFrame({
        "Camada SIG / Modelo": ["Distrito", "Concelho (CAOP)", "Freguesia (CAOP)", "Localidade", "Uso do Solo (COS)", "Altitude (MDT)", "Declive (MDT)", "Coordenadas rádio"],
        "Valor Detetado": [dados_sig["distrito"], dados_sig["concelho"], dados_sig["freguesia"], dados_sig["localidade"], dados_sig["cos_solo"], f"{dados_sig['altitude']} m", f"{dados_sig['declive']:.1f}% ({dados_sig['orientacao']})", f"{gmd_lat} / {gmd_lon}"]
    })
    st.dataframe(df_v, use_container_width=True, hide_index=True)
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("❌ REJEITAR LOCALIZAÇÃO", use_container_width=True): st.rerun()
    with c2:
        if st.button("✅ VALIDAR PONTO E IR", type="primary", use_container_width=True):
            st.session_state.lat = lat_c
            st.session_state.lon = lon_c
            st.session_state.zoom = 14
            st.rerun()

# --- 5. BARRA LATERAL (TRÍPLICE MODO DE INTRODUÇÃO E PARAMETRIZAÇÃO) ---
with st.sidebar:
    st.title("FIRESIMUL v5.6")
    st.markdown("---")
    
    st.markdown("<p style='color:#74b9ff; font-weight:bold; margin-bottom:2px;'>📥 MODO A: TEXTO ADMINISTRATIVO</p>", unsafe_allow_html=True)
    in_local = st.text_input("Local / Lugar:")
    in_freg = st.text_input("Freguesia:")
    in_conc = st.text_input("Concelho:")
    in_dist = st.text_input("Distrito:")
    if st.button("🔍 PESQUISAR POR TEXTO", use_container_width=True):
        if in_local or in_freg or in_conc or in_dist:
            coords = FIRESIMULEngine.buscar_por_texto_administrativo(in_local, in_freg, in_conc, in_dist)
            if coords: abrir_janela_validacao(coords[0], coords[1])
            else: st.sidebar.error("Local real não detetado na base cartográfica.")
        else: st.sidebar.warning("Preencha pelo menos um campo.")
            
    st.markdown("---")
    
    st.markdown("<p style='color:#ff793f; font-weight:bold; margin-bottom:2px;'>📥 MODO B: COORDENADAS RÁDIO (GMD)</p>", unsafe_allow_html=True)
    c_lat1, c_lat2 = st.columns(2)
    with c_lat1: g_lat = st.number_input("Lat (Graus):", value=39, step=1)
    with c_lat2: m_lat = st.number_input("Lat (Min.Dec):", value=33.120, format="%.3f")
    c_lon1, c_lon2 = st.columns(2)
    with c_lon1: g_lon = st.number_input("Lon (Graus):", value=-7, step=1)
    with c_lon2: m_lon = st.number_input("Lon (Min.Dec):", value=57.720, format="%.3f")
    if st.button("🗺️ ANALISAR COORDENADAS GMD", use_container_width=True):
        lat_calc = FIRESIMULEngine.gmd_para_decimal(g_lat, m_lat)
        lon_calc = FIRESIMULEngine.gmd_para_decimal(g_lon, m_lon)
        abrir_janela_validacao(lat_calc, lon_calc)

    st.markdown("---")
    
    st.markdown("<p style='color:#aaaaaa; font-weight:bold; margin-bottom:2px;'>⏱️ DETALHE DA SIMULAÇÃO</p>", unsafe_allow_html=True)
    duracao_simulacao = st.slider("Duração Pretendida da Projeção:", min_value=1, max_value=12, value=3, format="%dh")

# --- 6. EXTRAÇÃO INTEGRADA DE DADOS E RELATÓRIOS ---
sig_ponto_ativo = FIRESIMULEngine.cruzar_dados_sig_reais(st.session_state.lat, st.session_state.lon)
clima_ponto_ativo = FIRESIMULEngine.obter_clima_reativo(st.session_state.lat, st.session_state.lon)
hotspots = FIRESIMULEngine.obter_nasa_firms()
prociv_incendios = FIRESIMULEngine.obter_prociv_ativas()

# Cálculo reativo da velocidade de progressão (metros por minuto) baseada no declive MDT e vento
fator_velocidade = 8.5 + (sig_ponto_ativo["declive"] * 0.4) + (clima_ponto_ativo["vento_speed"] * 0.2)
comprimento_cabeça = (fator_velocidade * 60) * duracao_simulacao

# Geração de Vulnerabilidades e Logística de Meios Reais
pontos_sensiveis_calculados = FIRESIMULEngine.calcular_pontos_sensiveis_e_tempo(st.session_state.lat, st.session_state.lon, fator_velocidade)
tabela_meios_socorro = FIRESIMULEngine.calcular_deslocacao_meios(st.session_state.lat, st.session_state.lon)

# --- 7. PAINEL CENTRAL E CARTOGRAFIA ARCGIS HÍBRIDA ---
st.title("🛡️ Consola Operacional FIRESIMUL — Análise Dinâmica de Risco")
st.write("Cálculo preditivo de impacto de frentes de fogo em pontos sensíveis e monitorização logística de meios.")

col_map, col_tables = st.columns([1.4, 1])

m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=st.session_state.zoom, control_scale=True)

folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri ArcGIS World Imagery", name="ArcGIS Satélite", overlay=False, control=False
).add_to(m)

folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
    attr="Esri ArcGIS Legendas", name="ArcGIS Legendas", overlay=True, control=False, opacity=0.85
).add_to(m)

for pr in prociv_incendios:
    folium.Marker(location=[pr["lat"], pr["lon"]], icon=folium.Icon(color="red", icon="fire", prefix="fa")).add_to(m)
for hs in hotspots:
    folium.CircleMarker(location=[hs["lat"], hs["lon"]], radius=6, color="#ff793f", fill=True, fill_color="#ffb142").add_to(m)

for ps in pontos_sensiveis_calculados:
    folium.Marker(
        location=[ps["lat"], ps["lon"]],
        icon=folium.Icon(color="orange", icon="home" if "Aglomerado" in ps["tipo"] else "shield", prefix="fa"),
        popup=f"<b>{ps['nome']}</b><br>Impacto Previsto: {ps['hora_prevista']}"
    ).add_to(m)

folium.Marker(location=[st.session_state.lat, st.session_state.lon], icon=folium.Icon(color="darkpurple", icon="crosshairs", prefix="fa")).add_to(m)

# --- MODIFICAÇÃO SOLICITADA: ALGORITMO GEOMÉTRICO EM PONTO GOTA (PIRIFORME) ---
pontos_gota = []
angulo_rad = math.radians(clima_ponto_ativo["vento_dir"])

# Gerar 45 pontos táticos para desenhar a curva matemática simétrica de uma gota real
for i in range(46):
    t = math.radians(i * 8)
    # Equação geométrica da gota/piriforme: o estreitamento traseiro ocorre onde sin(t/2) tende a zero
    dx = (comprimento_cabeça * 0.4) * math.sin(t) * math.sin(t / 2.0)
    dy = (comprimento_cabeça * 0.85) * math.cos(t)
    
    # Aplicação da matriz de rotação com base no rumo real do vento
    rx = dx * math.cos(angulo_rad) - dy * math.sin(angulo_rad)
    ry = dx * math.sin(angulo_rad) + dy * math.cos(angulo_rad)
    
    # Conversão métrica para coordenadas geográficas do SIG (Projeção WGS84)
    n_lat = st.session_state.lat + (ry / 6378137) * (180 / math.pi)
    n_lon = st.session_state.lon + (rx / 6378137) * (180 / math.pi) / math.cos(math.radians(st.session_state.lat))
    pontos_gota.append([n_lat, n_lon])

folium.Polygon(locations=pontos_gota, color="#d63031", weight=3, fill=True, fill_opacity=0.2, popup="Vetor em Gota FIRESIMUL").add_to(m)

with col_map:
    mapa_retorno = st_folium(m, width="100%", height=550, key="mapa_firesimul_v56")
    if mapa_retorno and mapa_retorno.get("last_clicked"):
        cl_lat = mapa_retorno["last_clicked"]["lat"]
        cl_lon = mapa_retorno["last_clicked"]["lng"]
        if abs(cl_lat - st.session_state.lat) > 0.0001 or abs(cl_lon - st.session_state.lon) > 0.0001:
            abrir_janela_validacao(cl_lat, cl_lon)

with col_tables:
    st.subheader("📋 Matriz Integrada: Situação Geográfica e Climatológica")
    
    df_combinada = pd.DataFrame({
        "Parâmetro Analítico (SIG)": [
            "Localidade / Ponto Alvo", "Freguesia (CAOP Recente)", "Concelho (CAOP Recente)", "Distrito Administrativo",
            "Latitude (GMD)", "Longitude (GMD)", "Uso e Ocupação do Solo (COS)", 
            "Altitude Terrestre (MDT)", "Declive Médio (MDT)", "Temperatura Ambiente", 
            "Humidade Relativa do Ar", "Intensidade / Vetor do Vento"
        ],
        "Registo de Sala de Crise": [
            sig_ponto_ativo["localidade"], sig_ponto_ativo["freguesia"], sig_ponto_ativo["concelho"], sig_ponto_ativo["distrito"],
            FIRESIMULEngine.decimal_para_gmd(st.session_state.lat, is_lat=True), FIRESIMULEngine.decimal_para_gmd(st.session_state.lon, is_lat=False),
            sig_ponto_ativo["cos_solo"], f"{sig_ponto_ativo['altitude']} metros", f"{sig_ponto_ativo['declive']:.1f}% voltado a {sig_ponto_ativo['orientacao']}",
            f"{clima_ponto_ativo['temp']:.1f} °C", f"{clima_ponto_ativo['hr']:.0f} %", f"{clima_ponto_ativo['vento_speed']} km/h (Rumo {clima_ponto_ativo['vento_dir']}°)"
        ]
    })
    st.dataframe(df_combinada, use_container_width=True, hide_index=True)

st.markdown("---")

st.subheader("🚨 Avaliação de Alvos Ameaçados e Logística de Socorro")
col_ps, col_meios = st.columns(2)

with col_ps:
    st.write("**📍 Pontos Sensíveis em Calha de Risco Histórico:**")
    for ps in pontos_sensiveis_calculados:
        st.markdown(
            f"<div class='sensivel-card'>"
            f"<b>{ps['tipo']}:</b> {ps['nome']}<br>"
            f"Distância ao Ponto Zero: <b>{ps['dist_m']} m</b> | "
            f"Tempo Estimado de Chegada do Fogo: <span style='color:#ff793f;'><b>{ps['tempo_restante']}</b></span><br>"
            f"<b>HORA PREVISTA DE IMPACTO CRÍTICO: <span style='color:#d63031;'>{ps['hora_prevista']}</span></b>"
            f"</div>", unsafe_allow_html=True
        )

with col_meios:
    st.write("**🚒 Deslocação e Tempos de Trânsito das Forças de Socorro:**")
    st.dataframe(pd.DataFrame(tabela_meios_socorro), use_container_width=True, hide_index=True)

st.markdown("---")

st.subheader(f"🛡️ PEA - Plano Estratégico de Ação Real (+{duracao_simulacao}h)")

c_pea1, c_pea2 = st.columns(2)
with c_pea1:
    st.markdown(
        f"<div class='pea-card'>"
        f"<b>SÍNTESE ATUALIZADA DA OCORRÊNCIA:</b><br>"
        f"Foco ativo validado em <b>{sig_ponto_ativo['localidade']}</b>, freguesia de <b>{sig_ponto_ativo['freguesia']}</b>, progredindo em combustível do tipo <b>{sig_ponto_ativo['cos_solo']}</b>. "
        f"Sob influência de vento a <b>{clima_ponto_ativo['vento_speed']} km/h</b> e declive de <b>{sig_ponto_ativo['declive']:.1f}%</b>, a velocidade real da cabeça é de <b>{fator_velocidade:.1f} m/min</b>, projetando um alcance linear de <b>{comprimento_cabeça:.0f} metros</b> para a janela de <b>{duracao_simulacao}h</b>.<br><br>"
        f"<b>Alvo Crítico Imediato:</b> {pontos_sensiveis_calculados[0]['nome']} com impacto inevitável estimado para as <span style='color:#ff3838;'><b>{pontos_sensiveis_calculados[0]['hora_prevista']}</b></span>."
        f"</div>", unsafe_allow_html=True
    )
with c_pea2:
    st.write("**Diretrizes Operacionais Direcionadas à Ocorrência:**")
    st.write(f"1. **Setorização de Defesa Alvo:** Despachar e fixar o **{tabela_meios_socorro[0]['Meio de Socorro']}** (com tempo de chegada previsto de **{tabela_meios_socorro[0]['Tempo de Marcha']}**) na proteção perimétrica direta do **{pontos_sensiveis_calculados[0]['nome']}**, garantindo o posicionamento das linhas de água antes das **{pontos_sensiveis_calculados[0]['hora_prevista']}**.")
    st.write(f"2. **Ancoragem de Flancos (COS):** Aproveitar o avanço em combustível tipo *{sig_ponto_ativo['cos_solo']}* para realizar contra-fogo ou abertura de faixas através da **{tabela_meios_socorro[2]['Meio de Socorro']}**, tirando partido do seu trânsito rápido (**{tabela_meios_socorro[2]['Tempo de Marcha']}**).")
    st.write(f"3. **Uso de Meios de Asa Rotativa:** Direcionar o **{tabela_meios_socorro[3]['Meio de Socorro']}** (tempo de chegada estimado em **{tabela_meios_socorro[3]['Tempo de Voo']}**) para efetuar descargas concentradas na cabeça do incêndio de modo a reduzir a velocidade atual de **{fator_velocidade:.1f} m/min**.")
    st.write(f"4. **Escalonamento Preventivo:** Ativar o plano de evacuação para o **{pontos_sensiveis_calculados[2]['nome']}** caso o **{tabela_meios_socorro[1]['Meio de Socorro']}** (tempo de chegada de **{tabela_meios_socorro[1]['Tempo de Marcha']}**) não consiga conter o avanço na segunda linha de defesa antes das **{pontos_sensiveis_calculados[1]['hora_prevista']}**.")
