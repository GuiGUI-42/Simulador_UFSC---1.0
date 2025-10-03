from flask import Flask, render_template, request, jsonify, redirect
import numpy as np
import control as ctl
import scipy.signal  # Adicione esta linha junto com os outros imports
import io
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)

@app.route('/')
def home():
    return redirect('/principal')

@app.route('/principal')
def principal():
    return render_template('principal.html')

@app.route('/malhaaberta')
def pagina2():
    return render_template('pagina2.html')

@app.route('/simuladorcomp')
def pagina4():
    return render_template('pagina4.html')

@app.route('/blocos')
def blocos():
    return render_template('bloco.html')

@app.route('/alocacao')
def alocacao():
    return render_template('alocacao.html')

@app.route('/atualizar', methods=['POST'])
def atualizar():
    data = request.get_json()
    tipo = data.get("tipo", "Caso 1")

    # Recebe os parâmetros da planta
    p1_1 = float(data.get("p1_1", -1))
    z_1 = float(data.get("z_1", 0))
    p1_2 = float(data.get("p1_2", -1))
    p2_2 = float(data.get("p2_2", -2))
    z_2 = float(data.get("z_2", 0))

    # Define a função de transferência da planta
    if tipo == "Caso 1":
        num = np.poly([z_1])
        den = np.poly([p1_1])
    elif tipo == "Caso 2":
        num = np.poly([z_2])
        den = np.poly([p1_2, p2_2])
    else:
        num = [1]
        den = [1]

    G = ctl.tf(num, den)

    # Define as funções de transferência
    latex_planta = f"\\[ G_{{planta}}(s) = \\frac{{{np.poly1d(num)}}}{{{np.poly1d(den)}}} \\]"
    latex_controlador = "\\[ G_{{controlador}}(s) = \\frac{{s + 1}}{{s + 2}} \\]"
    latex_open = "\\[ G_{{open}}(s) = G_{{planta}}(s) \\cdot G_{{controlador}}(s) \\]"
    latex_closed = "\\[ G_{{closed}}(s) = \\frac{{G_{{open}}(s)}}{{1 + G_{{open}}(s)}} \\]"

    # Gera os gráficos
    fig, axs = plt.subplots(1, 2, figsize=(12, 6))

    # Diagrama de Polos e Zeros
    zeros = np.roots(num)
    poles = np.roots(den)
    axs[0].scatter(np.real(zeros), np.imag(zeros), label="Zeros", color="blue")
    axs[0].scatter(np.real(poles), np.imag(poles), label="Polos", color="red")
    axs[0].set_title("Diagrama de Polos e Zeros")
    axs[0].grid(True)
    axs[0].legend()

    # Resposta ao Degrau (Malha Aberta)
    T, yout = ctl.step_response(G)
    axs[1].plot(T, yout)
    axs[1].set_title("Resposta ao Degrau (Malha Aberta)")
    axs[1].grid(True)

    t_perturb = float(data.get("t_perturb", 20))
    amp_perturb = float(data.get("amp_perturb", 0.5))

    # Resposta ao degrau (sem perturbação)
    T, yout_step = ctl.step_response(G)

    # Resposta ao degrau + perturbação
    T_long = np.linspace(0, 50, 1000)
    u = np.ones_like(T_long)
    u[T_long >= t_perturb] += amp_perturb
    T_resp, yout_perturb = ctl.forced_response(G, T_long, u)

    return jsonify({
        "latex_planta": latex_planta,
        "latex_controlador": latex_controlador,
        "latex_open": latex_open,
        "latex_closed": latex_closed,
        "plot_data": {
            "T": T_long.tolist(),
            "yout_step": np.interp(T_long, T, yout_step).tolist(),
            "yout_perturb": yout_perturb.tolist(),
            "t_perturb": t_perturb,
            "amp_perturb": amp_perturb
        }
    })

@app.route('/atualizar_bode', methods=['POST'])
def atualizar_bode():
    data = request.get_json()
    polos_planta = [float(p) for p in data.get("polos_planta", [-1])]
    zeros_planta = [float(z) for z in data.get("zeros_planta", [0])]
    polos_controlador = [float(p) for p in data.get("polos_controlador", [-1])]
    zeros_controlador = [float(z) for z in data.get("zeros_controlador", [0])]
    ganho_controlador = float(data.get("ganho_controlador", 1.0))

    print("polos_planta:", polos_planta)
    print("zeros_planta:", zeros_planta)
    print("polos_controlador:", polos_controlador)
    print("zeros_controlador:", zeros_controlador)
    print("ganho_controlador:", ganho_controlador)

    zeros_planta_filtrados = [z for z in zeros_planta if abs(z) > 1e-8]
    polos_planta_filtrados = [p for p in polos_planta if abs(p) > 1e-8]
    zeros_controlador_filtrados = [z for z in zeros_controlador if abs(z) > 1e-8]
    polos_controlador_filtrados = [p for p in polos_controlador if abs(p) > 1e-8]

    num_planta = np.poly(zeros_planta_filtrados) if zeros_planta_filtrados else np.array([1.0])
    den_planta = np.poly(polos_planta_filtrados)
    num_controlador = np.poly(zeros_controlador_filtrados) if zeros_controlador_filtrados else np.array([1.0])
    num_controlador = ganho_controlador * num_controlador
    den_controlador = np.poly(polos_controlador_filtrados)

    num_open = np.polymul(num_planta, num_controlador)
    den_open = np.polymul(den_planta, den_controlador)
    G_open = ctl.tf(num_open, den_open)

    omega = np.logspace(-2, 2, 500)  # Frequências de 0.01 a 100 rad/s
    mag, phase, omega = ctl.bode(G_open, omega=omega, dB=True, plot=False)

    bode_data = {
        "data": [
            {
                "x": omega.tolist(),
                "y": 20 * np.log10(mag).tolist(),
                "type": "scatter",
                "mode": "lines",
                "name": "Magnitude"
            },
            {
                "x": omega.tolist(),
                "y": np.degrees(phase).tolist(),
                "type": "scatter",
                "mode": "lines",
                "name": "Fase",
                "yaxis": "y2"
            }
        ],
        "layout": {
            "title": "Diagrama de Bode",
            "xaxis": {"title": "Frequência (rad/s)", "type": "log"},
            "yaxis": {"title": "Magnitude (dB)"},
            "yaxis2": {
                "title": "Fase (graus)",
                "overlaying": "y",
                "side": "right"
            },
            "legend": {"x": 0, "y": 1.1, "orientation": "h"}
        }
    }

    return jsonify({"bode_data": bode_data})

