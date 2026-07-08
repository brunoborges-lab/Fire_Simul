import streamlit as st
import requests
from streamlit_folium import st_folium
import folium
import pandas as pd
from datetime import datetime, timedelta
import math

# --- CONFIGURAÇÃO INDUSTRIAL FEB ---
st.set_page_config(
    page_title="FEB Monitorização - Simulação Dinâmica Avançada",
    page_icon="⚡",
    layout="wide"
)

st.markdown("""
    <style>
    .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 12px; border-radius: 6px; }
    .status-card { padding: 12px; border-radius: 6px; margin-bottom: 8px; border: 1px solid #30363d; background-color: #161b22; }
    .section-title { color: #ffdd59; font-weight: bold; font-size: 18px; margin-top: 15px; }
    </style>
""", unsafe_allow_html=True)

# --- MOTOR COMPUTACIONAL DE SÉRIES TEMPORAIS ---
class MotorFEBPrevisao:
    MODELOS_COMBUSTIVEL = {
        322: {"nome": "Matos Densos (Urze/Tojo)", "carga": 12.0, "r_base": 1.1},
        312: {"nome": "Pinhal Florestal", "carga": 15.0, "r_base": 0.6},
        311: {"nome": "Eucaliptal Transgénico", "carga": 10.0, "r_base": 0.8},
        321: {"nome": "Pastagem / Erva Seca", "carga": 3.0, "r_base": 1.5}
    }

    @staticmethod
    def simular_curva_meteo_horaria(base_temp, base_rh, base_vento, horas_decorridas):
        """Simula a variação térmica e higrométrica real ao longo do dia (Ciclo Diurno)"""
        # À medida que a tarde avança, a temperatura sobe ligeiramente e a humidade cai
        fator_diurno = math.sin(horas_decorridas * (math.pi / 12))
        temp_atual = base_temp + (2.5 * fator_diurno)
        rh_atual = max(base_rh - (3.0 * fator_diurno), 10.0)
        vento_atual = base_vento + (1.5 * horas_decorridas) # Vento tende a intensificar-se à tarde
        return temp_atual, rh_atual, vento_atual

    @classmethod
    def calcular_passo_propagacao(cls, cos, vento_kmh, temp, humidade_rh, declive, dir_vento, dir_subida):
        comb = cls.MODELOS_COMBUSTIVEL.get(cos, {"carga": 5.0, "r_base": 0.5})
        
        # Equações de influência ambiental
        f_humidade = math.exp(-0.12 * (85.0 - (temp * 1.1) + (humidade_rh * 0.4)))
        f_vento = math.exp(0.048 * vento_kmh)
        
        alinhamento = math.cos(math.radians((dir_vento + 180) - dir_subida))
        f_declive = math.exp(0.065 * declive) * alinhamento if alinhamento > 0 else math.exp(-0.03 * declive)
        
        R = comb["r_base"] * f_humidade * f_vento * f_declive
        R = max(R, 0.1)
        
        # Intensidade de Byram (kW/m) e Linha de Chama
        I = 18000 * (comb["carga"] / 10.0) * (R / 60.0)
        chama = 0.0775 * (I ** 0.46)
        return R, I, chama

    @staticmethod
    def gerar_isoiopsa_gota(lat, lon, dist_cabeça, dir_vento):
        """Desenha a elipse/parábola de dispersão baseada na mecânica de fluidos do vento"""
        pontos = []
        dir_propagacao = dir_vento + 180
        
        # Resolução radial de alta definição (36 pontos para fechar o polígono perfeitamente)
        for i in range(37):
            angulo_graus = dir_propagacao - 180 + (i * 10)
            ang_rad = math.radians(angulo_graus)
            
            # Fator de excentricidade: r_sub_dist depende se o ângulo está virado para a cabeça ou cauda
            fator_direcional = math.cos(math.radians(angulo_graus - dir_propagacao))
            if fator_direcional > 0:
                fator_forma = 0.35 + (0.65 * falar_direcional := fator_direcional)
            else:
                fator_forma = 0.35 + (0.15 * falar_direcional := fator_direcional)
                
            dist_ponto = dist_cabeça * fator_forma
            dx = dist_ponto * math.sin(ang_rad)
            dy = dist_ponto * math.cos(ang_rad)
            
            n_lat = lat + (dy / 6378137) * (180 / math.pi)
            n_lon = lon + (dx / 6378137) * (180 / math.pi) / math.cos(math.radians(lat))
            pontos.append([n_lat, n_lon])
        return pontos

# --- CONFIGURAÇÃO DA SESSÃO ---
if "lat" not in st.session_state: st.session_state.lat = 39.557
if "lon" not in st.session_state: st.session_state.lon = -7.996
if "zoom" not in st.session_state: st.session_state.zoom = 7

# --- CONTROLOS TÁTICOS (PAINEL LATERAL CO-PILOTO) ---
with st.sidebar:
    st.header("⚙️ Configuração do Cenário")
    
    st.markdown("<p class='section-title'>Tempo de Simulação</p>", unsafe_allow_html=True)
    duracao_horas = st.slider("Duração Total da Projeção (Horas):", min_value=1, max_value=12, value=4, step=1)
    passo_minutos = st.selectbox("Resolução do Passo Temporal (Time-step):", options=[15, 30, 60], index=2)
    
    st.markdown("<p class='section-title'>Variáveis Iniciais do Ponto Zero</p>", unsafe_allow_html=True)
    cos_sel = st.selectbox("Tipo de Vegetação Predominante:", options=[322, 312, 311, 321], 
                           format_func=lambda x: MotorFEBPrevisao.MODELOS_COMBUSTIVEL[x]["nome"])
    
    in_temp = st.slider("Temperatura do Ar (°C):", 15.0, 45.0, 32.0, 0.5)
    in_rh = st.slider("Humidade Relativa (%):", 5.0, 90.0, 22.0, 1.0)
    in_vento = st.slider("Velocidade do Vento Base (km/h):", 5.0, 60.0, 25.0, 1.0)
    in_dir = st.slider("Direção de Origem do Vento (°):", 0, 360, 315, 5)

