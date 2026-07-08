
import streamlit as st
import requests
from streamlit_folium import st_folium
import folium
import pandas as pd
from datetime import datetime, timedelta
import math

# --- CONFIGURAÇÃO DO AMBIENTE SIG ---
st.set_page_config(
    page_title="FIRE SIMUL",
    page_icon="🗺️",
    layout="wide"
)

# Estilo Escuro Tático (FEB Monitorização UI)
st.markdown("""
    <style>
    .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 12px; border-radius: 6px; }
    .status-card { padding: 12px; border-radius: 6px; margin-bottom: 8px; border: 1px solid #30363d; background-color: #161b22; }
    .sig-badge { background-color: #21262d; border: 1px solid #c9d1d9; color: #c9d1d9; padding: 2px 6px; border-radius: 4px; font-size: 11px; }
    </style>
""", unsafe_allow_html=True)

# --- CONECTOR DE BASES DE DADOS GEOGRÁFICAS OFICIAIS ---
class ConectorBasesDadosPortugal:
    
    # Dicionário Operacional baseado estritamente na nomenclatura da COS (DGT)
    # Carga de combustível (t/ha), Altura média (m), Velocidade base (m/min)
    DICIONARIO_COS = {
        1: {"nome": "COS 3.1.1 - Floresta de Folhosas (Eucaliptal/Carvalhal)", "carga": 11.5, "altura": 12.0, "r_base": 0.75},
        2: {"nome": "COS 3.1.2 - Floresta de Coníferas (Pinhal Marítimo)", "carga": 14.0, "altura": 10.0, "r_base": 0.60},
        3: {"nome": "COS 3.2.2 - Matos e Formações Arbustivas Densas", "carga": 18.5, "altura": 1.8, "r_base": 1.30},
        4: {"nome": "COS 2.1.1 - Culturas Arvenses Sequeiro (Pasto Seco)", "carga": 2.5, "altura": 0.4, "r_base": 1.80},
        5: {"nome": "COS 3.1.3 - Floresta Mista (Folhosas e Coníferas)", "carga": 12.8, "altura": 11.0, "r_base": 0.68}
    }

    @staticmethod
    def consultar_caop_local(lat, lon):
        """
        Em ambiente de produção, este método consome o servidor WFS da DGT para a CAOP.
        Retorna a hierarquia político-administrativa exata do Ponto Zero.
        """
        # Simulação de intersecção espacial da geometria CAOP
        return {
            "Distrito": "Santarém",
            "Concelho": "Mação",
            "Freguesia": "Ortiga",
            "Dicofre": "141303",
            "Versao_CAOP": "2024/2025"
        }

    @staticmethod
    def extrair_mdt_ponto(lat, lon):
        """
        Interseção com o Modelo Digital do Terreno (MDT) de resolução de 10 metros.
        Calcula a altimetria, a inclinação (declive) e a orientação da vertente (aspeto).
        """
        # Simulação de leitura de pixel do Raster MDT
        declive_graus = 24.5  # Ângulo de inclinação da encosta
        aspeto_graus = 135    # Vertente exposta a Sudeste (SE)
        altitude_m = 285      # Altitude face ao nível médio das águas do mar
        return declive_graus, aspeto_graus, altitude_m

    @staticmethod
    def obter_arome_horario():
        agora = datetime.now()
        return {
            "T0": {"tempo": agora.strftime("%H:%M"), "vento": 26.0, "dir": 315, "temp": 33.0, "rh": 22.0},
            "T1": {"tempo": (agora + timedelta(hours=1)).strftime("%H:%M"), "vento": 29.0, "dir": 320, "temp": 34.2, "rh": 19.0},
            "T2": {"tempo": (agora + timedelta(hours=2)).strftime("%H:%M"), "vento": 34.0, "dir": 330, "temp": 34.8, "rh": 17.0}
        }