@app.route('/atualizar_nyquist', methods=['POST'])
def atualizar_nyquist():
    data = request.get_json()
    polos_planta = [float(p) for p in data.get("polos_planta", [-1])]
    zeros_planta = [float(z) for z in data.get("zeros_planta", [0])]
    polos_controlador = [float(p) for p in data.get("polos_controlador", [-1])]
    zeros_controlador = [float(z) for z in data.get("zeros_controlador", [0])]
    ganho_controlador = float(data.get("ganho_controlador", 1.0))

    zeros_planta_filtrados = [z for z in zeros_planta if abs(z) > 1e-8]
    polos_planta_filtrados = [p for p in polos_planta if abs(p) > 1e-8]
    zeros_controlador_filtrados = [z for z in zeros_controlador if abs(z) > 1e-8]
    polos_controlador_filtrados = [p for p in polos_controlador if abs(p) > 1e-8]

    num_planta = np.poly(zeros_planta_filtrados) if zeros_planta_filtrados else np.array([1.0])
    den_planta = np.poly(polos_planta_filtrados) if polos_planta_filtrados else np.array([1.0])
    num_controlador = np.poly(zeros_controlador_filtrados) if zeros_controlador_filtrados else np.array([1.0])
    num_controlador = ganho_controlador * num_controlador
    den_controlador = np.poly(polos_controlador_filtrados) if polos_controlador_filtrados else np.array([1.0])

    num_open = np.polymul(num_planta, num_controlador)
    den_open = np.polymul(den_planta, den_controlador)
    G_open = ctl.tf(num_open, den_open)

    omega = np.logspace(-2, 2, 500)
    _, H, _ = ctl.freqresp(G_open, omega)
    real = np.real(H[0]).tolist() if H.ndim == 3 else np.real(H).tolist()
    imag = np.imag(H[0]).tolist() if H.ndim == 3 else np.imag(H).tolist()

    nyquist_data = {
        "data": [
            {"x": real, "y": imag, "mode": "lines", "name": "Nyquist"},
            {"x": real, "y": [-i for i in imag], "mode": "lines", "name": "Nyquist (espelhado)", "line": {"dash": "dash"}}
        ],
        "layout": {
            "title": "Diagrama de Nyquist",
            "xaxis": {"title": "Eixo Real"},
            "yaxis": {"title": "Eixo Imaginário"},
            "showlegend": True,
            "yaxis_scaleanchor": "x",
            "yaxis_scaleratio": 1
        }
    }
    return jsonify({"nyquist_data": nyquist_data})

@app.route('/atualizar_pagina4', methods=['POST'])
def atualizar_pagina4():
    data = request.get_json()
    polos_planta = [float(p) for p in data.get("polos_planta", [-1])]
    zeros_planta = [float(z) for z in data.get("zeros_planta", [0])]
    polos_controlador = [float(p) for p in data.get("polos_controlador", [-1])]
    zeros_controlador = [float(z) for z in data.get("zeros_controlador", [0])]
    ganho_controlador = float(data.get("ganho_controlador", 1.0))
    ganho_planta = float(data.get("ganho_planta", 1.0))

    t_perturb_fechada = float(data.get("t_perturb_fechada", 20))
    amp_perturb_fechada = float(data.get("amp_perturb_fechada", 0.5))

    # Ensure num_planta and den_planta are arrays
    num_planta = np.array([ganho_planta]) * (np.poly(zeros_planta) if zeros_planta else np.array([1.0]))
    den_planta = np.poly(polos_planta) if polos_planta else np.array([1.0])
    num_controlador = np.array([ganho_controlador]) * (np.poly(zeros_controlador) if zeros_controlador else np.array([1.0]))
    den_controlador = np.poly(polos_controlador) if polos_controlador else np.array([1.0])

    G_planta = ctl.tf(num_planta, den_planta)
    G_controlador = ctl.tf(num_controlador, den_controlador)
    G_closed = ctl.feedback(G_planta * G_controlador)

    # Resposta ao degrau (Malha Aberta - apenas planta)
    T_open, yout_open = ctl.step_response(G_planta)
    plot_open_data = {
        "data": [
            {"x": T_open.tolist(), "y": yout_open.tolist(), "mode": "lines", "name": "Resposta ao Degrau (Malha Aberta)"}
        ],
        "layout": {"title": "Resposta ao Degrau (Malha Aberta)", "xaxis": {"title": "Tempo (s)"}, "yaxis": {"title": "Amplitude"}}
    }

    # Resposta ao degrau (Malha Fechada - planta e controlador)
    T = np.linspace(0, 50, 1000)
    _, yout_closed = ctl.forced_response(G_closed, T, np.ones_like(T))
    u_perturb = np.ones_like(T)
    u_perturb[T >= t_perturb_fechada] += amp_perturb_fechada
    _, yout_perturb = ctl.forced_response(G_closed, T, u_perturb)
    _, yout_open_interp = ctl.forced_response(G_planta, T, np.ones_like(T))

    plot_closed_data = {
        "data": [
            {"x": T.tolist(), "y": yout_closed.tolist(), "mode": "lines", "name": "Sem Perturbação"},
            {"x": T.tolist(), "y": yout_perturb.tolist(), "mode": "lines", "name": "Com Perturbação"},
            {"x": T.tolist(), "y": yout_open_interp.tolist(), "mode": "lines", "name": "Malha Aberta", "line": {"dash": "dash"}}
        ],
        "layout": {"title": "Resposta ao Degrau (Malha Fechada)", "xaxis": {"title": "Tempo (s)"}, "yaxis": {"title": "Amplitude"}}
    }

    # LaTeX das FTs
    latex_planta_polinomial = f"\\[ G(s) = \\frac{{{latex_poly(num_planta, 's')}}}{{{latex_poly(den_planta, 's')}}} \\]"
    latex_planta_fatorada = f"\\[ G(s) = \\frac{{{latex_factored(zeros_planta, 's')}}}{{{latex_factored(polos_planta, 's')}}} \\]"
    latex_planta_parcial = latex_partial_fraction(num_planta, den_planta, 's')

    

    latex_controlador_polinomial = f"\\[ G_c(s) = {ganho_controlador:.3g} \\cdot \\frac{{{latex_poly(np.poly(zeros_controlador) if zeros_controlador else [1.0], 's')}}}{{{latex_poly(den_controlador, 's')}}} \\]"
    latex_controlador_fatorada = f"\\[ G_c(s) = {ganho_controlador:.3g} \\cdot \\frac{{{latex_factored(zeros_controlador, 's')}}}{{{latex_factored(polos_controlador, 's')}}} \\]"
    latex_controlador_parcial = f"\\[ G_c(s) = {ganho_controlador:.3g} \\cdot {latex_partial_fraction(np.poly(zeros_controlador) if zeros_controlador else [1.0], den_controlador, 's')[3:-3]} \\]"


    return jsonify({
        "latex_planta_polinomial": latex_planta_polinomial,
        "latex_planta_fatorada": latex_planta_fatorada,
        "latex_planta_parcial": latex_planta_parcial,
        "latex_controlador_polinomial": latex_controlador_polinomial,
        "latex_controlador_fatorada": latex_controlador_fatorada,
        "latex_controlador_parcial": latex_controlador_parcial,
        "plot_open_data": plot_open_data,
        "plot_closed_data": plot_closed_data
    })

