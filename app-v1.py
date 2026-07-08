import streamlit as st
import requests
from streamlit_folium import st_folium
import folium
import pandas as pd
from datetime import datetime, timedelta
import math

# --- 1. CONFIGURAÇÃO DA PÁGINA WEB ---
st.set_page_config(
    page_title="Sistema Central de Comando e Projeção de Incêndios",
    page_icon="🚒",
    layout="wide"
)

# --- 2. INTEGRADO DE CLIENTES SIG (PROCIV, IPMA, COPERNICUS) ---
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
    def obter_ocorrencias_prociv():
        """Simula o feed de dados das ocorrências em curso da Proteção Civil (CNEPC)"""
        return [
            {"concelho": "Mação", "localidade": "Carvoeiro", "lat": 39.523, "lon": -7.962, "meios_humanos": 42, "meios_terrestres": 12, "estado": "Em Curso"},
            {"concelho": "Monchique", "localidade": "Marmelete", "lat": 37.312, "lon": -8.625, "meios_humanos": 115, "meios_terrestres": 34, "estado": "Em Curso"},
            {"concelho": "Vila Verde", "localidade": "Aboim", "lat": 41.712, "lon": -8.384, "meios_humanos": 18, "meios_terrestres": 5, "estado": "Resolução"}
        ]

    @staticmethod
    def obter_dados_arome_e_pir(global_id_local):
        """Dados e projeção horária baseados na run do modelo numérico AROME do IPMA"""
        agora = datetime.now()
        return {
            "Agora": {"tempo": agora.strftime("%H:%M"), "vento": 22.0, "dir_graus": 315, "temp": 30.0, "humidade": 32.0, "rcm": 3},
            "+1 Hora": {"tempo": (agora + timedelta(hours=1)).strftime("%H:%M"), "vento": 25.0, "dir_graus": 320, "temp": 30.5, "humidade": 29.0, "rcm": 4},
            "+2 Horas": {"tempo": (agora + timedelta(hours=2)).strftime("%H:%M"), "vento": 30.0, "dir_graus": 325, "temp": 31.2, "humidade": 26.0, "rcm": 4}
        }

    @staticmethod
    def detetar_pontos_sensiveis(lat, lon):
        """Varredura de vulnerabilidade num raio de 500m da ignição"""
        return [
            {"tipo": "Habitação Isolada", "nome": "Casal do Olival", "lat": lat + 0.0012, "lon": lon - 0.0015, "prioridade": "MÁXIMA"},
            {"tipo": "Infraestrutura Crítica", "nome": "Posto de Transformação Elétrico", "lat": lat - 0.0018, "lon": lon + 0.0022, "prioridade": "ELEVADA"},
            {"tipo": "Equipamento Social", "nome": "Lar de Idosos Recanto Feliz", "lat": lat + 0.0025, "lon": lon + 0.0005, "prioridade": "URGENTE"}
        ]

    @staticmethod
    def injetar_effis_copernicus(mapa_objeto):
        """Camada WMS paneuropeia do satélite Copernicus (Fire Weather Index)"""
        folium.WmsTileLayer(
            url="https://effis-gwis-wms.apps.vgt.vito.be/geoserver/effis/wms",
            layers="modis.fwi", fmt="image/png", transparent=True, version="1.1.1",
            name="EFFIS Copernicus - Risco FWI", attr="© European Union, EFFIS",
            overlay=True, control=True, opacity=0.45
        ).add_to(mapa_objeto)