# --- INTERFACE CENTRAL ---
st.title("⚡ FEB Monitorização — Simulador Preditivo de Multi-Passo Temporal")
st.write("Clique no mapa para posicionar o foco. O motor executará iterações com base na duração e resolução escolhidas.")

col_mapa, col_dados = st.columns([1.3, 1])

# Configuração e inicialização do mapa dinâmico
m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=st.session_state.zoom)
folium.TileLayer(tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                 attr="Esri", name="Satélite").add_to(m)
m.add_child(folium.LatLngPopup())

# Plotar ponto de ignição estável
folium.Marker(location=[st.session_state.lat, st.session_state.lon], icon=folium.Icon(color="red", icon="crosshairs")).add_to(m)

# --- EXECUÇÃO DO LOOP COMPUTACIONAL ---
dados_series_temporais = []
dist_acumulada_cabeça = 0.0
total_passos = int((duracao_horas * 60) / passo_minutos)

# Variáveis locais simuladas para a topografia
declive = round(abs(math.sin(st.session_state.lat * st.session_state.lon) * 28.0), 1)
dir_subida = int((st.session_state.lat - st.session_state.lon) * 1000) % 360

# Gradiente de cor para os perímetros temporais (do amarelo ao vermelho escuro)
escala_cores = ["#fed330", "#fa8231", "#eb3b5a", "#a55eea", "#4b154b", "#1e272e"]

for passo in range(1, total_passos + 1):
    minutos_decorridos = passo * passo_minutos
    horas_decorridas = minutos_decorridos / 60.0
    
    # Atualizar meteorologia dinâmica com base na hora da projeção
    t_atual, rh_atual, v_atual = MotorFEBPrevisao.simular_curva_meteo_horaria(in_temp, in_rh, in_vento, horas_decorridas)
    
    # Executar solver de Rothermel para este passo específico
    R, I, chama = MotorFEBPrevisao.calcular_passo_propagacao(cos_sel, v_atual, t_atual, rh_atual, declive, in_dir, dir_subida)
    
    # Distância avançada pela cabeça do incêndio neste intervalo de tempo
    dist_passo = R * passo_minutos
    dist_acumulada_cabeça += dist_passo
    
    # Gerar e desenhar polígono isócrono na carta tática
    cor_perimetro = escala_cores[min((passo - 1) // 2, len(escala_cores) - 1)]
    poligono_coordenadas = MotorFEBPrevisao.gerar_isoiopsa_gota(st.session_state.lat, st.session_state.lon, dist_acumulada_cabeça, in_dir)
    
    folium.Polygon(
        locations=poligono_coordenadas, 
        color=cor_perimetro, 
        weight=2, 
        fill=True, 
        fill_opacity=0.15 if passo != total_passos else 0.35,
        popup=f"Frente às +{horas_decorridas:.1f}h"
    ).add_to(m)
    
    # Registar métricas na matriz de saída
    dados_series_temporais.append({
        "Passo": f"T + {minutos_decorridos} min",
        "Temp (°C)": f"{t_atual:.1f}",
        "Humidade (%)": f"{rh_atual:.1f}",
        "Vento (km/h)": f"{v_atual:.1f}",
        "Velocidade R": f"{R:.2f} m/min",
        "Altura Chama": f"{chama:.1f} m",
        "Progressão": f"{dist_acumulada_cabeça:.0f} m"
    })

# Renderização final dos ecrãs split
with col_mapa:
    mapa_retorno = st_folium(m, width="100%", height=600)
    if mapa_retorno and mapa_retorno.get("last_clicked"):
        novo_clique = (mapa_retorno["last_clicked"]["lat"], mapa_retorno["last_clicked"]["lng"])
        if novo_clique != (st.session_state.lat, st.session_state.lon):
            st.session_state.lat = novo_clique[0]
            st.session_state.lon = novo_clique[1]
            st.session_state.zoom = 14
            st.rerun()

with col_dados:
    st.subheader("📊 Matriz de Evolução Temporal Consecutiva")
    st.write(f"Análise preditiva total configurada para uma janela de **{duracao_horas} horas** dividida em **{total_passos} ciclos**.")
    
    # Exibir tabela completa de séries temporais gerada pelo motor computacional
    df_previsao = pd.DataFrame(dados_series_temporais)
    st.dataframe(df_previsao, use_container_width=True, hide_index=True)
    
    # Cartões de balanço final na cabeça da frente de fogo
    st.write("---")
    st.subheader("🏁 Estimativa de Impacto no Perímetro Final")
    c1, c2 = st.columns(2)
    with c1:
        st.metric(label="Distância Total da Cabeça (Alcance)", value=f"{dist_acumulada_cabeça:.0f} metros")
    with c2:
        st.metric(label="Comprimento de Chama Máximo", value=df_previsao["Altura Chama"].iloc[-1])