@app.route('/atualizar_pz_closed', methods=['POST'])
def atualizar_pz_closed():
    data = request.get_json()
    polos_planta = [float(p) for p in data.get("polos_planta", [-1])]
    zeros_planta = [float(z) for z in data.get("zeros_planta", [0])]
    polos_controlador = [float(p) for p in data.get("polos_controlador", [-1])]
    zeros_controlador = [float(z) for z in data.get("zeros_controlador", [0])]
    ganho_controlador = float(data.get("ganho_controlador", 1.0))
    tipo = data.get("tipo", "malha_fechada")  # Recebe o tipo do frontend

    # Funções de transferência
    num_planta = np.poly(zeros_planta) if zeros_planta else np.array([1.0])
    den_planta = np.poly(polos_planta) if polos_planta else np.array([1.0])
    num_controlador = ganho_controlador * (np.poly(zeros_controlador) if zeros_controlador else np.array([1.0]))
    den_controlador = np.poly(polos_controlador) if polos_controlador else np.array([1.0])

    if tipo == "planta":
        # Apenas planta
        zeros = np.roots(num_planta)
        polos = np.roots(den_planta)
        titulo = "Diagrama de Polos e Zeros da Planta"
    elif tipo == "controlador":
        # Apenas controlador
        zeros = np.roots(num_controlador)
        polos = np.roots(den_controlador)
        titulo = "Diagrama de Polos e Zeros do Controlador"
    elif tipo == "malha_aberta":
        # Malha aberta: G(s)*Gc(s)
        num_open = np.polymul(num_planta, num_controlador)
        den_open = np.polymul(den_planta, den_controlador)
        zeros = np.roots(num_open)
        polos = np.roots(den_open)
        titulo = "Diagrama de Polos e Zeros (Malha Aberta)"
    else:
        # Malha fechada
        G_planta = ctl.tf(num_planta, den_planta)
        G_controlador = ctl.tf(num_controlador, den_controlador)
        G_closed = ctl.feedback(G_planta * G_controlador)
        num_closed = np.array(G_closed.num).flatten()
        den_closed = np.array(G_closed.den).flatten()
        zeros = np.roots(num_closed)
        polos = np.roots(den_closed)
        titulo = "Diagrama de Polos e Zeros (Malha Fechada)"

    plot_pz_closed = {
        "data": [
            {"x": np.real(zeros).tolist(), "y": np.imag(zeros).tolist(), "mode": "markers", "name": "Zeros", "marker": {"color": "blue", "size": 12, "symbol": "circle"}},
            {"x": np.real(polos).tolist(), "y": np.imag(polos).tolist(), "mode": "markers", "name": "Polos", "marker": {"color": "red", "size": 14, "symbol": "x"}}
        ],
        "layout": {
            "title": titulo,
            "xaxis": {"title": "Re", "zeroline": True},
            "yaxis": {"title": "Im", "zeroline": True, "scaleanchor": "x", "scaleratio": 1},
            "showlegend": True
        }
    }

    return jsonify({"plot_pz_closed": plot_pz_closed})


@app.route('/enviar_feedback', methods=['POST'])
def enviar_feedback():
    data = request.get_json()
    texto = data.get('feedback', '')
    # Configurações do seu e-mail
    remetente = 'syscoufsc@gmail.com'
    senha = 'jvey wybi xcnm znko'  # Use senha de app para Gmail
    destinatario = 'syscoufsc@gmail.com'  # Ou outro e-mail de destino

    msg = MIMEText(texto)
    msg['Subject'] = 'Feedback do Simulador'
    msg['From'] = remetente
    msg['To'] = destinatario

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(remetente, senha)
            server.sendmail(remetente, destinatario, msg.as_string())
        return jsonify({'status': 'ok'})
    except Exception as e:
        print("Erro ao enviar feedback:", e)
        return jsonify({'status': 'erro', 'mensagem': str(e)}), 500

def latex_poly(coeffs, var='s'):
    coeffs = np.array(coeffs, dtype=float)
    # Remove zeros à direita (constante no início)
    coeffs = np.trim_zeros(coeffs, 'f')
    # Se todos os zeros são zero, o numerador vira [1, 0, 0, ...]
    # Queremos mostrar "1" se todos os coeficientes, exceto o primeiro, são zero
    if len(coeffs) > 1 and np.allclose(coeffs[1:], 0) and np.isclose(coeffs[0], 1):
        return "1"
    if len(coeffs) == 1 and np.isclose(coeffs[0], 1):
        return "1"
    ordem = len(coeffs) - 1
    termos = []
    for i, c in enumerate(coeffs):
        pot = ordem - i
        if abs(c) < 1e-10:
            continue
        c_str = f"{c:.3g}" if abs(c) != 1 or pot == 0 else ("-" if c == -1 else "")
        if pot > 1:
            termos.append(f"{c_str}{var}^{pot}")
        elif pot == 1:
            termos.append(f"{c_str}{var}")
        else:
            termos.append(f"{c_str}")
    return " + ".join(termos).replace("+ -", "- ")

def latex_monic(coeffs, var='s'):
    if abs(coeffs[0]) < 1e-10:
        return latex_poly(coeffs, var)
    norm = coeffs / coeffs[0]
    return latex_poly(norm, var)

def latex_factored(roots, var='s'):
    if len(roots) == 0 or np.allclose(roots, 0):
        return "1"
    termos = []
    for r in roots:
        if abs(r) < 1e-10:
            termos.append(f"{var}")
        else:
            # Exibe (s - r) para qualquer valor de r (positivo ou negativo)
            sinal = "-" if r >= 0 else "+"
            valor = abs(r)
            if valor < 1e-10:
                termos.append(f"{var}")
            else:
                termos.append(f"({var} {sinal} {valor:.3g})")
    return "".join(termos)

def latex_partial_fraction(num, den, var='s'):
    """
    Gera a representação LaTeX da decomposição em frações parciais.
    """
    import scipy.signal
    import numpy as np

    # Remove zeros desnecessários no numerador e denominador
    num = np.trim_zeros(num, 'f')
    den = np.trim_zeros(den, 'f')

    # Verifica se o numerador ou denominador é vazio
    if len(num) == 0 or len(den) == 0:
        return "\\[ 0 \\]"

    try:
        # Calcula os resíduos, polos e termos constantes
        r, p, k = scipy.signal.residue(num, den)

        # Organiza os polos e resíduos em um dicionário para tratar polos repetidos
        termos = {}
        for ri, pi in zip(r, p):
            pi = np.round(pi, 4)  # Arredonda o polo
            if pi not in termos:
                termos[pi] = []
            termos[pi].append(ri)  # Adiciona o resíduo ao polo correspondente

        # Gera os termos da fração parcial
        latex_termos = []
        for pi, residuos in termos.items():
            for i, ri in enumerate(residuos):
                ri = np.round(ri, 4)  # Arredonda o resíduo
                if abs(ri) > 1e-8:  # Ignora resíduos nulos
                    expoente = i + 1
                    sinal = "+" if pi >= 0 else "-"
                    valor = abs(pi)
                    if expoente == 1:
                        latex_termos.append(f"\\frac{{{ri:.4g}}}{{{var} {sinal} {valor:.4g}}}")
                    else:
                        latex_termos.append(f"\\frac{{{ri:.4g}}}{{({var} {sinal} {valor:.4g})^{expoente}}}")

        # Adiciona os termos constantes, se existirem
        if k is not None and len(k) > 0:
            for i, ki in enumerate(k):
                if abs(ki) > 1e-8:  # Ignora termos constantes nulos
                    latex_termos.append(f"{ki:.4g}{var}^{len(k)-i-1}" if i < len(k) - 1 else f"{ki:.4g}")

        # Retorna a expressão LaTeX
        return "\\[ " + " + ".join(latex_termos) + " \\]" if latex_termos else "\\[ 0 \\]"
    except Exception as e:
        return f"\\[ \\text{{Erro ao calcular frações parciais: {e}}} \\]"


@app.route('/nyquist_pagina2', methods=['POST'])
def nyquist_pagina2():
    data = request.get_json()
    polos_planta = [float(p) for p in data.get("polos_planta", [-1])]
    zeros_planta = [float(z) for z in data.get("zeros_planta", [0])]

    # Filtrar zeros e polos
    zeros_planta_filtrados = [z for z in zeros_planta if abs(z) > 1e-8]
    num_planta = np.poly(zeros_planta_filtrados) if zeros_planta_filtrados else np.array([1.0])
    den_planta = np.poly(polos_planta)

    # Definir G_planta
    G_planta = ctl.tf(num_planta, den_planta)

    # Gerar o diagrama de Nyquist
    fig, ax = plt.subplots(figsize=(7, 4))  # Apenas aumenta o tamanho, não altera escala
    ctl.nyquist_plot(G_planta, omega=np.logspace(-2, 2, 500), ax=ax, color='b')
    ax.set_title("Diagrama de Nyquist")
    ax.set_xlabel("Re")
    ax.set_ylabel("Im")
    ax.grid(True)
    plt.tight_layout()

    # Salvar o gráfico como imagem base64
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    return jsonify({"nyquist_img": img_base64})