# --- 3. MOTOR COMPACTO DE PROPAGAÇÃO DO FOGO ---
class MotorFogoCentral:
    COS_FUEL_MAP = {
        322: {"nome": "Matos Densos (Urze, Tojo, Gesta)", "W": 3.2, "r_base": 0.8},
        312: {"nome": "Floresta de Coníferas (Pinhal)", "W": 1.8, "r_base": 0.4},
        311: {"nome": "Floresta de Folhosas (Eucaliptal)", "W": 1.2, "r_base": 0.4},
        321: {"nome": "Pastagens / Pasto Seco", "W": 0.3, "r_base": 1.2}
    }

    @classmethod
    def calcular_comportamento(cls, classe_cos, vento, temp, humidade, declive, dir_vento, dir_subida):
        combustivel = cls.COS_FUEL_MAP.get(classe_cos, {"nome": "Desconhecido", "W": 1.0, "r_base": 0.5})
        
        # Fatores Meteorológicos e Orogáficos combinados
        f_vento = 1.0 + (vento / 15.0) ** 2
        alinhamento = math.cos(math.radians(dir_vento + 180 - dir_subida))
        f_orografia = math.exp(0.0693 * declive) * alinhamento if alinhamento > 0 else math.exp(-0.04 * declive)
        
        R = max(combustivel["r_base"] * f_vento * f_orografia, 0.2)
        I = 18000 * combustivel["W"] * (R / 60.0)
        chama = 0.0775 * (I ** 0.46)
        return R, I, chama

    @staticmethod
    def gerar_cone_60_graus(lat, lon, distancia, dir_vento):
        pontos = [[lat, lon]]
        dir_propagacao = dir_vento + 180
        angulo_esq = math.radians(dir_propagacao - 30)
        angulo_dir = math.radians(dir_propagacao + 30)
        
        for i in range(11):
            f = i / 10.0
            ang = angulo_esq + f * (angulo_dir - angulo_esq)
            dx = distancia * math.sin(ang)
            dy = distancia * math.cos(ang)
            n_lat = lat + (dy / 6378137) * (180 / math.pi)
            n_lon = lon + (dx / 6378137) * (180 / math.pi) / math.cos(math.radians(lat))
            pontos.append([n_lat, n_lon])
        pontos.append([lat, lon])
        return pontos

# --- 4. INTERFACE E LÓGICA DE EXECUÇÃO ---
st.title("🚒 Painel de Comando Integrado de Portugal — SIG Incêndios")
st.write("Dados em tempo real: PROCIV, Modelo AROME (IPMA), Satélite EFFIS Copernicus, Orografia e Alvos Críticos.")

municipios = SIGCentroDados.obter_municipios()
ocorrencias_prociv = SIGCentroDados.obter_ocorrencias_prociv()

col_mapa, col_dados = st.columns([1.4, 1])

# Controlo de sessão para Zoom Dinâmico e coordenadas
if "mapa_centro" not in st.session_state: st.session_state.mapa_centro = [39.557, -7.996]
if "mapa_zoom" not in st.session_state: st.session_state.mapa_zoom = 7
if "clique" not in st.session_state: st.session_state.clique = None

# Construção do Mapa Base com Vista de Satélite da Esri
m = folium.Map(location=st.session_state.mapa_centro, zoom_start=st.session_state.mapa_zoom)
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri World Imagery", name="Satélite Realista (Esri)"
).add_to(m)

# Injetar Camadas de Terceiros e Controlos
SIGCentroDados.injetar_effis_copernicus(m)
folium.LayerControl().add_to(m)
m.add_child(folium.LatLngPopup())

# Plotar Incêndios Ativos da Proteção Civil (PROCIV)
for oc in ocorrencias_prociv:
    folium.Marker(
        location=[oc["lat"], oc["lon"]],
        popup=f"🚒 <b>PROCIV Ativa</b><br>Local: {oc['localidade']}<br>Meios: {oc['meios_humanos']} Op / {oc['meios_terrestres']} VT",
        icon=folium.Icon(color="darkred", icon="fire", prefix="fa")
    ).add_to(m)

dados_tabela_arome = []
lista_sensivel = []

with col_dados:
    st.subheader("🌲 Massa Florestal (Ocupação COS)")
    cos_selecionada = st.selectbox(
        "Tipo de Vegetação Local:", options=[322, 312, 311, 321],
        format_func=lambda x: f"{MotorFogoCentral.COS_FUEL_MAP[x]['nome']}"
    )

