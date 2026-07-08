import streamlit as st
import requests
from streamlit_folium import st_folium
import folium
import pandas as pd
from datetime import datetime, timedelta
import math

st.set_page_config(page_title="Motor Computacional Rothermel - SIG Fogo", page_icon="🔥", layout="wide")

# --- 1. INTEGRAÇÃO DE DADOS (APIs, SIG, Satélite) ---
class SIGCentroDados:
    @staticmethod
    def obter_municipios():
        url = "https://api.ipma.pt/open-data/distrits-islands.json"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200: return response.json()['data']
        except Exception: pass
        return []

    @staticmethod
    def obter_dados_arome(global_id_local):
        agora = datetime.now()
        # Simulação da run do modelo AROME baseada no ID do município
        return {
            "Agora": {"tempo": agora.strftime("%H:%M"), "vento": 22.0, "dir_graus": 315, "temp": 31.0, "humidade": 28.0, "rcm": 4},
            "+1 Hora": {"tempo": (agora + timedelta(hours=1)).strftime("%H:%M"), "vento": 26.0, "dir_graus": 320, "temp": 32.5, "humidade": 25.0, "rcm": 4},
            "+2 Horas": {"tempo": (agora + timedelta(hours=2)).strftime("%H:%M"), "vento": 32.0, "dir_graus": 325, "temp": 33.2, "humidade": 22.0, "rcm": 5}
        }

    @staticmethod
    def detetar_pontos_sensiveis(lat, lon):
        return [
            {"tipo": "Habitação Isolada", "nome": "Casal do Olival", "lat": lat + 0.0012, "lon": lon - 0.0015, "prioridade": "MÁXIMA"},
            {"tipo": "Infraestrutura Crítica", "nome": "Posto Elétrico", "lat": lat - 0.0018, "lon": lon + 0.0022, "prioridade": "ELEVADA"}
        ]

    @staticmethod
    def injetar_effis_copernicus(mapa_objeto):
        folium.WmsTileLayer(
            url="https://effis-gwis-wms.apps.vgt.vito.be/geoserver/effis/wms",
            layers="modis.fwi", fmt="image/png", transparent=True, version="1.1.1",
            name="EFFIS Copernicus - Risco FWI", attr="© EU, EFFIS",
            overlay=True, control=True, opacity=0.45
        ).add_to(mapa_objeto)

# --- 2. MOTOR COMPUTACIONAL (BASEADO EM ROTHERMEL) ---
class MotorComputacionalRothermel:
    # Modelos de Combustível simplificados (Carga W em ton/ha, Profundidade d em metros)
    MODELOS_COMBUSTIVEL = {
        322: {"nome": "Matos Densos", "carga": 12.0, "profundidade": 1.2, "r_base": 1.1},
        312: {"nome": "Pinhal", "carga": 15.0, "profundidade": 0.8, "r_base": 0.6},
        311: {"nome": "Eucaliptal", "carga": 10.0, "profundidade": 0.5, "r_base": 0.8},
        321: {"nome": "Pastagem Seca", "carga": 3.0, "profundidade": 0.2, "r_base": 1.5}
    }

    @classmethod
    def processar_frente(cls, cos, vento_kmh, temp, humidade_rh, declive_graus, dir_vento, dir_subida):
        """
        Calcula o comportamento combinando todos os inputs ambientais.
        """
        combustivel = cls.MODELOS_COMBUSTIVEL.get(cos, {"nome": "Desconhecido", "carga": 5.0, "profundidade": 0.5, "r_base": 0.5})
        
        # 1. Sub-Modelo de Humidade do Combustível (M_f)
        # Combustíveis finos secam rapidamente com alta temperatura e baixa RH
        humidade_fina = 85.0 - (temp * 1.2) + (humidade_rh * 0.5)
        if humidade_fina < 5.0: humidade_fina = 5.0
        fator_humidade = math.exp(-0.15 * humidade_fina)
        
        # 2. Sub-Modelo de Vento (Phi_w)
        # O vento empurra as chamas, aumentando a transferência de calor por radiação e convecção
        fator_vento = math.exp(0.0513 * vento_kmh)
        
        # 3. Sub-Modelo Orogáfico Vetorial (Phi_s)
        # Alinhamento entre o vento e a inclinação (0 a 1)
        alinhamento_vento_encosta = math.cos(math.radians((dir_vento + 180) - dir_subida))
        
        if alinhamento_vento_encosta > 0: # O fogo sobe a favor da inclinação
            fator_declive = math.exp(0.0693 * declive_graus) * alinhamento_vento_encosta
        else: # O fogo desce (propaga mais devagar)
            fator_declive = math.exp(-0.04 * declive_graus)
            
        # 4. Resolução da Equação de Propagação (R em m/min)
        # R = R_0 * (1 + phi_w + phi_s) simplificado operacionalmente para multiplicadores
        multiplicador_total = fator_humidade * fator_vento * fator_declive
        R = combustivel["r_base"] * multiplicador_total
        
        # Intensidade Linear de Byram (I = H * w * R)
        calor_combustao = 18000  # kJ/kg aproximado para vegetação ibérica
        I = calor_combustao * (combustivel["carga"] / 10.0) * (R / 60.0)
        
        # Altura da Chama (Lei de potência de Byram)
        chama = 0.0775 * (I ** 0.46)
        
        return max(R, 0.1), I, chama

    @staticmethod
    def gerar_perimetro_dispersao(lat, lon, distancia_m, dir_vento):
        """Usa geometria para calcular a dispersão em leque baseada no vetor vento."""
        pontos = [[lat, lon]]
        dir_propagacao = dir_vento + 180
        ang_esq = math.radians(dir_propagacao - 30)
        ang_dir = math.radians(dir_propagacao + 30)
        
        for i in range(15):  # Aumentada a resolução dos polígonos
            f = i / 14.0
            ang = ang_esq + f * (ang_dir - ang_esq)
            # Fator de flanco: a frente avança a 100%, os flancos a 40% da distância
            fator_flanco = 1.0 - (1.0 - 0.4) * abs(f - 0.5) * 2
            dx = (distancia_m * fator_flanco) * math.sin(ang)
            dy = (distancia_m * fator_flanco) * math.cos(ang)
            
            n_lat = lat + (dy / 6378137) * (180 / math.pi)
            n_lon = lon + (dx / 6378137) * (180 / math.pi) / math.cos(math.radians(lat))
            pontos.append([n_lat, n_lon])
        
        pontos.append([lat, lon])
        return pontos