@app.route('/nyquist_pagina4', methods=['POST'])
def nyquist_pagina4():
    data = request.get_json()
    polos_planta = [float(p) for p in data.get("polos_planta", [-1])]
    zeros_planta = [float(z) for z in data.get("zeros_planta", [0])]
    polos_controlador = [float(p) for p in data.get("polos_controlador", [-1])]
    zeros_controlador = [float(z) for z in data.get("zeros_controlador", [0])]
    ganho_controlador = float(data.get("ganho_controlador", 1.0))

    zeros_planta_filtrados = [z for z in zeros_planta if abs(z) > 1e-8]
    polos_planta_filtrados = [p for p in polos_planta if abs(p) > 1e-8]
    zeros_controlador_filtrados = [z for z in zeros_controlador if abs(z) > 1e-8]
    polos_controlador_filtrados = [p for p in polos_controlador if abs(p) > 1e-8]

    num_planta = np.poly(zeros_planta_filtrados) if zeros_planta_filtrados else np.array([1.0])
    den_planta = np.poly(polos_planta_filtrados) if polos_planta_filtrados else np.array([1.0])
    num_controlador = np.poly(zeros_controlador_filtrados) if zeros_controlador_filtrados else np.array([1.0])
    num_controlador = ganho_controlador * num_controlador
    den_controlador = np.poly(polos_controlador_filtrados) if polos_controlador_filtrados else np.array([1.0])

    # Definir G_open corretamente
    G_open = ctl.tf(np.polymul(num_planta, num_controlador), np.polymul(den_planta, den_controlador))

    fig, ax = plt.subplots(figsize=(7, 4))  # Apenas aumenta o tamanho, não altera escala
    ctl.nyquist_plot(G_open, omega=np.logspace(-2, 2, 500), ax=ax, color='b')
    ax.set_title("Diagrama de Nyquist")
    ax.set_xlabel("Re")
    ax.set_ylabel("Im")
    ax.grid(True)
    # Remova os set_xlim/set_ylim para manter a escala automática
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    return jsonify({"nyquist_img": img_base64})

@app.route('/simular_saida', methods=['POST'])
def simular_saida():
    data = request.get_json()
    num = data.get("num", [1])
    den = data.get("den", [1, 1])
    t_final = float(data.get("t_final", 40))
    n_points = int(data.get("n_points", 200))
    try:
        import scipy.signal
        import numpy as np
        num = [float(x) for x in num]
        den = [float(x) for x in den]
        system = scipy.signal.TransferFunction(num, den)
        t = np.linspace(0, t_final, n_points)
        t, y = scipy.signal.step(system, T=t)
        return jsonify({"t": t.tolist(), "y": y.tolist()})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/discreto')
def pagina_discreto():
    return render_template('discreto.html')

@app.route('/atualizar_discreto', methods=['POST'])
def atualizar_discreto():
    data = request.get_json()
    # Recebe os parâmetros da planta
    ordem = int(data.get("ordem", 2))
    polos = [float(data.get(f"polo_{i+1}", -1)) for i in range(ordem)]
    zeros = [float(data.get(f"zero_{i+1}", 0)) for i in range(ordem)]
    Ts = float(data.get("Ts", 0.1))

    # Função de transferência contínua
    num = np.poly([z for z in zeros if abs(z) > 1e-8]) if any(abs(z) > 1e-8 for z in zeros) else np.array([1.0])
    den = np.poly([p for p in polos if abs(p) > 1e-8]) if any(abs(p) > 1e-8 for p in polos) else np.array([1.0])
    Gs = ctl.tf(num, den)

    # Discretização (bilinear)
    Gz = ctl.sample_system(Gs, Ts, method='tustin')

    # Resposta ao degrau contínua
    T_cont, y_cont = ctl.step_response(Gs, T=np.linspace(0, Ts*50, 500))
    # Resposta ao degrau discreta
    T_disc = np.arange(0, Ts*50, Ts)
    tout, y_disc = ctl.step_response(Gz, T=T_disc)

    # LaTeX das FTs
    latex_Gs = f"\\[ G(s) = \\frac{{{latex_poly(num, 's')}}}{{{latex_poly(den, 's')}}} \\]"
    return jsonify({
        "latex_Gs": latex_Gs,
        "plot_continuo": {
            "x": T_cont.tolist(),
            "y": y_cont.tolist()
        },
        "plot_discreto": {
            "x": tout.tolist(),
            "y": y_disc.tolist()
        }
    })

@app.route('/pid')
def pid_page():
    return render_template('pid.html')

@app.route('/pid_latex', methods=['POST'])
def pid_latex():
    data = request.get_json()
    polos_planta = [float(p) for p in data.get("polos_planta", [-1])]
    zeros_planta = [float(z) for z in data.get("zeros_planta", [0])]

    zeros_planta_filtrados = [z for z in zeros_planta if abs(z) > 1e-8]
    num_planta = np.poly(zeros_planta_filtrados) if zeros_planta_filtrados else np.array([1.0])
    den_planta = np.poly(polos_planta)

    latex_plant = f"\\[ G(s) = \\frac{{{latex_poly(num_planta, 's')}}}{{{latex_poly(den_planta, 's')}}} \\]"

    ctrl_type = data.get('ctrl_type', 'PID')
    K = float(data.get('ctrl_k', 1))
    Ti = float(data.get('ctrl_ti', 1))
    Td = float(data.get('ctrl_td', 1))
    N = float(data.get('ctrl_n', 10))
    b = float(data.get('ctrl_b', 0.5))

    # Mostra os parâmetros reais na expressão LaTeX
    if ctrl_type == "P":
        latex_ctrl = r"\[ G_c(s) = %.2f \]" % K
    elif ctrl_type == "I":
        latex_ctrl = r"\[ G_c(s) = \frac{%.2f}{%.2f\,s} \]" % (K, Ti)
    elif ctrl_type == "PI":
        latex_ctrl = r"\[ G_c(s) = %.2f \left(1 + \frac{1}{%.2f\,s}\right) \]" % (K, Ti)
    elif ctrl_type == "PD":
        latex_ctrl = r"\[ G_c(s) = %.2f \left(1 + %.2f\,s \frac{%.2f}{s+%.2f}\right) \]" % (K, Td, N, N)
    else:  # PID
        latex_ctrl = r"\[ G_c(s) = %.2f \left(1 + \frac{1}{%.2f\,s} + \frac{%.2f\,s\,%.2f}{s+%.2f}\right) \]" % (K, Ti, Td, N, N)

    return jsonify({
        "latex_plant": latex_plant,
        "latex_ctrl": latex_ctrl
    })

