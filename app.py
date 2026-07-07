import streamlit as st

# Configuração da página web
st.set_page_config(
    page_title="Calculadora de Incêndios PT",
    page_icon="🔥",
    layout="centered"
)

# Motor de Cálculo (A mesma lógica que usaste no Kivy)
class MotorCalculoIncendios:
    CORINE_FUEL_MAP = {
        311: {"nome": "Floresta de Folhosas (Eucalipto/Carvalho)", "W": 1.2},
        312: {"nome": "Floresta de Coníferas (Pinhal)", "W": 1.8},
        321: {"nome": "Pastagens Naturais / Pasto Seco", "W": 0.3},
        322: {"nome": "Matos Densos (Urze, Tojo, Gesta)", "W": 3.2},
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
st.title("🔥 Calculadora de Comportamento do Fogo")
st.subheader("Simulador Técnico para Incêndios Florestais")
st.write("Insira os dados operacionais abaixo para estimar o comportamento da frente de fogo.")

st.divider()

# Colunas para organizar os inputs de forma visual e limpa
col1, col2 = st.columns(2)

with col1:
    corine = st.selectbox(
        "Tipo de Combustível (CORINE):",
        options=[322, 312, 311, 321, 324],
        format_func=lambda x: f"{x} - {MotorCalculoIncendios.CORINE_FUEL_MAP[x]['nome']}"
    )
    vento = st.slider("Velocidade do Vento (km/h):", min_value=0, max_value=80, value=25)

with col2:
    ffmc = st.number_input("Índice FFMC (IPMA):", min_value=0.0, max_value=101.0, value=91.5, step=0.1)

st.divider()

# Botão de cálculo
if st.button("CALCULAR COMPORTAMENTO", type="primary", use_container_width=True):
    nome, R, I, chama, status, cor = MotorCalculoIncendios.calcular(corine, vento, ffmc)
    
    # Apresentação dos resultados em cartões visuais (Metrics)
    st.subheader("📊 Resultados da Simulação")
    
    c1, c2, c3 = st.columns(3)
    c1.metric(label="Velocidade de Propagação (R)", value=f"{R:.2f} m/min")
    c2.metric(label="Intensidade Linear (I)", value=f"{I:.2f} kW/m")
    c3.metric(label="Altura da Chama", value=f"{chama:.2f} metros")
    
    # Alerta visual de perigo com a cor correspondente
    if cor == "green": st.success(f"**Nível de Perigo:** {status}")
    elif cor == "orange": st.warning(f"**Nível de Perigo:** {status}")
    else: st.error(f"**Nível de Perigo:** {status}")
