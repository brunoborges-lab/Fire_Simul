import streamlit as st
import requests
from streamlit_folium import st_folium
import folium
import pandas as pd
from datetime import datetime, timedelta
import math

# Configuração da página web
st.set_page_config(
    page_title="Simulador SIG - Contornos de Incêndio Rural",
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
        url = f"https://api.ipma.pt/open-data/forecast/meteorology/cities/daily/{global_id_local}.json"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                dados_base = response.json()['data'][0]
                vento_bruto = dados_base.get('intensidadeVento', 'Moderado')
                
                if isinstance(vento_bruto, str):
                    v_atual = {"Fraco": 10.0, "Moderado": 20.0, "Forte": 40.0, "Muito Forte": 65.0}.get(vento_bruto, 20.0)
                else:
                    v_atual = float(vento_bruto) * 3.6
                
                t_max = float(dados_base.get('tMax', 25.0))
                agora = datetime.now()
                
                # Simulação da direção do vento (ex: vindo de Noroeste = 315 graus, empurra para Sudeste)
                return {
                    "Agora": {"tempo": agora.strftime("%H:%M"), "vento": v_atual, "dir_graus": 315, "temp": t_max, "humidade": 35.0},
                    "+1 Hora": {"tempo": (agora + timedelta(hours=1)).strftime("%H:%M"), "vento": v_atual * 1.1, "dir_graus": 310, "temp": t_max + 0.5, "humidade": 32.0},
                    "+2 Horas": {"tempo": (agora + timedelta(hours=2)).strftime("%H:%M"), "vento": v_atual * 1.25, "dir_graus": 300, "temp": t_max + 0.8, "humidade": 29.0}
                }
        except Exception: pass
        return None

# --- MOTOR DE CÁLCULO FÍSICO DO FOGO ---
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
        
        f_vento = 1.0 + (vento / 15.0) ** 2
        ffmc_estimado = 59.5 * (1.0 - (humidade / 100.0)) + (temp * 0.5) + 30
        f_humidade = 0.1 if ffmc_estimado < 80 else (ffmc_estimado - 75) / 4.0
        
        R = r_base * f_vento * f_humidade
        I = 18000 * W * (R / 60.0)
        chama = 0.0775 * (I ** 0.46)
        
        return R, I, chama

    @staticmethod
    def gerar_coordenadas_contorno(lat, lon, distancia_metros, direcao_vento_graus):
        """Calcula os pontos geográficos do contorno elíptico da expansão do fogo"""
        pontos = []
        # Direção de propagação é oposta à direção de onde vem o vento (+180°)
        angulo_prop = math.radians(direcao_vento_graus + 180)
        
        # Gerar um polígono de 24 pontos para desenhar a elipse de projeção
        for i in range(24):
            frente_angulo = math.radians(i * (360 / 24))
            # Eixo maior (comprimento) vs eixo menor (largura do flanco) baseado no vento
            raio_comprimento = distancia_metros if abs(frente_angulo - angulo_prop) < math.pi/2 else distancia_metros * 0.4
            
            dx = raio_comprimento * math.sin(frente_angulo)
            dy = raio_comprimento * math.cos(frente_angulo)
            
            # Conversão aproximada de metros para graus decimais (Fórmula simplificada de Haversine)
            r_earth = 6378137
            nova_lat = lat + (dy / r_earth) * (180 / math.pi)
            nova_lon = lon + (dx / r_earth) * (180 / math.pi) / math.cos(math.radians(lat))
            pontos.append([nova_lat, nova_lon])
        return pontos

# --- INTERFACE OPERACIONAL ---
st.title("🗺️ Simulador SIG - Contornos de Projeção de Incêndios")
st.write("Clique no mapa para marcar a ignição e projetar as frentes geográficas (isócronas de 1h e 2h).")

municipios = IPMAAromeClient.obter_municipios()
col_mapa, col_dados = st.columns([1.3, 1])

lat_inicial, lon_inicial = 39.557, -7.996
dados_tabela = []
contornos_mapa = []

# Processamento de Dados Prévio antes de desenhar o mapa
if "clique" not in st.session_state:
    st.session_state.clique = None

with col_dados:
    st.subheader("🌲 Parâmetros e Modelo Físico")
    cos_selecionada = st.selectbox(
        "Classe de Vegetação (COS):",
        options=[322, 312, 311, 321],
        format_func=lambda x: f"{MotorCalculoArome.COS_FUEL_MAP[x]['nome']}"
    )

# Inicializar o mapa base
m = folium.Map(location=[lat_inicial, lon_inicial], zoom_start=7, tiles="OpenStreetMap")
m.add_child(folium.LatLngPopup())

# Se houver um clique registado, injetamos a Estrela Vermelha e calculamos os contornos
if st.session_state.clique:
    lat, lon = st.session_state.clique
    
    # Desenhar Estrela Vermelha de Ignição usando FontAwesome
    folium.Marker(
        location=[lat, lon],
        popup="PONTO DE IGNIÇÃO",
        icon=folium.Icon(color="red", icon="star", prefix="fa")
    ).add_to(m)
    
    if municipios:
        concelho = min(municipios, key=lambda x: (float(x['latitude']) - lat)**2 + (float(x['longitude']) - lon)**2)
        dados_horarios = IPMAAromeClient.obter_projeccao_arome(concelho['globalIdLocal'])
        
        if dados_horarios:
            distancia_acumulada = 0.0
            cores_contorno = {"Agora": "#34495e", "+1 Hora": "#e67e22", "+2 Horas": "#e74c3c"}
            opacidade_contorno = {"Agora": 0.2, "+1 Hora": 0.4, "+2 Horas": 0.5}
            
            for momento, dados in dados_horarios.items():
                R, I, chama = MotorCalculoArome.calcular_cenario(
                    cos_selecionada, dados["vento"], dados["temp"], dados["humidade"]
                )
                
                # Multiplicar a velocidade de avanço por 60 minutos para saber a distância percorrida nessa hora
                if momento != "Agora":
                    distancia_acumulada += R * 60.0
                else:
                    distancia_acumulada += R * 5.0 # Contorno imediato (5 min iniciais)
                
                # Gerar o polígono geométrico elíptico da frente
                coordenadas_elipse = MotorCalculoArome.gerar_coordenadas_contorno(
                    lat, lon, distancia_acumulada, dados["dir_graus"]
                )
                
                # Adicionar o contorno visual diretamente ao mapa Folium
                folium.Polygon(
                    locations=coordenadas_elipse,
                    color=cores_contorno[momento],
                    weight=3,
                    fill=True,
                    fill_color=cores_contorno[momento],
                    fill_opacity=opacidade_contorno[momento],
                    popup=f"Previsão {momento} | Área de Impacto"
                ).add_to(m)
                
                dados_tabela.append({
                    "Projeção": momento,
                    "Vento": f"{dados['vento']:.1f} km/h",
                    "R (Avanço)": f"{R:.2f} m/min",
                    "Dist. Total": f"{distancia_acumulada:.0f} metros",
                    "Chama": f"{chama:.2f} m"
                })

with col_mapa:
    # Renderizar o mapa interativo no Streamlit
    mapa_retorno = st_folium(m, width="100%", height=550)
    
    # Capturar e guardar o clique do utilizador para forçar o re-render com gráficos
    if mapa_retorno and mapa_retorno.get("last_clicked"):
        novo_clique = (mapa_retorno["last_clicked"]["lat"], mapa_retorno["last_clicked"]["lng"])
        if novo_clique != st.session_state.clique:
            st.session_state.clique = novo_clique
            st.rerun()

with col_dados:
    if dados_tabela:
        st.write("---")
        st.write("### ⏱️ Relatório Tático de Expansão de Área")
        st.dataframe(pd.DataFrame(dados_tabela), use_container_width=True, hide_index=True)
        
        st.markdown("""
        **Legenda de Cores no Mapa:**
        * ⬛ **Cinza Escuro:** Área afetada imediata (Primeiros minutos).
        * 🟧 **Laranja:** Perímetro estimado da frente de fogo em **+1 Hora**.
        * 🟥 **Vermelho:** Perímetro estimado da frente de fogo em **+2 Horas**.
        """)