@app.route('/pid_simular', methods=['POST'])
def pid_simular():
    data = request.get_json()
    polos_planta = [float(p) for p in data.get("polos_planta", [-1])]
    zeros_planta = [float(z) for z in data.get("zeros_planta", [0])]

    zeros_planta_filtrados = [z for z in zeros_planta if abs(z) > 1e-8]
    num_planta = np.poly(zeros_planta_filtrados) if zeros_planta_filtrados else np.array([1.0])
    den_planta = np.poly(polos_planta)
    G = ctl.tf(num_planta, den_planta)

    ctrl_type = data.get('ctrl_type', 'PID')
    K = float(data.get('ctrl_k', 1))
    Ti = float(data.get('ctrl_ti', 1))
    Td = float(data.get('ctrl_td', 1))
    N = float(data.get('ctrl_n', 10))
    b = float(data.get('ctrl_b', 0.5))

    s = ctl.tf([1, 0], [0, 1])
    if ctrl_type == "P":
        Gc = ctl.tf([K], [1])
    elif ctrl_type == "I":
        Gc = ctl.tf([K], [Ti, 0])
    elif ctrl_type == "PI":
        Gc = ctl.tf([K*Ti, K], [Ti, 0])
    elif ctrl_type == "PD":
        numc = [K*Td*N, K]
        denc = [1, N]
        Gc = ctl.tf(numc, denc)
    else:  # PID
        numc = [K*Td*N, K*N, K]
        denc = [Ti, Ti*N, 0]
        Gc = ctl.tf(numc, denc)

    sys_cl = ctl.feedback(Gc*G, 1)
    T = np.linspace(0, 40, 400)
    T, y = ctl.step_response(sys_cl, T)
    # Corrigido: forced_response retorna apenas 2 valores nas versões recentes
    _, u = ctl.forced_response(Gc, T, 1 - y)

    plot_processo = {
        "data": [
            {"x": T.tolist(), "y": y.tolist(), "type": "scatter", "name": "Saída do Processo"}
        ],
        "layout": {"title": "Saída do Processo", "xaxis": {"title": "Tempo (s)"}, "yaxis": {"title": "y(t)"}}
    }
    plot_controlador = {
        "data": [
            {"x": T.tolist(), "y": u.tolist(), "type": "scatter", "name": "Saída do Controlador"}
        ],
        "layout": {"title": "Saída do Controlador", "xaxis": {"title": "Tempo (s)"}, "yaxis": {"title": "u(t)"}}
    }

    return jsonify({
        "plot_processo": plot_processo,
        "plot_controlador": plot_controlador
    })

@app.route('/state')
def state_page():
    return render_template('state.html')

@app.route('/state_equation', methods=['POST'])
def state_equation():
    data = request.get_json()
    masses = data.get("masses", [])
    springs = data.get("springs", [])
    dampers = data.get("dampers", [])

    n = len(masses)
    import sympy as sp
    M = sp.zeros(n)
    K = sp.zeros(n)
    C = sp.zeros(n)

    for i, m in enumerate(masses):
        M[i, i] = m
    for s in springs:
        i, j, k = s['from'], s['to'], s['k']
        if j == -1:
            K[i, i] += k
        else:
            K[i, i] += k
            K[j, j] += k
            K[i, j] -= k
            K[j, i] -= k
    for d in dampers:
        i, j, c = d['from'], d['to'], d['c']
        if j == -1:
            C[i, i] += c
        else:
            C[i, i] += c
            C[j, j] += c
            C[i, j] -= c
            C[j, i] -= c

    try:
        Minv = M.inv()
        A_top = sp.zeros(n, n).row_join(sp.eye(n))
        A_bot = (-Minv*K).row_join(-Minv*C)
        A = A_top.col_join(A_bot)
        eq_latex = (
            "M \\ddot{x} + C \\dot{x} + K x = 0 \\\\"
            "M = " + sp.latex(M) + "\\quad "
            "C = " + sp.latex(C) + "\\quad "
            "K = " + sp.latex(K)
        )
        A_latex = sp.latex(A)
    except Exception as e:
        eq_latex = f"Erro ao montar sistema: {e}"
        A_latex = ""

    return {
        "equation": eq_latex,
        "A_latex": A_latex
    }

