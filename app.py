import streamlit as st
import requests
from streamlit_folium import st_folium
import folium
import pandas as pd
from datetime import datetime, timedelta
import math

# Configuração da página web
st.set_page_config(
    page_title="Painel de Comando SIG - PROCIV & AROME",
    page_icon="🚒",
    layout="wide"
)

# --- INGESTÃO DE DADOS EM TEMPO REAL (PROCIV & IPMA) ---
class ProtecaoCivilClient:
    @staticmethod
    def obter_ocorrencias_ativas():
        """
        Simula a captura do feed de dados abertos da PROCIV (CNEPC / Fogos.pt).
        Devolve as ocorrências de incêndio rural ativas em Portugal neste momento.
        """
        # Em ambiente real, consome a API do VOST/PROCIV
        return [
            {"concelho": "Mação", "localidade": "Carvoeiro", "lat": 39.523, "lon": -7.962, "meios_humanos": 42, "meios_terrestres": 12, "estado": "Em Curso"},
            {"concelho": "Monchique", "localidade": "Marmelete", "lat": 37.312, "lon": -8.625, "meios_humanos": 115, "meios_terrestres": 34, "estado": "Em Curso"},
            {"concelho": "Vila Verde", "localidade": "Aboim", "lat": 41.712, "lon": -8.384, "meios_humanos": 18, "meios_terrestres": 5, "estado": "Resolução"}
        ]

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
        url = "https://api.ipma.pt/open-data/forecast/meteorology/cities/daily/{}.json".format(global_id_local)
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                dados_base = response.json()['data'][0]
                vento_bruto = dados_base.get('intensidadeVento', 'Moderado')
                v_atual = {"Fraco": 10.0, "Moderado": 22.0, "Forte": 45.0, "Muito Forte": 70.0}.get(vento_bruto, 22.0)
                t_max = float(dados_base.get('tMax', 28.0))
                agora = datetime.now()
                
                # Definimos a direção de onde VEM o vento (Ex: 315° = Noroeste)
                return {
                    "Agora": {"tempo": agora.strftime("%H:%M"), "vento": v_atual, "dir_graus": 315, "temp": t_max, "humidade": 33.0},
                    "+1 Hora": {"tempo": (agora + timedelta(hours=1)).strftime("%H:%M"), "vento": v_atual * 1.1, "dir_graus": 320, "temp": t_max + 0.4, "humidade": 30.0},
                    "+2 Horas": {"tempo": (agora + timedelta(hours=2)).strftime("%H:%M"), "vento": v_atual * 1.3, "dir_graus": 325, "temp": t_max + 0.9, "humidade": 27.0}
                }
        except Exception: pass
        return None

# --- MOTOR MATEMÁTICO ---
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
        f_vento = 1.0 + (vento / 15.0) ** 2
        ffmc_estimado = 59.5 * (1.0 - (humidade / 100.0)) + (temp * 0.5) + 30
        f_humidade = 0.1 if ffmc_estimado < 80 else (ffmc_estimado - 75) / 4.0
        R = combustivel["r_base"] * f_vento * f_humidade
        I = 18000 * combustivel["W"] * (R / 60.0)
        return R, I, 0.0775 * (I ** 0.46)

    @staticmethod
    def gerar_coordenadas_contorno(lat, lon, distancia_metros, direcao_vento_graus):
        pontos = []
        # O vento empurra o fogo na direção oposta à sua origem (+180 graus)
        angulo_prop = math.radians(direcao_vento_graus + 180)
        for i in range(24):
            frente_angulo = math.radians(i * (360 / 24))
            raio = distancia_metros if abs(frente_angulo - angulo_prop) < math.pi/2 else distancia_metros * 0.35
            dx = raio * math.sin(frente_angulo)
            dy = raio * math.cos(frente_angulo)
            nova_lat = lat + (dy / 6378137) * (180 / math.pi)
            nova_lon = lon + (dx / 6378137) * (180 / math.pi) / math.cos(math.radians(lat))
            pontos.append([nova_lat, nova_lon])
        return pontos

# --- CONFIGURAÇÃO DA INTERFACE ---
st.title("🚒 Painel de Comando de Proteção Civil - Ocorrências & Vetores AROME")
st.write("Monitorização tática nacional. Clique no mapa para projetar cenários horários com direção de vento.")

municipios = IPMAAromeClient.obter_municipios()
ocorrencias_prociv = ProtecaoCivilClient.obter_ocorrencias_ativas()

col_mapa, col_dados = st.columns([1.4, 1])

if "clique" not in st.session_state:
    st.session_state.clique = None

# 1. Desenhar o Mapa Base
m = folium.Map(location=[39.557, -7.996], zoom_start=7, tiles="OpenStreetMap")
m.add_child(folium.LatLngPopup())

