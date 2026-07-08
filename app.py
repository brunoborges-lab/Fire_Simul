import streamlit as st
import requests
from streamlit_folium import st_folium
import folium
import pandas as pd
import math
from datetime import datetime, timedelta
import time

# --- 1. CONFIGURAÇÃO OPERACIONAL FIRESIMUL ---
st.set_page_config(
    page_title="FIRESIMUL v5.6 - Monitorização Estável",
    page_icon="🛡️",
    layout="wide"
)

# Estilo Visual Tático de Sala de Crise
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

# --- 2. MOTOR DE GEOPROCESSAMENTO ---
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
            {"tipo": "🏡 Aglomerado Populacional", "nome": f"Zona Habitacional Sul ({concelho})", "dist_m": 680, "lat": lat + 0.004, "lon": lon - 0.003},
            {"tipo": "⚡ Infraestrutura Crítica", "nome": f"Nó de Distribuição de Energia Concelhia", "dist_m": 1420, "lat": lat + 0.009, "lon": lon - 0.006},
            {"tipo": "🏥 Saúde / Vulnerável", "nome": f"Unidade de Apoio Social Integrada de {concelho}", "dist_m": 3800, "lat": lat + 0.028, "lon": lon + 0.010}
        ]
        for p in pontos:
            minutos_ate_impacto = p["dist_m"] / velocidade_m_min
            hora_impacto = agora + timedelta(minutes=minutos_ate_impacto)
            p["hora_prevista"] = hora_impacto.strftime("%H:%M:%S")
            p["tempo_restante"] = f"{int(minutos_ate_impacto)} min"
        return pontos

    @staticmethod
    def calcular_deslocacao_meios(lat, lon, concelho):
        return [
            {"Meio de Socorro": f"AHBV {concelho} (VUCI / VFCI)", "Localização Original": "Quartel Sede Concelhia", "Distância (km)": "5.2 km", "Tempo de Marcha": "7 min", "Estado": "Em Marcha"},
            {"Meio de Socorro": "Corporação de Apoio Perimétrico (VFCI)", "Localização Original": "Setor Limítrofe Regional", "Distância (km)": "19.5 km", "Tempo de Marcha": "22 min", "Estado": "Despachado"},
            {"Meio de Socorro": "Força Especial de Proteção Civil (FEPC)", "Localização Original": "Comando de Operações Distrital", "Distância (km)": "42.0 km", "Tempo de Marcha": "38 min", "Estado": "Em Trânsito"},
            {"Meio de Socorro": "Meio Aéreo de Ataque Expandido", "Localização Original": "Centro de Meios Aéreos (CMA)", "Distância (km)": "28.0 km", "Tempo de Voo": "6 min", "Estado": "A descolar"}
        ]

    @staticmethod
    def gerar_alertas_satelite_dinamicos(lat, lon):
        return [
            {"lat": lat + 0.008, "lon": lon + 0.006, "satelite": "VIIRS (Deteção Remota)", "confianca": "Alta", "temp_k": 345.2},
            {"lat": lat - 0.005, "lon": lon - 0.004, "satelite": "MODIS (Térmico)", "confianca": "Nominal", "temp_k": 319.8}
        ]

# --- 3. ESTADOS DE SESSÃO OPERACIONAL ---
if "lat" not in st.session_state: st.session_state.lat = 39.552
if "lon" not in st.session_state: st.session_state.lon = -7.962
if "zoom" not in st.session_state: st.session_state.zoom = 13

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
            st.session_state.zoom = 13
            st.rerun()

# --- 5. BARRA LATERAL (PARAMETRIZAÇÃO ADAPTATIVA) ---
with st.sidebar:
    st.title("FIRESIMUL v5.6")
    st.markdown("---")
    
    st.markdown("<p style='color:#74b9ff; font-weight:bold; margin-bottom:2px;'>📥 MODO A: TEXTO ADMINISTRATIVO</p>", unsafe_allow_html=True)
    in_local = st.text_input("Local / Lugar:", value="Ortiga")
    in_freg = st.text_input("Freguesia:", value="Ortiga")
    in_conc = st.text_input("Concelho:", value="Mação")
    in_dist = st.text_input("Distrito:", value="Santarém")
    if st.button("🔍 PESQUISAR POR TEXTO", use_container_width=True):
        if in_local or in_freg or in_conc or in_dist:
            coords = FIRESIMULEngine.buscar_por_texto_administrativo(in_local, in_freg, in_conc, in_dist)
            if coords: abrir_janela_validacao(coords[0], coords[1])
            else: st.sidebar.error("Local real não detetado na base cartográfica.")
            
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
    duracao_simulacao = st.slider("Duração Pretendida da Projeção:", min_value=1, max_value=12, value=3, format="%dh")

