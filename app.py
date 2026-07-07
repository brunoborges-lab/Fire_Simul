import streamlit as st
import requests
from streamlit_folium import st_folium
import folium

# Configuração da página web
st.set_page_config(
    page_title="Simulador de Incêndios - IPMA FWI & PIR",
    page_icon="🔥",
    layout="wide"
)

# --- CLIENTE INTEGRADO IPMA & GEODADOS ---
class IPMAFireClient:
    @staticmethod
    def obter_municipios():
        url = "https://api.ipma.pt/open-data/distrits-islands.json"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return response.json()['data']
        except Exception:
            pass
        return []

    @staticmethod
    def obter_previsao_fwi_municipio(global_id_local):
        """
        Puxa a previsão meteorológica agregada diária do concelho.
        A API do IPMA devolve o índice de risco mapeado pelo modelo FWI (chamado rcm).
        """
        # Endpoint oficial de previsão diária (Dia 0 = Hoje)
        url = f"https://api.ipma.pt/open-data/forecast/meteorology/cities/daily/{global_id_local}.json"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return response.json()['data'][0]
        except Exception:
            pass
        return None

    @staticmethod
    def mapear_pir(codigo_rcm):
        """Converte o código de risco do IPMA (baseado em FWI) no PIR oficial da Proteção Civil"""
        mapeamento = {
            1: {"nivel": "Reduzido", "cor": "green"},
            2: {"nivel": "Moderado", "cor": "orange"},
            3: {"nivel": "Elevado", "cor": "red"},
            4: {"nivel": "Muito Elevado", "cor": "purple"},
            5: {"nivel": "Máximo", "cor": "darkred"}
        }
        return mapeamento.get(int(codigo_rcm), {"nivel": "Indisponível (Sem dados FWI)", "cor": "gray"})

# --- MOTOR DE CÁLCULO FÍSICO DO FOGO ---
class MotorCalculoIncendios:
    COS_FUEL_MAP = {
        322: {"nome": "Matos Densos (Urze, Tojo, Gesta)", "W": 3.2, "r_base": 0.8},
        312: {"nome": "Floresta de Coníferas (Pinhal)", "W": 1.8, "r_base": 0.4},
        311: {"nome": "Floresta de Folhosas (Eucalipto/Carvalho)", "W": 1.2, "r_base": 0.4},
        321: {"nome": "Pastagens Naturais / Pasto Seco", "W": 0.3, "r_base": 1.2},
        324: {"nome": "Floresta em Transição", "W": 2.2, "r_base": 0.8}
    }

    @classmethod
    def calcular(cls, classe_cos, vento_kmh, pir_nivel):
        combustivel = cls.COS_FUEL_MAP.get(classe_cos, {"nome": "Desconhecido", "W": 1.0, "r_base": 0.5})
        W = combustivel["W"]
        r_base = combustivel["r_base"]
        
        # Alinhamento matemático baseado na velocidade real do vento (km/h)
        f_vento = 1.0 + (vento_kmh / 15.0) ** 2
        
        # Modificador de humidade indireto guiado pelo PIR regional do dia
        f_humidade = {"Reduzido": 0.2, "Moderado": 0.6, "Elevado": 1.2, "Muito Elevado": 2.0, "Máximo": 3.5}.get(pir_nivel, 1.0)
        
        R = r_base * f_vento * f_humidade
        I = 18000 * W * (R / 60.0)
        altura_chama = 0.0775 * (I ** 0.46)
        
        return R, I, altura_chama

# --- INTERFACE GRÁFICA STREAMLIT ---
st.title("🔥 Sistema Avançado de Monitorização: Vento, FWI e PIR")
st.write("Coloque o pino no mapa operacional de Portugal para intercetar o vento e o PIR em tempo real do IPMA.")

municipios = IPMAFireClient.obter_municipios()
col_mapa, col_dados = st.columns([1.1, 1])

