from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.utils import get_color_from_hex

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
        
        if I < 500: status, cor = "BAIXO (Ataque Manual)", "#2ecc71"
        elif I < 2000: status, cor = "MODERADO (Ataque c/ Viaturas)", "#f1c40f"
        elif I < 4000: status, cor = "ELEVADO (Apoio Aéreo / Controfogo)", "#e67e22"
        else: status, cor = "EXTREMO (Fora de Capacidade)", "#e74c3c"
            
        return combustivel["nome"], R, I, altura_chama, status, cor

class FireApp(App):
    def build(self):
        self.title = "Calculadora de Incêndios"
        main_layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        
        main_layout.add(Label(text="Código CORINE (Ex: 312-Pinhal, 322-Matos):", size_hint_y=None, height=30))
        self.input_corine = TextInput(text="322", multiline=False, size_hint_y=None, height=40)
        main_layout.add(self.input_corine)
        
        main_layout.add(Label(text="Velocidade do Vento (km/h):", size_hint_y=None, height=30))
        self.input_vento = TextInput(text="25", multiline=False, size_hint_y=None, height=40)
        main_layout.add(self.input_vento)
        
        main_layout.add(Label(text="Índice FFMC (IPMA):", size_hint_y=None, height=30))
        self.input_ffmc = TextInput(text="91.5", multiline=False, size_hint_y=None, height=40)
        main_layout.add(self.input_ffmc)
        
        btn_calcular = Button(text="CALCULAR COMPORTAMENTO", size_hint_y=None, height=50, background_color=get_color_from_hex("#34495e"))
        btn_calcular.bind(on_press=self.processar_calculo)
        main_layout.add(btn_calcular)
        
        scroll = ScrollView()
        self.lbl_resultado = Label(text="Insira os dados e clique em Calcular.", size_hint_y=None, halign="left", valign="top", markup=True)
        self.lbl_resultado.bind(texture_size=self.lbl_resultado.setter('size'))
        scroll.add_widget(self.lbl_resultado)
        main_layout.add(scroll)
        return main_layout

    def processar_calculo(self, instance):
        try:
            corine = int(self.input_corine.text)
            vento = float(self.input_vento.text)
            ffmc = float(self.input_ffmc.text)
            nome, R, I, chama, status, cor = MotorCalculoIncendios.calcular(corine, vento, ffmc)
            
            self.lbl_resultado.text = (
                f"[b]Combustível:[/b] {nome}\n"
                f"[b]Velocidade (R):[/b] {R:.2f} m/min\n"
                f"[b]Intensidade (I):[/b] {I:.2f} kW/m\n"
                f"[b]Alt. Chama:[/b] {chama:.2f} metros\n\n"
                f"[b]PERIGO:[/b] [color={cor}]{status}[/color]"
            )
        except ValueError:
            self.lbl_resultado.text = "[color=#e74c3c]Insira valores válidos.[/color]"

if __name__ == '__main__':
    FireApp().run()