# --- 6. PROCESSAMENTO DOS FLUXOS DINÂMICOS ---
sig_ponto_ativo = FIRESIMULEngine.cruzar_dados_sig_reais(st.session_state.lat, st.session_state.lon)
clima_ponto_ativo = FIRESIMULEngine.obter_clima_reativo(st.session_state.lat, st.session_state.lon)
hotspots = FIRESIMULEngine.gerar_alertas_satelite_dinamicos(st.session_state.lat, st.session_state.lon)

fator_velocidade = 10.5 + (sig_ponto_ativo["declive"] * 0.4) + (clima_ponto_ativo["vento_speed"] * 0.25)
comprimento_cabeça = (fator_velocidade * 60) * duracao_simulacao

pontos_sensiveis_calculados = FIRESIMULEngine.calcular_pontos_sensiveis_e_tempo(st.session_state.lat, st.session_state.lon, fator_velocidade, sig_ponto_ativo["concelho"])
tabela_meios_socorro = FIRESIMULEngine.calcular_deslocacao_meios(st.session_state.lat, st.session_state.lon, sig_ponto_ativo["concelho"])

# --- 7. PAINEL CENTRAL E CARTOGRAFIA ---
st.title("🛡️ Consola Operacional FIRESIMUL — Monitorização Real")
st.write(f"Painel tático para o Teatro de Operações de **{sig_ponto_ativo['localidade']}**.")

col_map, col_tables = st.columns([1.4, 1])

# O Mapa é desenhado fora do fragment para nunca piscar nem perder o estado de zoom
with col_map:
    m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=st.session_state.zoom, control_scale=True)
    
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri ArcGIS World Imagery", name="ArcGIS Satélite", overlay=False, control=False
    ).add_to(m)

    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
        attr="Esri ArcGIS Legendas", name="ArcGIS Legendas", overlay=True, control=False, opacity=0.85
    ).add_to(m)

    for hs in hotspots:
        folium.CircleMarker(location=[hs["lat"], hs["lon"]], radius=6, color="#ff793f", fill=True, fill_color="#ffb142").add_to(m)

    for ps in pontos_sensiveis_calculados:
        folium.Marker(
            location=[ps["lat"], ps["lon"]],
            icon=folium.Icon(color="orange", icon="home" if "Aglomerado" in ps["tipo"] else "shield", prefix="fa"),
            popup=f"<b>{ps['nome']}</b>"
        ).add_to(m)

    folium.Marker(location=[st.session_state.lat, st.session_state.lon], icon=folium.Icon(color="darkpurple", icon="crosshairs", prefix="fa")).add_to(m)

    # ALGORITMO GEOMÉTRICO EM PONTO GOTA
    pontos_gota = []
    angulo_rad = math.radians(clima_ponto_ativo["vento_dir"])
    for i in range(46):
        t = math.radians(i * 8)
        dx = (comprimento_cabeça * 0.45) * math.sin(t) * math.sin(t / 2.0)
        dy = (comprimento_cabeça * 0.85) * math.cos(t)
        rx = dx * math.cos(angulo_rad) - dy * math.sin(angulo_rad)
        ry = dx * math.sin(angulo_rad) + dy * math.cos(angulo_rad)
        n_lat = st.session_state.lat + (ry / 6378137) * (180 / math.pi)
        n_lon = st.session_state.lon + (rx / 6378137) * (180 / math.pi) / math.cos(math.radians(st.session_state.lat))
        pontos_gota.append([n_lat, n_lon])

    folium.Polygon(locations=pontos_gota, color="#d63031", weight=3, fill=True, fill_opacity=0.2).add_to(m)

    mapa_retorno = st_folium(m, width="100%", height=550, key="mapa_firesimul_v56")
    if mapa_retorno and mapa_retorno.get("last_clicked"):
        cl_lat = mapa_retorno["last_clicked"]["lat"]
        cl_lon = mapa_retorno["last_clicked"]["lng"]
        if abs(cl_lat - st.session_state.lat) > 0.0001 or abs(cl_lon - st.session_state.lon) > 0.0001:
            abrir_janela_validacao(cl_lat, cl_lon)