@app.route('/alocacao_polos_backend', methods=['POST'])
def alocacao_polos_backend():
    import numpy as np
    import control as ctl

    data = request.get_json()
    polos_planta = [float(p) for p in data.get("polos_planta", [-0.0758])]
    zeros_planta = [float(z) for z in data.get("zeros_planta", [])]
    ganho_planta = float(data.get("ganho_planta", 1.0))
    polos_controlador = [float(p) for p in data.get("polos_controlador", [])]
    zeros_controlador = [float(z) for z in data.get("zeros_controlador", [])]
    ganho_controlador = float(data.get("ganho_controlador", 1.0))
    ts_multiplier = float(data.get("ts_multiplier", 0.5))

    # Função de transferência da planta
    num_planta = ganho_planta * (np.poly(zeros_planta) if zeros_planta else np.array([1.0]))
    den_planta = np.poly(polos_planta) if polos_planta else np.array([1.0])
    G_planta = ctl.tf(num_planta, den_planta)

    # Função de transferência do controlador
    num_controlador = ganho_controlador * (np.poly(zeros_controlador) if zeros_controlador else np.array([1.0]))
    den_controlador = np.poly(polos_controlador) if polos_controlador else np.array([1.0])
    G_controlador = ctl.tf(num_controlador, den_controlador)

    # Malha aberta e fechada
    G_open = G_planta * G_controlador
    G_closed = ctl.feedback(G_open)

    # Resposta ao degrau (Malha Aberta)
    T_open = np.linspace(0, 50, 1000)
    _, yout_open = ctl.step_response(G_open, T_open)
    y_final_open = yout_open[-1]
    tol_open = 0.05 * abs(y_final_open)
    idx_settle_open = np.where(np.abs(yout_open - y_final_open) > tol_open)[0]
    ts_aberta = T_open[idx_settle_open[-1] + 1] if len(idx_settle_open) > 0 else T_open[-1]

    # Resposta ao degrau (Malha Fechada)
    T_closed = np.linspace(0, 50, 1000)
    _, yout_closed = ctl.step_response(G_closed, T_closed)
    y_final_closed = yout_closed[-1]
    tol_closed = 0.05 * abs(y_final_closed)
    idx_settle_closed = np.where(np.abs(yout_closed - y_final_closed) > tol_closed)[0]
    ts_fechada = T_closed[idx_settle_closed[-1] + 1] if len(idx_settle_closed) > 0 else T_closed[-1]

    # Tempo de assentamento desejado (multiplicador)
    ts_desejado = ts_aberta * ts_multiplier

    # Pd (polo dominante desejado) - regras típicas
    ordem = len(polos_planta)
    if ordem == 1:
        pd_val = 3 / ts_desejado if ts_desejado > 0 else 0
        pd_formula = r"P_d = \frac{3}{T_{s,fechada}}"
    elif ordem == 2:
        pd_val = 4.8 / ts_desejado if ts_desejado > 0 else 0
        pd_formula = r"P_d = \frac{4.8}{T_{s,fechada}}"
    elif ordem == 3:
        pd_val = 6.3 / ts_desejado if ts_desejado > 0 else 0
        pd_formula = r"P_d = \frac{6.3}{T_{s,fechada}}"
    else:
        pd_val = 3 / ts_desejado if ts_desejado > 0 else 0
        pd_formula = r"P_d = \frac{3}{T_{s,fechada}}"
    pd_value = f"{pd_val:.4g}" if ts_desejado > 0 else ""

    # Polinômio característico atual
    poly_caracteristico = None
    try:
        Dp = den_planta
        Dc = den_controlador
        Np = num_planta
        Nc = num_controlador
        poly_atual = np.polyadd(np.polymul(Dp, Dc), np.polymul(Np, Nc))
        poly_caracteristico = f"\\( {latex_poly(poly_atual, 's')} \\)"
    except Exception:
        poly_caracteristico = ""

    # Polinômio desejado (todos polos em -Pd)
    if ordem > 0 and pd_val > 0:
        poly_desejado_coeffs = np.poly([-pd_val] * ordem)
        poly_desejado = f"\\( {latex_poly(poly_desejado_coeffs, 's')} \\)"
    else:
        poly_desejado = ""

    # Diagrama de Polos e Zeros (Malha Fechada)
    try:
        num_closed = np.array(G_closed.num).flatten()
        den_closed = np.array(G_closed.den).flatten()
        zeros_closed = np.roots(num_closed)
        poles_closed = np.roots(den_closed)
    except Exception:
        zeros_closed = []
        poles_closed = []

    plot_pz_closed = {
        "data": [
            {"x": np.real(zeros_closed).tolist(), "y": np.imag(zeros_closed).tolist(), "mode": "markers", "name": "Zeros", "marker": {"color": "blue", "size": 12, "symbol": "circle"}},
            {"x": np.real(poles_closed).tolist(), "y": np.imag(poles_closed).tolist(), "mode": "markers", "name": "Polos", "marker": {"color": "red", "size": 14, "symbol": "x"}}
        ],
        "layout": {
            "title": "Diagrama de Polos e Zeros (Malha Fechada)",
            "xaxis": {"title": "Re", "zeroline": True},
            "yaxis": {"title": "Im", "zeroline": True, "scaleanchor": "x", "scaleratio": 1},
            "showlegend": True
        }
    }

    # Diagrama de Polos e Zeros (Malha Aberta)
    try:
        num_open = np.array(G_open.num).flatten()
        den_open = np.array(G_open.den).flatten()
        zeros_open = np.roots(num_open)
        poles_open = np.roots(den_open)
    except Exception:
        zeros_open = []
        poles_open = []

    plot_pz_open = {
        "data": [
            {"x": np.real(zeros_open).tolist(), "y": np.imag(zeros_open).tolist(), "mode": "markers", "name": "Zeros", "marker": {"color": "blue", "size": 12, "symbol": "circle"}},
            {"x": np.real(poles_open).tolist(), "y": np.imag(poles_open).tolist(), "mode": "markers", "name": "Polos", "marker": {"color": "red", "size": 14, "symbol": "x"}}
        ],
        "layout": {
            "title": "Diagrama de Polos e Zeros (Malha Aberta)",
            "xaxis": {"title": "Re", "zeroline": True},
            "yaxis": {"title": "Im", "zeroline": True, "scaleanchor": "x", "scaleratio": 1},
            "showlegend": True
        }
    }

    # Gráfico da resposta ao degrau (Malha Fechada)
    plot_closed = {
        "data": [
            {"x": T_closed.tolist(), "y": yout_closed.tolist(), "mode": "lines", "name": "Resposta ao Degrau (Malha Fechada)"}
        ],
        "layout": {
            "title": "Resposta ao Degrau (Malha Fechada)",
            "xaxis": {"title": "Tempo (s)"},
            "yaxis": {"title": "Amplitude"}
        }
    }

    try:
        polos = np.roots(den_planta)
        zeros = np.roots(num_planta)
    except Exception:
        polos = []
        zeros = []
    plot_pz_planta = {
        "data": [
            {"x": np.real(zeros).tolist(), "y": np.imag(zeros).tolist(), "mode": "markers", "name": "Zeros", "marker": {"color": "blue", "size": 12, "symbol": "circle"}},
            {"x": np.real(polos).tolist(), "y": np.imag(polos).tolist(), "mode": "markers", "name": "Polos", "marker": {"color": "red", "size": 14, "symbol": "x"}}
        ],
        "layout": {
            "title": "Diagrama de Polos e Zeros da Planta",
            "xaxis": {"title": "Re", "zeroline": True},
            "yaxis": {"title": "Im", "zeroline": True, "scaleanchor": "x", "scaleratio": 1},
            "showlegend": True
        }
    }

    # Diagrama de Polos e Zeros (Controlador)
    try:
        polos_ctrl = np.roots(den_controlador)
        zeros_ctrl = np.roots(num_controlador)
    except Exception:
        polos_ctrl = []
        zeros_ctrl = []
    plot_pz_controlador = {
        "data": [
            {"x": np.real(zeros_ctrl).tolist(), "y": np.imag(zeros_ctrl).tolist(), "mode": "markers", "name": "Zeros", "marker": {"color": "blue", "size": 12, "symbol": "circle"}},
            {"x": np.real(polos_ctrl).tolist(), "y": np.imag(polos_ctrl).tolist(), "mode": "markers", "name": "Polos", "marker": {"color": "red", "size": 14, "symbol": "x"}}
        ],
        "layout": {
            "title": "Diagrama de Polos e Zeros do Controlador",
            "xaxis": {"title": "Re", "zeroline": True},
            "yaxis": {"title": "Im", "zeroline": True, "scaleanchor": "x", "scaleratio": 1},
            "showlegend": True
        }
    }

    # Gráfico da resposta ao degrau (Malha Aberta)
    plot_open = {
        "data": [
            {"x": T_open.tolist(), "y": yout_open.tolist(), "mode": "lines", "name": "Resposta ao Degrau (Malha Aberta)"}
        ],
        "layout": {
            "title": "Resposta ao Degrau (Malha Aberta)",
            "xaxis": {"title": "Tempo (s)"},
            "yaxis": {"title": "Amplitude"}
        }
    }

    # LaTeX das FTs
    latex_planta = f"\\( G(s) = {ganho_planta:.3g} \\cdot \\frac{{{latex_factored(zeros_planta, 's')}}}{{{latex_factored(polos_planta, 's')}}} \\)"
    latex_controlador = f"\\( G_c(s) = {ganho_controlador:.3g} \\cdot \\frac{{{latex_factored(zeros_controlador, 's')}}}{{{latex_factored(polos_controlador, 's')}}} \\)"
    
    return jsonify({
        "tempo_assentamento_aberta": round(float(ts_aberta), 3),
        "tempo_assentamento_fechada": round(float(ts_fechada), 3),
        "ts_desejado": round(float(ts_desejado), 3),
        "pd_value": pd_value,
        "pd_formula": f"({pd_formula})",
        "poly_caracteristico": poly_caracteristico,
        "poly_desejado": poly_desejado,
        "latex_planta": latex_planta,
        "latex_controlador": latex_controlador,
        "plot_pz_closed": plot_pz_closed,
        "plot_pz_open": plot_pz_open,
        "plot_pz_planta": plot_pz_planta,
        "plot_pz_controlador": plot_pz_controlador,
        "plot_closed": plot_closed,
        "plot_open": plot_open
    })