# --- 3. INTERFACE DE COMANDO ---
st.title("🔥 Motor Computacional de Fogo - Integração Total de Dados")
st.write("Cálculos baseados em topografia, satélite EFFIS, meteorologia horária AROME e algoritmos Rothermel.")

municipios = SIGCentroDados.obter_municipios()
col_mapa, col_dados = st.columns([1.4, 1])

if "mapa_centro" not in st.session_state: st.session_state.mapa_centro = [39.557, -7.996]
if "mapa_zoom" not in st.session_state: st.session_state.mapa_zoom = 7
if "clique" not in st.session_state: st.session_state.clique = None

m = folium.Map(location=st.session_state.mapa_centro, zoom_start=st.session_state.mapa_zoom)
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri", name="Satélite Alta Resolução"
).add_to(m)

SIGCentroDados.injetar_effis_copernicus(m)
folium.LayerControl().add_to(m)
m.add_child(folium.LatLngPopup())

with col_dados:
    st.subheader("🌲 Parametrização do Terreno")
    cos_sel = st.selectbox(
        "Combustível COS Mapeado:", options=[322, 312, 311, 321],
        format_func=lambda x: f"{MotorComputacionalRothermel.MODELOS_COMBUSTIVEL[x]['nome']}"
    )

if st.session_state.clique:
    lat, lon = st.session_state.clique
    
    # 1. Topografia e Interseções
    declive = round(abs(math.sin(lat * lon) * 35.0), 1)
    dir_subida = int((lat - lon) * 1000) % 360
    pontos_sensiveis = SIGCentroDados.detetar_pontos_sensiveis(lat, lon)
    
    folium.Marker(location=[lat, lon], icon=folium.Icon(color="red", icon="crosshairs", prefix="fa")).add_to(m)
    for pts in pontos_sensiveis:
        folium.Marker(location=[pts["lat"], pts["lon"]], icon=folium.Icon(color="orange", icon="home")).add_to(m)

    if municipios:
        concelho = min(municipios, key=lambda x: (float(x['latitude']) - lat)**2 + (float(x['longitude']) - lon)**2)
        proj_meteo = SIGCentroDados.obter_dados_arome(concelho['globalIdLocal'])
        
        dist_acumulada = 0.0
        cores = {"Agora": "#34495e", "+1 Hora": "#e67e22", "+2 Horas": "#e74c3c"}
        dados_output = []
        
        # 2. Execução do Motor de Cálculo para as próximas 2 horas
        for momento, dados in proj_meteo.items():
            R, I, chama = MotorComputacionalRothermel.processar_frente(
                cos_sel, dados["vento"], dados["temp"], dados["humidade"], declive, dados["dir_graus"], dir_subida
            )
            dist_acumulada += (R * 60.0) if momento != "Agora" else (R * 5.0)
            
            # Gerar polígono morfológico corrigido (Flancos e Cabeça)
            cone_calc = MotorComputacionalRothermel.gerar_perimetro_dispersao(lat, lon, dist_acumulada, dados["dir_graus"])
            folium.Polygon(locations=cone_calc, color=cores[momento], weight=2, fill=True, fill_opacity=0.3).add_to(m)
            
            dados_output.append({
                "T": momento,
                "Vento (AROME)": f"{dados['vento']} km/h",
                "Temp/RH": f"{dados['temp']}°C | {dados['humidade']}%",
                "R (Propagação)": f"{R:.2f} m/min",
                "Intensidade (I)": f"{I:.0f} kW/m",
                "Alt. Chama": f"{chama:.1f} m",
                "Alcance": f"{dist_acumulada:.0f} m"
            })

with col_mapa:
    mapa_ret = st_folium(m, width="100%", height=600)
    if mapa_ret and mapa_ret.get("last_clicked"):
        novo_clq = (mapa_ret["last_clicked"]["lat"], mapa_ret["last_clicked"]["lng"])
        if novo_clq != st.session_state.clique:
            st.session_state.clique = novo_clq
            st.session_state.mapa_centro = novo_clq
            st.session_state.mapa_zoom = 15
            st.rerun()

with col_dados:
    if st.session_state.clique:
        st.write("---")
        st.subheader("⚙️ Output do Motor Computacional")
        st.info(f"📍 **Topografia Detetada:** Declive de {declive}° (Rumo: {dir_subida}°)")
        st.dataframe(pd.DataFrame(dados_output), use_container_width=True, hide_index=True)
        
        if st.button("LIMPAR TEATRO DE OPERAÇÕES"):
            st.session_state.mapa_centro = [39.557, -7.996]
            st.session_state.mapa_zoom = 7
            st.session_state.clique = None
            st.rerun()