# --- MOTOR DE PROPAGAÇÃO DO FOGO OPERACIONAL ---
class MotorPropagacaoSIG:
    @classmethod
    def resolver_rothermel_sig(cls, classe_cos, vento_kmh, temp, rh, declive, dir_vento, aspeto_encosta):
        dados_cos = ConectorBasesDadosPortugal.DICIONARIO_COS.get(classe_cos, {"carga": 5.0, "r_base": 0.5})
        
        # 1. Humidade Equivalente dos Combustíveis Finos Mortos (M_f)
        m_f = 12.0 * (rh / 50.0) - (temp * 0.1)
        f_humidade = math.exp(-0.20 * max(m_f, 2.0))
        
        # 2. Fator de Vento Vetorial ($\phi_w$)
        f_vento = math.exp(0.045 * vento_kmh)
        
        # 3. Fator Orogáfico do MDT ($\phi_s$)
        # Alinhamento entre o rumo do vento e a direção de subida da encosta
        alinhamento = math.cos(math.radians((dir_vento + 180) - aspeto_encosta))
        if alinhamento > 0:
            f_declive = math.exp(0.072 * declive) * alinhamento
        else:
            f_declive = math.exp(-0.04 * declive)
            
        # Velocidade Final da Frente ($R$)
        R = dados_cos["r_base"] * f_humidade * f_vento * f_declive
        R = max(R, 0.1)
        
        # Intensidade de Byram (I) e Comprimento da Chama (L)
        I = 18000 * (dados_cos["carga"] / 10.0) * (R / 60.0)
        chama = 0.0775 * (I ** 0.46)
        
        return R, I, chama

    @staticmethod
    def calcular_vetor_coordenadas(lat, lon, distancia_m, dir_vento):
        pontos = [[lat, lon]]
        dir_propagacao = dir_vento + 180
        
        for i in range(25):
            f = i / 24.0
            angulo_rad = math.radians(dir_propagacao - 45 + (f * 90))
            fator_forma = 1.0 - 0.55 * abs(f - 0.5) * 2  # Morfologia parabólica
            
            dx = (distancia_m * fator_forma) * math.sin(angulo_rad)
            dy = (distancia_m * fator_forma) * math.cos(angulo_rad)
            
            n_lat = lat + (dy / 6378137) * (180 / math.pi)
            n_lon = lon + (dx / 6378137) * (180 / math.pi) / math.cos(math.radians(lat))
            pontos.append([n_lat, n_lon])
            
        pontos.append([lat, lon])
        return pontos

# --- GRAPHICAL USER INTERFACE ---
st.title("🚒 FEB Monitorização — Painel Avançado SIG (CAOP / MDT / COS)")
st.write("Fusiamento em tempo real de Sistemas de Informação Geográfica e Modelos de Comportamento do Fogo.")

# Configuração de Sessão Estável
if "lat" not in st.session_state: st.session_state.lat = 39.552
if "lon" not in st.session_state: st.session_state.lon = -7.962
if "zoom" not in st.session_state: st.session_state.zoom = 7

col_mapa, col_dados = st.columns([1.4, 1])

# Inicialização da Carta Tática Base
m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=st.session_state.zoom)
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri World Imagery", name="Satélite Alta Definição"
).add_to(m)
m.add_child(folium.LatLngPopup())

# Plotar Marcador Principal do Teatro de Operações
folium.Marker(location=[st.session_state.lat, st.session_state.lon], icon=folium.Icon(color="darkred", icon="crosshairs")).add_to(m)

with col_dados:
    st.subheader("🌲 Classificação de Cobertura de Solo (COS)")
    cos_id = st.selectbox(
        "Código/Classe COS detetada pelo Satélite:", 
        options=[1, 2, 3, 4, 5],
        format_func=lambda x: ConectorBasesDadosPortugal.DICIONARIO_COS[x]["nome"]
    )
    
    st.subheader("⏱️ Configuração Temporal")
    janela_horas = st.slider("Duração do Cenário de Projeção (Horas):", 1, 8, 3)