@app.route('/atualizar_pagina2', methods=['POST'])
def atualizar_pagina2():
    data = request.get_json()
    polos_planta = [float(p) for p in data.get("polos_planta", [-1])]
    zeros_planta = [float(z) for z in data.get("zeros_planta", [0])]

    zeros_planta_filtrados = [z for z in zeros_planta if abs(z) > 1e-8]
    num_planta = np.poly(zeros_planta_filtrados) if zeros_planta_filtrados else np.array([1.0])
    den_planta = np.poly(polos_planta) if polos_planta else np.array([1.0])

    G_planta = ctl.tf(num_planta, den_planta)

    latex_planta_polinomial = (
        f"\\[ G(s) = \\frac{{{latex_poly(num_planta, 's')}}}{{{latex_poly(den_planta, 's')}}} \\]"
    )
    latex_planta_fatorada = (
        f"\\[ G(s) = \\frac{{{latex_factored(zeros_planta, 's')}}}{{{latex_factored(polos_planta, 's')}}} \\]"
    )
    latex_planta_parcial = (
    f"\\[ G(s) = {latex_partial_fraction(num_planta, den_planta, 's')[3:-3]} \\]"
    )

    # Diagrama de Polos e Zeros
    zeros = np.roots(num_planta)
    polos = np.roots(den_planta)
    plot_pz_data = {
        "data": [
            {"x": np.real(zeros).tolist(), "y": np.imag(zeros).tolist(), "mode": "markers", "name": "Zeros", "marker": {"color": "blue", "size": 12, "symbol": "circle"}},
            {"x": np.real(polos).tolist(), "y": np.imag(polos).tolist(), "mode": "markers", "name": "Polos", "marker": {"color": "red", "size": 14, "symbol": "x"}}
        ],
        "layout": {
            "title": "Diagrama de Polos e Zeros",
            "xaxis": {"title": "Re", "zeroline": True},
            "yaxis": {"title": "Im", "zeroline": True, "scaleanchor": "x", "scaleratio": 1},
            "showlegend": True
        }
    }

    # Resposta ao Degrau (Malha Aberta)
    T = np.linspace(0, 20, 500)
    _, yout = ctl.step_response(G_planta, T)
    plot_open_data = {
        "data": [
            {"x": T.tolist(), "y": yout.tolist(), "mode": "lines", "name": "Resposta ao Degrau (Malha Aberta)"}
        ],
        "layout": {
            "title": "Resposta ao Degrau (Malha Aberta)",
            "xaxis": {"title": "Tempo (s)"},
            "yaxis": {"title": "Amplitude"}
        }
    }

    return jsonify({
        "latex_planta_polinomial": latex_planta_polinomial,
        "latex_planta_fatorada": latex_planta_fatorada,
        "latex_planta_parcial": latex_planta_parcial,
        "plot_pz_data": plot_pz_data,
        "plot_open_data": plot_open_data
    })

def latex_poly(coeffs, var='s'):
    coeffs = np.array(coeffs, dtype=float)
    # Remove zeros à direita (constante no início)
    coeffs = np.trim_zeros(coeffs, 'f')
    # Se todos os zeros são zero, o numerador vira [1, 0, 0, ...]
    # Queremos mostrar "1" se todos os coeficientes, exceto o primeiro, são zero
    if len(coeffs) > 1 and np.allclose(coeffs[1:], 0) and np.isclose(coeffs[0], 1):
        return "1"
    if len(coeffs) == 1 and np.isclose(coeffs[0], 1):
        return "1"
    ordem = len(coeffs) - 1
    termos = []
    for i, c in enumerate(coeffs):
        pot = ordem - i
        if abs(c) < 1e-10:
            continue
        c_str = f"{c:.3g}" if abs(c) != 1 or pot == 0 else ("-" if c == -1 else "")
        if pot > 1:
            termos.append(f"{c_str}{var}^{pot}")
        elif pot == 1:
            termos.append(f"{c_str}{var}")
        else:
            termos.append(f"{c_str}")
    return " + ".join(termos).replace("+ -", "- ")

def latex_monic(coeffs, var='s'):
    if abs(coeffs[0]) < 1e-10:
        return latex_poly(coeffs, var)
    norm = coeffs / coeffs[0]
    return latex_poly(norm, var)

def latex_factored(roots, var='s'):
    if len(roots) == 0 or np.allclose(roots, 0):
        return "1"
    termos = []
    for r in roots:
        if abs(r) < 1e-10:
            termos.append(f"{var}")
        else:
            # Exibe (s - r) para qualquer valor de r (positivo ou negativo)
            sinal = "-" if r >= 0 else "+"
            valor = abs(r)
            if valor < 1e-10:
                termos.append(f"{var}")
            else:
                termos.append(f"({var} {sinal} {valor:.3g})")
    return "".join(termos)

def latex_partial_fraction(num, den, var='s'):
    """
    Gera a representação LaTeX da decomposição em frações parciais.
    """
    import scipy.signal
    import numpy as np

    # Remove zeros desnecessários no numerador e denominador
    num = np.trim_zeros(num, 'f')
    den = np.trim_zeros(den, 'f')

    # Verifica se o numerador ou denominador é vazio
    if len(num) == 0 or len(den) == 0:
        return "\\[ 0 \\]"

    try:
        # Calcula os resíduos, polos e termos constantes
        r, p, k = scipy.signal.residue(num, den)

        # Organiza os polos e resíduos em um dicionário para tratar polos repetidos
        termos = {}
        for ri, pi in zip(r, p):
            pi = np.round(pi, 4)  # Arredonda o polo
            if pi not in termos:
                termos[pi] = []
            termos[pi].append(ri)  # Adiciona o resíduo ao polo correspondente

        # Gera os termos da fração parcial
        latex_termos = []
        for pi, residuos in termos.items():
            for i, ri in enumerate(residuos):
                ri = np.round(ri, 4)  # Arredonda o resíduo
                if abs(ri) > 1e-8:  # Ignora resíduos nulos
                    expoente = i + 1
                    sinal = "+" if pi >= 0 else "-"
                    valor = abs(pi)
                    if expoente == 1:
                        latex_termos.append(f"\\frac{{{ri:.4g}}}{{{var} {sinal} {valor:.4g}}}")
                    else:
                        latex_termos.append(f"\\frac{{{ri:.4g}}}{{({var} {sinal} {valor:.4g})^{expoente}}}")

        # Adiciona os termos constantes, se existirem
        if k is not None and len(k) > 0:
            for i, ki in enumerate(k):
                if abs(ki) > 1e-8:  # Ignora termos constantes nulos
                    latex_termos.append(f"{ki:.4g}{var}^{len(k)-i-1}" if i < len(k) - 1 else f"{ki:.4g}")

        # Retorna a expressão LaTeX
        return "\\[ " + " + ".join(latex_termos) + " \\]" if latex_termos else "\\[ 0 \\]"
    except Exception as e:
        return f"\\[ \\text{{Erro ao calcular frações parciais: {e}}} \\]"


@app.route('/sinais')
def sinais_page():
    return render_template('sinais.html')

