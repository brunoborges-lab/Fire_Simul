import streamlit as st
import requests
from streamlit_folium import st_folium
import folium

# Configuração da página web
st.set_page_config(
    page_title="Calculadora de Incêndios PT com Mapa",
    page_icon="🔥",
    layout="wide"
)

# --- CLASSE DE CONEXÃO À API DO IPMA ---
class IPMAClient:
    @staticmethod
    def obter_municipios():
        """Vai buscar a lista de todos os municípios e respetivos códigos do IPMA"""
        url = "https://api.ipma.pt/open-data/distrits-islands.json"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return response.json()['data']
        except Exception:
            pass
        return []

    @staticmethod
    def obter_previsao_municipio(global_id_local):
        """Obtém a previsão meteorológica para o município selecionado (hoje)"""
        url = f"https://api.ipma.pt/open-data/forecast/meteorology/cities/daily/{global_id_local}.json"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                # Retorna os dados do dia de hoje (primeiro elemento da lista)
                return response.json()['data'][0]
        except Exception:
            pass
        return None

# --- MOTOR DE CÁLCULO ---
class MotorCalculoIncendios:
    CORINE_FUEL_MAP = {
        322: {"nome": "Matos Densos (Urze, Tojo, Gesta)", "W": 3.2},
        312: {"nome": "Floresta de Coníferas (Pinhal)", "W": 1.8},
        311: {"nome": "Floresta de Folhosas (Eucalipto/Carvalho)", "W": 1.2},
        321: {"nome": "Pastagens Naturais / Pasto Seco", "W": 0.3},
        324: {"nome": "Floresta em Transição", "W": 2.2}
    }

    @classmethod
    def calcular(cls, classe_corine, vento, ffmc):
        combustivel = cls.CORINE_FUEL_MAP.get(classe_corine, {"nome": "Desconhecido", "W": 1.0})
        W = combustivel["W"]
        f_vento = 1.0 + (vento / 15.0) ** 2
        f_humidade = 0.1 if ffmc < 80 else (ffmc - 75) / 4.0
        r_base = 0.8 if classe_corine in [322, 324] else (1.2 if classe_corine == 321 else 0.4)
        
        R = r_base * f_vento * f_humidade
        I = 18000 * W * (R / 60.0)
        altura_chama = 0.0775 * (I ** 0.46)
        
        if I < 500: status, cor = "BAIXO (Ataque Manual)", "green"
        elif I < 2000: status, cor = "MODERADO (Ataque c/ Viaturas)", "orange"
        elif I < 4000: status, cor = "ELEVADO (Apoio Aéreo)", "red"
        else: status, cor = "EXTREMO (Fora de Capacidade)", "purple"
            
        return combustivel["nome"], R, I, altura_chama, status, cor

# --- INTERFACE WEB ---
st.title("🔥 Simulador de Incêndios com Integração IPMA")
st.write("Clique no mapa de Portugal para colocar o pino e extrair os dados meteorológicos locais automaticamente.")

# Carregar lista de municípios do IPMA
municipios = IPMAClient.obter_municipios()

# Criar duas colunas: Esquerda para o Mapa, Direita para Dados e Cálculos
col_mapa, col_dados = st.columns([1.2, 1])

# Coordenadas padrão de início (Centro de Portugal - Mação)
lat_inicial, lon_inicial = 39.557, -7.996

with col_mapa:
    st.subheader("📍 Selecione o Local no Mapa")
    
    # Inicializar o mapa Folium
    m = folium.Map(location=[lat_inicial, lon_inicial], zoom_start=7, tiles="OpenStreetMap")
    
    # Adicionar o intercetor de cliques (Pino Dinâmico)
    m.add_child(folium.LatLngPopup())
    
    # Renderizar o mapa no Streamlit e capturar o clique do utilizador
    mapa_retorno = st_folium(m, width="100%", height=500)

# Valores padrão de vento e FFMC caso o utilizador não clique em lado nenhum
vento_ipma = 15.0
ffmc_calculado = 85.0
municipio_detetado = "Nenhum (Clique no mapa)"

# Se o utilizador clicou no mapa, intercetamos as coordenadas
if mapa_retorno and mapa_retorno.get("last_clicked"):
    lat_clique = mapa_retorno["last_clicked"]["lat"]
    lon_clique = mapa_retorno["last_clicked"]["lng"]
    
    # Encontrar o município do IPMA mais próximo por proximidade geográfica simples
    if municipios:
        mais_proximo = min(
            municipios, 
            key=lambda x: (float(x['latitude']) - lat_clique)**2 + (float(x['longitude']) - lon_clique)**2
        )
        municipio_detetado = f"{mais_proximo['local']}"
        global_id = mais_proximo['globalIdLocal']
        
        # Chamar a API do IPMA para este município
        dados_tempo = IPMAClient.obter_previsao_municipio(global_id)
        
        if dados_tempo:
            # O IPMA fornece a velocidade do vento (intensidadeVento) e a humidade
            # Como o IPMA não dá o FFMC direto na API pública diária, estimamos o FFMC 
            # com base na classe de probabilidade de precipitação e temperatura.
            vento_ipma = float(dados_tempo.get('intensidadeVento', 15.0)) * 3.6 # Converter m/s para km/h se necessário
            t_max = float(dados_tempo.get('tMax', 25.0))
            precipitacao = float(dados_tempo.get('precipitaProb', 0.0))
            
            # Algoritmo de aproximação técnica do FFMC para o simulador baseado no clima do dia
            ffmc_calculado = 70.0 + (t_max * 0.8) - (precipitacao * 0.3)
            if ffmc_calculado > 101: ffmc_calculado = 101.0

with col_dados:
    st.subheader("📝 Dados Operacionais e de Clima")
    st.info(f"📍 **Localidade Identificada:** {municipio_detetado}")
    
    # Inputs da simulação
    corine = st.selectbox(
        "Tipo de Combustível (CORINE):",
        options=[322, 312, 311, 321, 324],
        format_func=lambda x: f"{x} - {MotorCalculoIncendios.CORINE_FUEL_MAP[x]['nome']}"
    )
    
    # Inputs preenchidos automaticamente com dados do IPMA, mas editáveis se o bombeiro quiser ajustar
    vento = st.slider("Velocidade do Vento (km/h):", min_value=0, max_value=100, value=int(vento_ipma))
    ffmc = st.number_input("Índice FFMC (Estimado via IPMA):", min_value=0.0, max_value=101.0, value=round(ffmc_calculado, 1))

    st.divider()

    # Botão de cálculo
    if st.button("CALCULAR RISCO DE INCÊNDIO", type="primary", use_container_width=True):
        nome, R, I, chama, status, cor = MotorCalculoIncendios.calcular(corine, vento, ffmc)
        
        st.subheader("📊 Resultados da Frente de Fogo")
        
        c1, c2, c3 = st.columns(3)
        c1.metric(label="Velocidade de Avanço (R)", value=f"{R:.2f} m/min")
        c2.metric(label="Intensidade Linear (I)", value=f"{I:.2f} kW/m")
        c3.metric(label="Altura da Chama", value=f"{chama:.2f} m")
        
        if cor == "green": st.success(f"**Capacidade de Supressão:** {status}")
        elif cor == "orange": st.warning(f"**Capacidade de Supressão:** {status}")
        else: st.error(f"**Capacidade de Supressão:** {status}")