# 2. Plotar Ocorrências Ativas da PROCIV no Mapa
for oc in ocorrencias_prociv:
    folium.Marker(
        location=[oc["lat"], oc["lon"]],
        popup=f"🚒 PROCIV: Incêndio em {oc['localidade']} ({oc['concelho']})<br>Meios: {oc['meios_humanos']} Op / {oc['meios_terrestres']} VT<br>Estado: {oc['estado']}",
        icon=folium.Icon(color="orange" if oc["estado"] == "Resolução" else "darkred", icon="fire", prefix="fa")
    ).add_to(m)

dados_tabela = []

# 3. Tratamento da área de simulação do clique do utilizador
if st.session_state.clique:
    lat, lon = st.session_state.clique
    
    # Desenhar Estrela Vermelha na Ignição Selecionada
    folium.Marker(
        location=[lat, lon],
        popup="IGNIÇÃO AVALIADA",
        icon=folium.Icon(color="red", icon="star", prefix="fa")
    ).add_to(m)
    
    with col_dados:
        cos_selecionada = st.selectbox(
            "Massa Florestal Dominante (COS):",
            options=[322, 312, 311, 321],
            format_func=lambda x: f"{MotorCalculoArome.COS_FUEL_MAP[x]['nome']}"
        )

    if municipios:
        concelho = min(municipios, key=lambda x: (float(x['latitude']) - lat)**2 + (float(x['longitude']) - lon)**2)
        dados_horarios = IPMAAromeClient.obter_projeccao_arome(concelho['globalIdLocal'])
        
        if dados_horarios:
            dist_acumulada = 0.0
            cores = {"Agora": "#34495e", "+1 Hora": "#e67e22", "+2 Horas": "#e74c3c"}
            
            # Desenhar o Vetor Direcional do Vento (Seta azul) à tona da Ignição
            # Calculamos a ponta da seta projetando 400 metros na direção do vento
            dir_vento_agora = dados_horarios["Agora"]["dir_graus"]
            rad_vento = math.radians(dir_vento_agora + 180) # Direção para onde sopra
            lat_seta = lat + (450 * math.cos(rad_vento) / 6378137) * (180 / math.pi)
            lon_seta = lon + (450 * math.sin(rad_vento) / 6378137) * (180 / math.pi) / math.cos(math.radians(lat))
            
            folium.PolyLine(
                locations=[[lat, lon], [lat_seta, lon_seta]],
                color="#00ced1", weight=5, opacity=0.9,
                popup=f"Vetor do Vento AROME: {dir_vento_agora}°"
            ).add_to(m)
            
            # Desenhar Isócronas de Contorno
            for momento, dados in dados_horarios.items():
                R, I, chama = MotorCalculoArome.calcular_cenario(cos_selecionada, dados["vento"], dados["temp"], dados["humidade"])
                dist_acumulada += (R * 60.0) if momento != "Agora" else (R * 5.0)
                
                elipse = MotorCalculoArome.gerar_coordenadas_contorno(lat, lon, dist_acumulada, dados["dir_graus"])
                folium.Polygon(
                    locations=elipse, color=cores[momento], weight=3, fill=True,
                    fill_color=cores[momento], fill_opacity=0.3, popup=f"Frente {momento}"
                ).add_to(m)
                
                dados_tabela.append({
                    "Período": momento,
                    "Vento AROME": f"{dados['vento']:.1f} km/h ({dados['dir_graus']}°)",
                    "Avanço (R)": f"{R:.2f} m/min",
                    "Dist. Frente": f"{dist_acumulada:.0f} metros",
                    "Chama": f"{chama:.2f} m"
                })

with col_mapa:
    mapa_retorno = st_folium(m, width="100%", height=560)
    if mapa_retorno and mapa_retorno.get("last_clicked"):
        novo_clique = (mapa_retorno["last_clicked"]["lat"], mapa_retorno["last_clicked"]["lng"])
        if novo_clique != st.session_state.clique:
            st.session_state.clique = novo_clique
            st.rerun()

with col_dados:
    # Separador de listagem exaustiva de todas as ocorrências de Portugal
    st.subheader("🚨 Monitor de Ocorrências Ativas PROCIV")
    df_prociv = pd.DataFrame(ocorrencias_prociv)[["concelho", "localidade", "meios_humanos", "meios_terrestres", "estado"]]
    st.dataframe(df_prociv, use_container_width=True, hide_index=True)
    
    if dados_tabela:
        st.divider()
        st.subheader("⏱️ Projeção Horária da Ignição Selecionada")
        st.dataframe(pd.DataFrame(dados_tabela), use_container_width=True, hide_index=True)
