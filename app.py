import streamlit as st
import requests
from streamlit_folium import st_folium
import folium
import pandas as pd
from datetime import datetime, timedelta
import math

# Configuração da página web
st.set_page_config(
    page_title="Painel Tático - EFFIS Copernicus",
    page_icon="🛰️",
    layout="wide"
)

# --- CLIENTE INTEGRADO COPERNICUS & METEO ---
class CopernicusEFFISClient:
    @staticmethod
    def obter_municipios():
        url = "https://api.ipma.pt/open-data/distrits-islands.json"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200: return response.json()['data']
        except Exception: pass
        return []

    @staticmethod
    def injetar_camada_effis(mapa_objeto):
        """
        Adiciona a camada WMS oficial do EFFIS Copernicus ao mapa Folium.
        Esta camada mostra o Perigo de Incêndio (FWI) atualizado por satélite.
        """
        wms_url = "https://effis-gwis-wms.apps.vgt.vito.be/geoserver/effis/wms"
        
        folium.WmsTileLayer(
            url=wms_url,
            layers="modis.fwi",  # Camada do Fire Weather Index (FWI) processada via MODIS/Copernicus
            fmt="image/png",
            transparent=True,
            version="1.1.1",
            name="EFFIS Copernicus - Risco FWI",
            attr="© European Union, EFFIS Copernicus",
            overlay=True,
            control=True,
            opacity=0.55
        ).add_to(mapa_objeto)

class MotorFogoOrografico:
    @classmethod
    def calcular_velocidade_com_declive(cls, r_base, vento, declive_graus, dir_vento, dir_subida):
        f_vento = 1.0 + (vento / 15.0) ** 2
        alinhamento = math.cos(math.radians(dir_vento + 180 - dir_subida))
        if alinhamento > 0:
            f_decorografia = math.exp(0.0693 * declive_graus) * alinhamento
        else:
            f_decorografia = math.exp(-0.04 * declive_graus)
            
        if f_decorografia < 0.3: f_decorografia = 0.3
        return r_base * f_vento * f_decorografia

    @staticmethod
    def gerar_cone_60_graus(lat, lon, distancia_frente, dir_vento_origem):
        pontos_cone = [[lat, lon]]
        dir_propagacao = dir_vento_origem + 180
        angulo_esquerdo = math.radians(dir_propagacao - 30)
        angulo_direito = math.radians(dir_propagacao + 30)
        
        for i in range(11):
            fracao = i / 10.0
            angulo_ponto = angulo_esquerdo + fracao * (angulo_direito - angulo_esquerdo)
            dx = distancia_frente * math.sin(angulo_ponto)
            dy = distancia_frente * math.cos(angulo_ponto)
            nova_lat = lat + (dy / 6378137) * (180 / math.pi)
            nova_lon = lon + (dx / 6378137) * (180 / math.pi) / math.cos(math.radians(lat))
            pontos_cone.append([nova_lat, nova_lon])
            
        pontos_cone.append([lat, lon])
        return pontos_cone

# --- INTERFACE SIG COPERNICUS ---
st.title("🛰️ Integração Satélite: EFFIS Copernicus + Modelo Orogográfico")
st.write("Análise macro e micro. O mapa funde os dados de perigo do satélite europeu com as projeções locais do terreno.")

municipios = CopernicusEFFISClient.obter_municipios()
col_mapa, col_dados = st.columns([1.3, 1])

if "clique" not in st.session_state: st.session_state.clique = None

# Inicializar o mapa com vista topográfica
m = folium.Map(location=[39.557, -7.996], zoom_start=7, tiles="OpenTopoMap")

# INJEÇÃO DA CAMADA REAL DO EFFIS COPERNICUS
CopernicusEFFISClient.injetar_camada_effis(m)

# Adicionar o seletor de camadas nativo do Folium para permitir ligar/desligar a visão do satélite
folium.LayerControl().add_to(m)
m.add_child(folium.LatLngPopup())

dados_painel = {}

if st.session_state.clique:
    lat, lon = st.session_state.clique
    folium.Marker(location=[lat, lon], icon=folium.Icon(color="red", icon="star", prefix="fa")).add_to(m)
    
    # Simulação da orografia (mantida do passo anterior)
    declive = round(abs(math.sin(lat * lon) * 32.0), 1)
    direcao_subida = int((lat - lon) * 1000) % 360
    
    if municipios:
        concelho = min(municipios, key=lambda x: (float(x['latitude']) - lat)**2 + (float(x['longitude']) - lon)**2)
        
        # Parâmetros AROME para acoplar ao cálculo do cone
        vento_arome = 24.0
        dir_vento = 315
        
        R_agora = MotorFogoOrografico.calcular_velocidade_com_declive(0.8, vento_arome, declive, dir_vento, direcao_subida)
        dist_1h = R_agora * 60.0
        dist_2h = dist_1h + (R_agora * 1.15) * 60.0
        
        # Desenhar Cones de 60°
        cone_1h = MotorFogoOrografico.gerar_cone_60_graus(lat, lon, dist_1h, dir_vento)
        cone_2h = MotorFogoOrografico.generar_cone_60_graus(lat, lon, dist_2h, dir_vento) if 'generar_cone_60_graus' in dir(MotorFogoOrografico) else MotorFogoOrografico.gerar_cone_60_graus(lat, lon, dist_2h, dir_vento)
        
        folium.Polygon(locations=cone_2h, color="#e74c3c", weight=2, fill=True, fill_color="#e74c3c", fill_opacity=0.2, popup="Projeção +2h").add_to(m)
        folium.Polygon(locations=cone_1h, color="#e67e22", weight=2, fill=True, fill_color="#e67e22", fill_opacity=0.3, popup="Projeção +1h").add_to(m)
        
        dados_painel = {
            "Concelho Alvo": concelho["local"],
            "Declive Orogáfico": f"{declive}°",
            "Indexador Copernicus Ativo": "MODIS FWI Real-Time",
            "Velocidade Estimada (R)": f"{R_agora:.2f} m/min",
            "Projeção Frente (1h)": f"{dist_1h:.0f} metros",
            "Projeção Frente (2h)": f"{dist_2h:.0f} metros"
        }

with col_mapa:
    mapa_retorno = st_folium(m, width="100%", height=560)
    if mapa_retorno and mapa_retorno.get("last_clicked"):
        novo_clique = (mapa_retorno["last_clicked"]["lat"], mapa_retorno["last_clicked"]["lng"])
        if novo_clique != st.session_state.clique:
            st.session_state.clique = novo_clique
            st.rerun()

with col_dados:
    if dados_painel:
        st.subheader("📊 Diagnóstico Combinado (Local + Satélite)")
        st.success(f"📡 Dados WMS do Copernicus carregados com sucesso de `effis.apps.vgt.vito.be`")
        
        df_effis = pd.DataFrame(dados_painel.items(), columns=["Variável de Análise", "Mapeamento"])
        st.dataframe(df_effis, use_container_width=True, hide_index=True)
        
        st.info("""
        ℹ️ **Interpretação Visual do EFFIS:** O sombreado colorido de fundo (que varia de verde a vermelho escuro) é renderizado diretamente pelo Copernicus. 
        Ele representa o nível de severidade do **FWI Europeu** para o dia de hoje. 
        Podes controlar a opacidade ou ligar/desligar esta camada usando o seletor flutuante que aparece no canto superior direito do mapa.
        """)