@app.route('/sinais_backend', methods=['POST'])
def sinais_backend():
    data = request.get_json()
    num = [float(x) for x in data.get("num", [1])]
    den = [float(x) for x in data.get("den", [1, 1])]

    G = ctl.tf(num, den)
    zeros = np.roots(num)
    polos = np.roots(den)
    mod_zeros = np.abs(zeros)
    mod_polos = np.abs(polos)

    T = np.linspace(0, 20, 500)
    T, yout = ctl.step_response(G, T)

    latex_ft = f"\\[ G(s) = \\frac{{{latex_poly(num, 's')}}}{{{latex_poly(den, 's')}}} \\]"

    # Novo: cálculo do diagrama de Bode se solicitado
    bode_data = None
    if data.get("bode", False):
        try:
            omega = np.logspace(-2, 2, 500)
            mag, phase, omega = ctl.bode(G, omega=omega, dB=True, plot=False)
            bode_data = {
                "data": [
                    {
                        "x": omega.tolist(),
                        "y": 20 * np.log10(mag).tolist(),
                        "type": "scatter",
                        "mode": "lines",
                        "name": "Magnitude"
                    },
                    {
                        "x": omega.tolist(),
                        "y": np.degrees(phase).tolist(),
                        "type": "scatter",
                        "mode": "lines",
                        "name": "Fase",
                        "yaxis": "y2"
                    }
                ],
                "layout": {
                    "title": "Diagrama de Bode",
                    "xaxis": {"title": "Frequência (rad/s)", "type": "log"},
                    "yaxis": {"title": "Magnitude (dB)"},
                    "yaxis2": {
                        "title": "Fase (graus)",
                        "overlaying": "y",
                        "side": "right"
                    },
                    "legend": {"x": 0, "y": 1.1, "orientation": "h"}
                }
            }
        except Exception as e:
            bode_data = None

    # Corrigir: polos e zeros para string (JSON serializável)
    def complex_to_str(z):
        if isinstance(z, complex):
            if abs(z.imag) < 1e-8:
                return f"{z.real:.6g}"
            else:
                return f"{z.real:.6g}{'+' if z.imag >= 0 else '-'}{abs(z.imag):.6g}j"
        else:
            return f"{z:.6g}"

    zeros_json = [complex_to_str(z) for z in zeros]
    polos_json = [complex_to_str(p) for p in polos]

    return jsonify({
        "latex_ft": latex_ft,
        "mod_zeros": mod_zeros.tolist(),
        "mod_polos": mod_polos.tolist(),
        "zeros": zeros_json,
        "polos": polos_json,
        "step_response": {
            "T": T.tolist(),
            "y": yout.tolist()
        },
        "bode_data": bode_data
    })

@app.route('/raizes')
def raizes():
    return render_template('raizes.html')

@app.route('/sinais_edo', methods=['POST'])
def sinais_edo():
    import sympy as sp
    from scipy.signal import lti, step
    data = request.get_json()
    eq_str = data.get("edo", "")
    t = np.linspace(0, 20, 500)
    try:
        # Parse EDO do tipo: y'' + 2y' + y = u(t)
        y = sp.Function('y')
        u = sp.Function('u')
        t_sym = sp.symbols('t')
        eq = sp.sympify(eq_str.replace("=", "-(") + ")", locals={'y': y(t_sym), "u": u(t_sym)})
        eq = sp.Eq(eq, 0)
        # Coeficientes da EDO (ordem até 2)
        lhs = eq.lhs.expand()
        a2 = lhs.coeff(y(t_sym).diff(t_sym, 2))
        a1 = lhs.coeff(y(t_sym).diff(t_sym, 1))
        a0 = lhs.coeff(y(t_sym))
        b0 = -lhs.coeff(u(t_sym))
        num = [float(b0)]
        den = [float(a2), float(a1), float(a0)]
        system = lti(num, den)
        tout, yout = step(system, T=t)
        latex = f"\\[ {sp.latex(eq)} \\]"
        return jsonify({"t": tout.tolist(), "y": yout.tolist(), "latex": latex})
    except Exception as e:
        return jsonify({"t": [], "y": [], "latex": f"Erro ao interpretar EDO: {e}"})

@app.route('/novo_grafico_fechado', methods=['POST'])
def novo_grafico_fechado():
    data = request.get_json()
    polos_planta = [float(p) for p in data.get("polos_planta", [-1])]
    zeros_planta = [float(z) for z in data.get("zeros_planta", [0])]
    polos_controlador = [float(p) for p in data.get("polos_controlador", [-1])]
    zeros_controlador = [float(z) for z in data.get("zeros_controlador", [0])]
    ganho_controlador = float(data.get("ganho_controlador", 1.0))
    ganho_planta = float(data.get("ganho_planta", 1.0))

    # Funções de transferência
    num_planta = ganho_planta * (np.poly(zeros_planta) if zeros_planta else np.array([1.0]))
    den_planta = np.poly(polos_planta) if polos_planta else np.array([1.0])
    num_controlador = ganho_controlador * (np.poly(zeros_controlador) if zeros_controlador else np.array([1.0]))
    den_controlador = np.poly(polos_controlador) if polos_controlador else np.array([1.0])

    G_planta = ctl.tf(num_planta, den_planta)
    G_controlador = ctl.tf(num_controlador, den_controlador)
    G_closed = ctl.feedback(G_planta * G_controlador)

    # Resposta ao degrau (Malha Fechada - sem perturbação)
    T = np.linspace(0, 50, 1000)
    _, yout_closed = ctl.step_response(G_closed, T)

    # Dados para o novo gráfico
    novo_grafico_data = {
        "data": [
            {"x": T.tolist(), "y": yout_closed.tolist(), "mode": "lines", "name": "Resposta ao Degrau (Malha Fechada)"}
        ],
        "layout": {
            "title": "Resposta ao Degrau (Malha Fechada)",
            "xaxis": {"title": "Tempo (s)"},
            "yaxis": {"title": "Amplitude"}
        }
    }

    return jsonify({"novo_grafico_data": novo_grafico_data})


@app.route('/lgr_backend', methods=['POST'])
def lgr_backend():
    data = request.get_json()
    polos_planta = [float(p) for p in data.get("polos_planta", [-1])]
    zeros_planta = [float(z) for z in data.get("zeros_planta", [])]
    ganho = float(data.get("ganho", 1.0))

    try:
        num = ganho * (np.poly(zeros_planta) if zeros_planta else np.array([1.0]))
        den = np.poly(polos_planta) if polos_planta else np.array([1.0])
        G = ctl.tf(num, den)

        latex_planta = f"\\[ G(s) = {ganho:.3g} \\cdot \\frac{{{latex_factored(zeros_planta, 's')}}}{{{latex_factored(polos_planta, 's')}}} \\]"

        # Lugar das Raízes (LGR)
        try:
            rlist, klist = ctl.root_locus(G, plot=False)
            lgr_data = []
            for i in range(rlist.shape[1]):
                lgr_data.append({
                    "x": np.real(rlist[:, i]).tolist(),
                    "y": np.imag(rlist[:, i]).tolist(),
                    "mode": "lines",
                    "name": f"Comportamento {i+1}",
                    "line": {"color": "#0074d9"},
                    "marker": {"size": 4}
                })
            polos = np.roots(den)
            zeros = np.roots(num)
            lgr_data.append({
                "x": np.real(polos).tolist(),
                "y": np.imag(polos).tolist(),
                "mode": "markers",
                "name": "Polos",
                "marker": {"color": "red", "size": 12, "symbol": "x"}
            })
            lgr_data.append({
                "x": np.real(zeros).tolist(),
                "y": np.imag(zeros).tolist(),
                "mode": "markers",
                "name": "Zeros",
                "marker": {"color": "blue", "size": 10, "symbol": "circle"}
            })
            lgr_layout = {
                "title": "Lugar das Raízes",
                "xaxis": {"title": "Re", "zeroline": True},
                "yaxis": {"title": "Im", "zeroline": True, "scaleanchor": "x", "scaleratio": 1},
                "showlegend": True
            }
            lgr_plot = {"data": lgr_data, "layout": lgr_layout}
            klist_out = klist.tolist()
        except Exception as e:
            print("Erro no root_locus:", e)
            lgr_plot = {"data": [], "layout": {"title": f"Erro ao calcular LGR: {e}"}}
            klist_out = []

        return jsonify({
            "latex_planta": latex_planta,
            "lgr_plot": lgr_plot,
            "klist": klist_out
        })
    except Exception as e:
        print("Erro geral no lgr_backend:", e)
        return jsonify({"lgr_plot": {"data": [], "layout": {"title": f"Erro geral: {e}"}}})

if __name__ == '__main__':
    app.run(debug=True)
    #host='0.0.0.0'