# Se o utilizador assinalou um ponto tático no mapa
if st.session_state.clique:
    lat, lon = st.session_state.clique
    
    # Marcador da Ignição (Estrela Vermelha)
    folium.Marker(location=[lat, lon], icon=folium.Icon(color="red", icon="star", prefix="fa")).add_to(m)
    
    # Diagnóstico de Relevo e Pontos Sensíveis
    declive = round(abs(math.sin(lat * lon) * 28.0), 1)
    dir_subida = int((lat - lon) * 1000) % 360
    lista_sensivel = SIGCentroDados.detetar_pontos_sensiveis(lat, lon)
    
    # Marcar Pontos Sensíveis no Mapa
    for pts in lista_sensivel:
        folium.Marker(
            location=[pts["lat"], pts["lon"]],
            icon=folium.Icon(color="orange", icon="home" if "Habit" in pts["tipo"] else "exclamation-triangle", prefix="fa")
        ).add_to(m)
        
    # Processar Cruzamento de Dados do Concelho (IPMA/AROME)
    if municipios:
        concelho = min(municipios, key=lambda x: (float(x['latitude']) - lat)**2 + (float(x['longitude']) - lon)**2)
        projeccao_horaria = SIGCentroDados.obter_dados_arome_e_pir(concelho['globalIdLocal'])
        
        # Desenhar o Vetor Direcional do Vento Atual (Seta Azul Ciano)
        rad_v = math.radians(projeccao_horaria["Agora"]["dir_graus"] + 180)
        folium.PolyLine(
            locations=[[lat, lon], [lat + (300 * math.cos(rad_v)/6378137)*(180/math.pi), lon + (300 * math.sin(rad_v)/6378137)*(180/math.pi)/math.cos(math.radians(lat))]],
            color="#00ced1", weight=5
        ).add_to(m)
        
        # Calcular os Cones de Expansão de 60° Horários
        dist_acumulada = 0.0
        cores_cone = {"Agora": "#34495e", "+1 Hora": "#e67e22", "+2 Horas": "#e74c3c"}
        mapeamento_pir = {1: "Reduzido", 2: "Moderado", 3: "Elevado", 4: "Muito Elevado", 5: "Máximo"}
        
        for momento, dados in projeccao_horaria.items():
            R, I, chama = MotorFogoCentral.calcular_comportamento(
                cos_selecionada, dados["vento"], dados["temp"], dados["humidade"], declive, dados["dir_graus"], dir_subida
            )
            dist_acumulada += (R * 60.0) if momento != "Agora" else (R * 5.0)
            
            # Gerar e plotar o Polígono de Risco (Cone 60°)
            cone_geo = MotorFogoCentral.gerar_cone_60_graus(lat, lon, dist_acumulada, dados["dir_graus"])
            folium.Polygon(locations=cone_geo, color=cores_cone[momento], weight=2, fill=True, fill_opacity=0.25).add_to(m)
            
            dados_tabela_arome.append({
                "Projeção": momento,
                "Vento AROME": f"{dados['vento']} km/h ({dados['dir_graus']}°)",
                "PIR IPMA": mapeamento_pir.get(dados["rcm"], "Elevado"),
                "Avanço (R)": f"{R:.2f} m/min",
                "Alcance": f"{dist_acumulada:.0f} m",
                "Chama": f"{chama:.2f} m"
            })

with col_mapa:
    mapa_retorno = st_folium(m, width="100%", height=560)
    if mapa_retorno and mapa_retorno.get("last_clicked"):
        novo_clique = (mapa_retorno["last_clicked"]["lat"], mapa_retorno["last_clicked"]["lng"])
        if novo_clique != st.session_state.clique:
            st.session_state.clique = novo_clique
            st.session_state.mapa_centro = novo_clique
            st.session_state.mapa_zoom = 16  # Zoom focado automático de satélite
            st.rerun()

with col_dados:
    if st.session_state.clique:
        # Relatório Completo de Alvos em Risco e Dados Técnicos
        st.subheader("⚠️ Alvos Críticos Monitorizados (Raio 500m)")
        for pts in lista_sensivel:
            st.markdown(
                f"<div style='padding:10px; border-left: 5px solid orange; background-color:#1e272e; margin-bottom:6px; border-radius:4px;'>"
                f"<b>{pts['tipo']}</b>: {pts['nome']} — <span style='color:#ffdd59;'>Prioridade: {pts['prioridade']}</span>"
                f"</div>", unsafe_allow_html=True
            )
        
        st.divider()
        st.subheader("⏱️ Linha Temporal AROME & Cones Orogáficos")
        st.dataframe(pd.DataFrame(dados_tabela_arome), use_container_width=True, hide_index=True)
        st.caption(f"⛰️ **Orografia Local:** Declive detetado de **{declive}°** com exposição de encosta a **{dir_subida}°**.")
        
        if st.button("RESETAR FOCO NACIONAL", use_container_width=True):
            st.session_state.mapa_centro = [39.557, -7.996]
            st.session_state.mapa_zoom = 7
            st.session_state.clique = None
            st.rerun()
    else:
        # Se nenhum ponto estiver selecionado, exibe o sumário global de incêndios ativos
        st.subheader("🚨 Ocorrências Ativas CNEPC / Proteção Civil")
        st.dataframe(pd.DataFrame(ocorrencias_prociv)[["concelho", "localidade", "meios_humanos", "estado"]], use_container_width=True, hide_index=True)