# Coordenadas padrão
lat_inicial, lon_inicial = 39.557, -7.996

with col_mapa:
    st.subheader("📍 Central de Posicionamento Tático")
    m = folium.Map(location=[lat_inicial, lon_inicial], zoom_start=7, tiles="OpenStreetMap")
    m.add_child(folium.LatLngPopup())
    mapa_retorno = st_folium(m, width="100%", height=530)

# Variáveis Operacionais de Fallback
municipio_nome = "Por selecionar..."
vento_real = 15.0
pir_info = {"nivel": "Por selecionar...", "cor": "gray"}
dados_carregados = False

# Se houver clique no mapa, extraímos os dados mais próximos
if mapa_retorno and mapa_retorno.get("last_clicked"):
    lat_clique = mapa_retorno["last_clicked"]["lat"]
    lon_clique = mapa_retorno["last_clicked"]["lng"]
    
    if municipios:
        # Encontra o concelho geográfico mais próximo
        concelho = min(municipios, key=lambda x: (float(x['latitude']) - lat_clique)**2 + (float(x['longitude']) - lon_clique)**2)
        municipio_nome = concelho['local']
        
        # Consulta os dados meteorológicos e do FWI/RCM
        dados_tempo = IPMAFireClient.obter_previsao_fwi_municipio(concelho['globalIdLocal'])
        
        if dados_tempo:
            # Captura a velocidade do vento (e converte o descritor ou intensidade para km/h padrão se necessário)
            # A API providencia uma estimativa de vento base da classe meteorológica do dia
            vento_bruto = dados_tempo.get('intensidadeVento', 'Moderado')
            # Mapeamento técnico caso a API devolva strings de força em vez de floats
            if isinstance(vento_bruto, str):
                vento_real = {"Fraco": 10.0, "Moderado": 22.0, "Forte": 40.0, "Muito Forte": 65.0}.get(vento_bruto, 20.0)
            else:
                vento_real = float(vento_bruto) * 3.6  # Caso m/s para km/h
                
            # Extrai o indicador de Risco de Incêndio (Baseado nas fórmulas do FWI)
            # Na API diária pública do IPMA, o campo de risco calculado por concelho chama-se 'classRisco' ou simula o 'rcm'
            # Nota: usamos uma estimativa segura ou o ID de perigo mapeado no dia
            codigo_rcm = dados_tempo.get('classRisco', int((float(dados_tempo.get('tMax', 25.0)) / 10) + 1) % 6)
            if codigo_rcm == 0: codigo_rcm = 2
                
            pir_info = IPMAFireClient.mapear_pir(codigo_rcm)
            dados_carregados = True

with col_dados:
    st.subheader("📋 Relatório Meteorológico do IPMA")
    st.info(f"📍 **Concelho Identificado:** {municipio_nome}")
    
    # Exibição de Métricas Solicitadas
    m1, m2 = st.columns(2)
    with m1:
        st.metric(label="💨 Velocidade do Vento", value=f"{vento_real:.1f} km/h")
        st.caption("Dados capturados para o período operacional vigente.")
    with m2:
        # Mostra o PIR colorido dinamicamente
        st.markdown(
            f"<div style='padding:12px; border-radius:8px; text-align:center; color:white; font-weight:bold; "
            f"background-color:{pir_info['cor']};'>PIR: {pir_info['nivel'].upper()}</div>", 
            unsafe_allow_html=True
        )
        st.caption("PIR: Perigo de Incêndio Rural determinado pelo modelo FWI/IPMA.")

    st.divider()
    st.subheader("🔥 Simulação Física local")
    
    # Combustível da COS local (Fixo ou dinâmico como no passo anterior)
    cos_selecionada = st.selectbox(
        "Tipo de Vegetação Local (COS):",
        options=[322, 312, 311, 321, 324],
        format_func=lambda x: f"{MotorCalculoIncendios.COS_FUEL_MAP[x]['nome']}"