# --- EXECUÇÃO DO SOLVER COMPUTACIONAL ---
caop = ConectorBasesDadosPortugal.consultar_caop_local(st.session_state.lat, st.session_state.lon)
declive, aspeto, altitude = ConectorBasesDadosPortugal.extrair_mdt_ponto(st.session_state.lat, st.session_state.lon)
series_meteo = ConectorBasesDadosPortugal.obter_arome_horario()

tabela_operacional = []
dist_acumulada = 0.0
escala_cores = ["#f1c40f", "#e67e22", "#e74c3c", "#9b59b6"]

for idx, (chave, dados) in enumerate(series_meteo.items()):
    if idx >= janela_horas: break
    
    # Resolver comportamento mecânico do passo
    R, I, chama = MotorPropagacaoSIG.resolver_rothermel_sig(
        cos_id, dados["vento"], dados["temp"], dados["rh"], declive, dados["dir"], aspeto
    )
    
    dist_acumulada += (R * 60.0)
    perimetro_geo = MotorPropagacaoSIG.calcular_vetor_coordenadas(st.session_state.lat, st.session_state.lon, dist_acumulada, dados["dir"])
    
    # Desenhar Isócronas de Avanço no Mapa
    folium.Polygon(
        locations=perimetro_geo,
        color=escala_cores[idx % len(escala_cores)],
        weight=2.5,
        fill=True,
        fill_opacity=0.18,
        popup=f"Isócrona de Avanço: {dados['tempo']}"
    ).add_to(m)
    
    tabela_operacional.append({
        "Janela": chave,
        "Hora": dados["tempo"],
        "Vento Real": f"{dados['vento']} km/h",
        "Taxa R": f"{R:.2f} m/min",
        "Chama (L)": f"{chama:.1f} m",
        "Alcance Projeção": f"{dist_acumulada:.0f} m"
    })

# --- RENDERIZAÇÃO DOS PAINÉIS DE INFORMAÇÃO ---
with col_mapa:
    mapa_retorno = st_folium(m, width="100%", height=580)
    if mapa_retorno and mapa_retorno.get("last_clicked"):
        novo_clique = (mapa_retorno["last_clicked"]["lat"], mapa_retorno["last_clicked"]["lng"])
        if novo_clique != (st.session_state.lat, st.session_state.lon):
            st.session_state.lat = novo_clique[0]
            st.session_state.lon = novo_clique[1]
            st.session_state.zoom = 15
            st.rerun()

with col_dados:
    st.subheader("📋 Cruzamento de Dados Espaciais e Geográficos")
    
    # Bloco 1: Validação Administrativa CAOP
    st.markdown(
        f"<div class='status-card' style='border-left: 4px solid #3498db;'>"
        f"<b>📍 Georreferenciação CAOP:</b> {caop['Distrito']} &rarr; {caop['Concelho']} &rarr; {caop['Freguesia']}<br>"
        f"<span class='sig-badge'>DICOFRE: {caop['Dicofre']}</span> <span class='sig-badge'>Base Oficial: {caop['Versao_CAOP']}</span>"
        f"</div>", unsafe_allow_html=True
    )
    
    # Bloco 2: Telemetria Topográfica MDT
    st.markdown(
        f"<div class='status-card' style='border-left: 4px solid #2ecc71;'>"
        f"<b>⛰️ Geomorfologia MDT (Resolução 10m):</b><br>"
        f"Altitude: {altitude} m | Inclinação Encosta: {declive}° | Orientação da Vertente: {aspeto}° (SE)"
        f"</div>", unsafe_allow_html=True
    )
    
    # Bloco 3: Tabela de Saída do Motor Computacional
    st.dataframe(pd.DataFrame(tabela_operacional), use_container_width=True, hide_index=True)
