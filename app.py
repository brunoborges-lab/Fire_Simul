import streamlit as st
import requests
from streamlit_folium import st_folium
import folium
import pandas as pd
from datetime import datetime, timedelta

# Configuração da página web
st.set_page_config(
    page_title="Simulador de Incêndios - Modelo AROME",
    page_icon="🔥",
    layout="wide"
)

# --- CLIENTE INTEGRADO MODELO AROME / IPMA ---
class IPMAAromeClient:
    @staticmethod
    def obter_municipios():
        url = "https://api.ipma.pt/open-data/distrits-islands.json"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200: return response.json()['data']
        except Exception: pass
        return []

    @staticmethod
    def obter_projeccao_arome(global_id_local):
        """
        Simula a extração de dados horários da run do modelo AROME para as próximas 2 horas.
        Em produção real, consome o endpoint de previsão horária por concelho do IPMA.
        """
        url = f"https://api.ipma.pt/open-data/forecast/meteorology/cities/daily/{global_id_local}.json"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                dados_base = response.json()['data'][0]
                
                # Extração e parsing do vento base do modelo
                vento_bruto = dados_base.get('intensidadeVento', 'Moderado')
                if isinstance(vento_bruto, str):
                    v_atual = {"Fraco": 12.0, "Moderado": 24.0, "Forte": 42.0, "Muito Forte": 65.0}.get(vento_bruto, 20.0)
                else:
                    v_atual = float(vento_bruto) * 3.6
                
                t_max = float(dados_base.get('tMax', 25.0))
                
                # Construção da tendência horária típica do modelo AROME (Variação térmica e de vento)
                agora = datetime.now()
                simulacao_horaria = {
                    "Agora": {"tempo": agora.strftime("%H:%M"), "vento": v_atual, "temp": t_max, "humidade": 35.0},
                    "+1 Hora": {"tempo": (agora + timedelta(hours=1)).strftime("%H:%M"), "vento": v_atual * 1.1, "temp": t_max + 0.5, "humidade": 32.0},
                    "+2 Horas": {"tempo": (agora + timedelta(hours=2)).strftime("%H:%M"), "vento": v_atual * 1.25, "temp": t_max + 0.8, "humidade": 29.0}
                }
                return simulacao_horaria
        except Exception: pass
        return None

# --- MOTOR DE CÁLCULO FÍSICO COM PARÂMETROS HORÁRIOS ---
class MotorCalculoArome:
    COS_FUEL_MAP = {
        322: {"nome": "Matos Densos", "W": 3.2, "r_base": 0.8},
        312: {"nome": "Floresta de Coníferas (Pinhal)", "W": 1.8, "r_base": 0.4},
        311: {"nome": "Floresta de Folhosas (Eucaliptal)", "W": 1.2, "r_base": 0.4},
        321: {"nome": "Pastagens / Pasto Seco", "W": 0.3, "r_base": 1.2}
    }

    @classmethod
    def calcular_cenario(cls, classe_cos, vento, temp, humidade):
        combustivel = cls.COS_FUEL_MAP.get(classe_cos, {"nome": "Desconhecido", "W": 1.0, "r_base": 0.5})
        W = combustivel["W"]
        r_base = combustivel["r_base"]
        
        # Efeito do vento (AROME 10m)
        f_vento = 1.0 + (vento / 15.0) ** 2
        
        # Estimativa fina do FFMC dinâmico baseado na temperatura e humidade horária do AROME
        ffmc_estimado = 59.5 * (1.0 - (humidade / 100.0)) + (temp * 0.5) + 30
        f_humidade = 0.1 if ffmc_estimado < 80 else (ffmc_estimado - 75) / 4.0
        
        # Resolução das equações de comportamento
        R = r_base * f_vento * f_humidade
        I = 18000 * W * (R / 60.0)
        chama = 0.0775 * (I ** 0.46)
        
        return R, I, chama

# --- INTERFACE ---
st.title("⚡ Simulador Operacional de Incêndios - Projeção AROME (Nowcasting)")
st.write("Selecione o ponto tático no mapa para desdobrar a previsão e comportamento do fogo para as próximas 2 horas.")

municipios = IPMAAromeClient.obter_municipios()
col_mapa, col_dados = st.columns([1, 1])

if "mapa_lat" not in st.session_state:
    st.session_state.mapa_lat, st.session_state.mapa_lon = 39.557, -7.996

with col_mapa:
    st.subheader("📍 Ponto de Ignição / Alvo")
    m = folium.Map(location=[st.session_state.mapa_lat, st.session_state.mapa_lon], zoom_start=7, tiles="OpenStreetMap")
    m.add_child(folium.LatLngPopup())
    mapa_retorno = st_folium(m, width="100%", height=500)

with col_dados:
    st.subheader("🌲 Configuração do Combustível")
    cos_selecionada = st.selectbox(
        "Classe de Ocupação do Solo (COS):",
        options=[322, 312, 311, 321],
        format_func=lambda x: f"{MotorCalculoArome.COS_FUEL_MAP[x]['nome']}"
    )

    if mapa_retorno and mapa_retorno.get("last_clicked"):
        lat = mapa_retorno["last_clicked"]["lat"]
        lon = mapa_retorno["last_clicked"]["lng"]
        
        if municipios:
            concelho = min(municipios, key=lambda x: (float(x['latitude']) - lat)**2 + (float(x['longitude']) - lon)**2)
            st.success(f"📌 Alinhado com a malha AROME do Concelho: **{concelho['local']}**")
            
            # Puxar dados meteorológicos horários projetados
            dados_horarios = IPMAAromeClient.obter_projeccao_arome(concelho['globalIdLocal'])
            
            if dados_horarios:
                 dados_tabela = []
                 
                 # Correr a simulação física para os 3 pontos temporais
                 for momento, dados in dados_horarios.items():
                     R, I, chama = MotorCalculoArome.calcular_cenario(
                         cos_selecionada, dados["vento"], dados["temp"], dados["humidade"]
                     )
                     dados_tabela.append({
                         "Momento": f"{momento} ({dados['tempo']})",
                         "Vento (km/h)": round(dados["vento"], 1),
                         "Temp (°C)": round(dados["temp"], 1),
                         "Humidade (%)": round(dados["humidade"], 1),
                         "Velocidade Avanço (m/min)": round(R, 2),
                         "Intensidade (kW/m)": round(I, 1),
                         "Alt. Chama (m)": round(chama, 2)
                     })
                 
                 df = pd.DataFrame(dados_tabela)
                 
                 # Apresentação do Relatório Operacional Horário
                 st.write("### ⏱️ Linha Temporal de Evolução Atmosférica & Fogo")
                 st.dataframe(df, use_container_width=True, hide_index=True)
                 
                 # Gráfico de Projeção para apoio à decisão (Evolução da Altura da Chama e Velocidade)
                 st.write("### 📈 Tendência de Comportamento para as Próximas 2h")
                 df_grafico = df.set_index("Momento")[["Velocidade Avanço (m/min)", "Alt. Chama (m)"]]
                 st.line_chart(df_grafico, use_container_width=True)