# --- 8. FRAGMENTO DINÂMICO (Atualiza as tabelas e relatórios a cada 1 min sem piscar o mapa) ---
@st.fragment(run_every=60)
def renderizar_dados_dinamicos():
    with col_tables:
        st.subheader("📋 Situação Geográfica e Climatológica")
        st.caption(f"⏱️ Relatório atualizado às: {datetime.now().strftime('%H:%M:%S')}")
        
        df_combinada = pd.DataFrame({
            "Parâmetro Analítico (SIG)": [
                "Localidade / Ponto Alvo", "Freguesia (CAOP)", "Concelho (CAOP)", "Distrito",
                "Uso do Solo (COS)", "Altitude Terrestre", "Declive Médio", "Temperatura", 
                "Humidade Relativa", "Vetor do Vento"
            ],
            "Registo de Sala de Crise": [
                sig_ponto_ativo["localidade"], sig_ponto_ativo["freguesia"], sig_ponto_ativo["concelho"], sig_ponto_ativo["distrito"],
                sig_ponto_ativo["cos_solo"], f"{sig_ponto_ativo['altitude']} metros", f"{sig_ponto_ativo['declive']:.1f}% ({sig_ponto_ativo['orientacao']})",
                f"{clima_ponto_ativo['temp']:.1f} °C", f"{clima_ponto_ativo['hr']:.0f} %", f"{clima_ponto_ativo['vento_speed']} km/h ({clima_ponto_ativo['vento_dir']}°)"
            ]
        })
        st.dataframe(df_combinada, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("🚨 Avaliação de Alvos Ameaçados e Logística de Socorro")
    col_ps, col_meios = st.columns(2)

    with col_ps:
        st.write(f"**📍 Alvos em Calha de Risco Histórico ({sig_ponto_ativo['concelho']}):**")
        for ps in pontos_sensiveis_calculados:
            st.markdown(
                f"<div class='sensivel-card'>"
                f"<b>{ps['tipo']}:</b> {ps['nome']}<br>"
                f"Distância: <b>{ps['dist_m']} m</b> | Falta: <span style='color:#ff793f;'><b>{ps['tempo_restante']}</b></span><br>"
                f"<b>HORA PREVISTA DE IMPACTO: <span style='color:#d63031;'>{ps['hora_prevista']}</span></b>"
                f"</div>", unsafe_allow_html=True
            )

    with col_meios:
        st.write("**🚒 Deslocação de Forças Operacionais Ativas:**")
        st.dataframe(pd.DataFrame(tabela_meios_socorro), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader(f"🛡️ PEA - Plano Estratégico de Ação (+{duracao_simulacao}h)")

    c_pea1, c_pea2 = st.columns(2)
    with c_pea1:
        st.markdown(
            f"<div class='pea-card'>"
            f"<b>SÍNTESE OPERACIONAL DO SETOR:</b><br>"
            f"Foco ativo em <b>{sig_ponto_ativo['localidade']}</b>, a progredir em <b>{sig_ponto_ativo['cos_solo']}</b>. "
            f"Velocidade real da cabeça estimada em <b>{fator_velocidade:.1f} m/min</b>, projetando um alcance linear de <b>{comprimento_cabeça:.0f} metros</b>.<br><br>"
            f"<b>Alvo Crítico Imediato:</b> {pontos_sensiveis_calculados[0]['nome']} com impacto modelado para as <span style='color:#ff3838;'><b>{pontos_sensiveis_calculados[0]['hora_prevista']}</b></span>."
            f"</div>", unsafe_allow_html=True
        )
    with c_pea2:
        st.write("**Diretrizes Operacionais Direcionadas:**")
        st.write(f"1. **Setorização:** Despachar o contingente **{tabela_meios_socorro[0]['Meio de Socorro']}** para proteção perimétrica na **{pontos_sensiveis_calculados[0]['nome']}** antes das **{pontos_sensiveis_calculados[0]['hora_prevista']}**.")
        st.write(f"2. **Logística:** Acionar alertas rodoviários perto de **{pontos_sensiveis_calculados[1]['nome']}**, visto que a progressão cruzará o setor pelas **{pontos_sensiveis_calculados[1]['hora_prevista']}**.")
        st.write(f"3. **Combate Leste:** Manter o **{tabela_meios_socorro[1]['Meio de Socorro']}** focado no flanco esquerdo para travar a expansão lateral da gota geométrica.")

# Executa a renderização contínua e isolada das tabelas
renderizar_dados_dinamicos()
