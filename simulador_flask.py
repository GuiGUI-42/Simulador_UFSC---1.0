from flask import Flask, render_template, request, jsonify, redirect
import numpy as np
import control as ctl
import scipy.signal
import io
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)

# Páginas
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

@app.route('/discreto')
def pagina_discreto():
    return render_template('discreto.html')

@app.route('/pid')
def pid_page():
    return render_template('pid.html')

@app.route('/state')
def state_page():
    return render_template('state.html')

@app.route('/sinais')
def sinais_page():
    return render_template('sinais.html')

@app.route('/raizes')
def raizes():
    return render_template('raizes.html')


# Helpers LaTeX
def latex_poly(coeffs, var='s'):
    coeffs = np.array(coeffs, dtype=float)
    coeffs = np.trim_zeros(coeffs, 'f')
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
            sinal = "-" if r >= 0 else "+"
            valor = abs(r)
            if valor < 1e-10:
                termos.append(f"{var}")
            else:
                termos.append(f"({var} {sinal} {valor:.3g})")
    return "".join(termos)

def latex_partial_fraction(num, den, var='s'):
    num = np.trim_zeros(num, 'f')
    den = np.trim_zeros(den, 'f')
    if len(num) == 0 or len(den) == 0:
        return "\\[ 0 \\]"
    try:
        r, p, k = scipy.signal.residue(num, den)
        termos = {}
        for ri, pi in zip(r, p):
            pi = np.round(pi, 4)
            if pi not in termos:
                termos[pi] = []
            termos[pi].append(ri)
        latex_termos = []
        for pi, residuos in termos.items():
            for i, ri in enumerate(residuos):
                ri = np.round(ri, 4)
                if abs(ri) > 1e-8:
                    expoente = i + 1
                    sinal = "+" if pi >= 0 else "-"
                    valor = abs(pi)
                    if expoente == 1:
                        latex_termos.append(f"\\frac{{{ri:.4g}}}{{{var} {sinal} {valor:.4g}}}")
                    else:
                        latex_termos.append(f"\\frac{{{ri:.4g}}}{{({var} {sinal} {valor:.4g})^{expoente}}}")
        if k is not None and len(k) > 0:
            for i, ki in enumerate(k):
                if abs(ki) > 1e-8:
                    latex_termos.append(f"{ki:.4g}{var}^{len(k)-i-1}" if i < len(k) - 1 else f"{ki:.4g}")
        return "\\[ " + " + ".join(latex_termos) + " \\]" if latex_termos else "\\[ 0 \\]"
    except Exception as e:
        return f"\\[ \\text{{Erro ao calcular frações parciais: {e}}} \\ ]"


# Endpoints — Malha aberta simples com perturbação na entrada
@app.route('/atualizar', methods=['POST'])
def atualizar():
    data = request.get_json()
    tipo = data.get("tipo", "Caso 1")

    p1_1 = float(data.get("p1_1", -1))
    z_1 = float(data.get("z_1", 0))
    p1_2 = float(data.get("p1_2", -1))
    p2_2 = float(data.get("p2_2", -2))
    z_2 = float(data.get("z_2", 0))

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

    latex_planta = f"\\[ G_{{planta}}(s) = \\frac{{{np.poly1d(num)}}}{{{np.poly1d(den)}}} \\]"
    latex_controlador = "\\[ G_{{controlador}}(s) = \\frac{{s + 1}}{{s + 2}} \\]"
    latex_open = "\\[ G_{{open}}(s) = G_{{planta}}(s) \\cdot G_{{controlador}}(s) \\]"
    latex_closed = "\\[ G_{{closed}}(s) = \\frac{{G_{{open}}(s)}}{{1 + G_{{open}}(s)}} \\]"

    T, yout_step = ctl.step_response(G)
    T_long = np.linspace(0, 50, 1000)
    t_perturb = float(data.get("t_perturb", 20))
    amp_perturb = float(data.get("amp_perturb", 0.5))
    u = np.ones_like(T_long)
    u[T_long >= t_perturb] += amp_perturb
    _, yout_perturb = ctl.forced_response(G, T_long, u)

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


# Bode e Nyquist (planta*controlador em malha aberta)
@app.route('/atualizar_bode', methods=['POST'])
def atualizar_bode():
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
    num_controlador = ganho_controlador * (np.poly(zeros_controlador_filtrados) if zeros_controlador_filtrados else np.array([1.0]))
    den_controlador = np.poly(polos_controlador_filtrados) if polos_controlador_filtrados else np.array([1.0])

    num_open = np.polymul(num_planta, num_controlador)
    den_open = np.polymul(den_planta, den_controlador)
    G_open = ctl.tf(num_open, den_open)

    omega = np.logspace(-2, 2, 500)
    mag, phase, omega = ctl.bode(G_open, omega=omega, dB=True, plot=False)

    bode_data = {
        "data": [
            {"x": omega.tolist(), "y": (20*np.log10(mag)).tolist(), "type": "scatter", "mode": "lines", "name": "Magnitude"},
            {"x": omega.tolist(), "y": np.degrees(phase).tolist(),   "type": "scatter", "mode": "lines", "name": "Fase", "yaxis": "y2"}
        ],
        "layout": {
            "title": "Diagrama de Bode",
            "xaxis": {"title": "Frequência (rad/s)", "type": "log"},
            "yaxis": {"title": "Magnitude (dB)"},
            "yaxis2": {"title": "Fase (graus)", "overlaying": "y", "side": "right"},
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
    num_controlador = ganho_controlador * (np.poly(zeros_controlador_filtrados) if zeros_controlador_filtrados else np.array([1.0]))
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


# Página 4 — Malha fechada (sem filtro) + overlays + LaTeX
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

    num_planta = np.array([ganho_planta]) * (np.poly(zeros_planta) if zeros_planta else np.array([1.0]))
    den_planta = np.poly(polos_planta) if polos_planta else np.array([1.0])
    num_controlador = np.array([ganho_controlador]) * (np.poly(zeros_controlador) if zeros_controlador else np.array([1.0]))
    den_controlador = np.poly(polos_controlador) if polos_controlador else np.array([1.0])

    G_planta = ctl.tf(num_planta, den_planta)
    G_controlador = ctl.tf(num_controlador, den_controlador)
    G_closed = ctl.feedback(G_planta * G_controlador)

    T = np.linspace(0, 50, 1000)
    _, yout_closed = ctl.forced_response(G_closed, T, np.ones_like(T))

    u_ref = np.ones_like(T)
    u_ref[T >= t_perturb_fechada] += amp_perturb_fechada
    _, yout_closed_ref2 = ctl.forced_response(G_closed, T, u_ref)

    _, yout_open = ctl.forced_response(G_planta, T, np.ones_like(T))

    plot_closed_data = {
        "data": [
            {"x": T.tolist(), "y": yout_closed.tolist(), "mode": "lines", "name": "Sem Perturbação", "line": {"color": "#077FFF", "width": 3}},
            {"x": T.tolist(), "y": yout_closed_ref2.tolist(), "mode": "lines", "name": "Com Perturbação", "line": {"color": "#ff9800", "dash": "dash", "width": 2}},
            {"x": T.tolist(), "y": yout_open.tolist(), "mode": "lines", "name": "Malha Aberta", "line": {"color": "#06B900", "dash": "dash", "width": 3}}
        ],
        "layout": {"title": "Resposta ao Degrau", "xaxis": {"title": "Tempo (s)", "range": [0, 10]}, "yaxis": {"title": "Amplitude"}}
    }

    L = G_planta * G_controlador
    S = ctl.feedback(ctl.tf([1.0], [1.0]), L)
    Tq = ctl.feedback(G_planta, G_controlador)

    _, e_step = ctl.step_response(S, T)
    _, yq_step = ctl.step_response(Tq, T)

    error_closed_data = {"data": [{"x": T.tolist(), "y": e_step.tolist(), "mode": "lines", "name": "E/R", "line": {"color": "#000000", "dash": "solid", "width": 2}}]}
    perturb_closed_data = {"data": [{"x": T.tolist(), "y": yq_step.tolist(), "mode": "lines", "name": "Y/Q", "line": {"dash": "dash", "color": "#9c27b0"}}]}

    latex_planta_polinomial = f"\\[ G(s) = \\frac{{{latex_poly(num_planta, 's')}}}{{{latex_poly(den_planta, 's')}}} \\]"
    latex_planta_fatorada   = f"\\[ G(s) = \\frac{{{latex_factored(zeros_planta, 's')}}}{{{latex_factored(polos_planta, 's')}}} \\]"
    latex_planta_parcial    = latex_partial_fraction(num_planta, den_planta, 's')

    latex_controlador_polinomial = f"\\[ G_c(s) = {ganho_controlador:.3g} \\cdot \\frac{{{latex_poly(np.poly(zeros_controlador) if zeros_controlador else [1.0], 's')}}}{{{latex_poly(den_controlador, 's')}}} \\]"
    latex_controlador_fatorada   = f"\\[ G_c(s) = {ganho_controlador:.3g} \\cdot \\frac{{{latex_factored(zeros_controlador, 's')}}}{{{latex_factored(polos_controlador, 's')}}} \\]"
    latex_controlador_parcial    = f"\\[ G_c(s) = {ganho_controlador:.3g} \\cdot {latex_partial_fraction(np.poly(zeros_controlador) if zeros_controlador else [1.0], den_controlador, 's')[3:-3]} \\]"

    return jsonify({
        "latex_planta_polinomial": latex_planta_polinomial,
        "latex_planta_fatorada":   latex_planta_fatorada,
        "latex_planta_parcial":    latex_planta_parcial,
        "latex_controlador_polinomial": latex_controlador_polinomial,
        "latex_controlador_fatorada":   latex_controlador_fatorada,
        "latex_controlador_parcial":    latex_controlador_parcial,
        "plot_closed_data": plot_closed_data,
        "error_closed_data": error_closed_data,
        "perturb_closed_data": perturb_closed_data
    })


# PZ para diferentes seleções (malha aberta/fechada/erro/perturbação)
@app.route('/atualizar_pz_closed', methods=['POST'])
def atualizar_pz_closed():
    data = request.get_json(force=True)
    tipo = data.get("tipo", "malha_fechada")
    polos_planta = [float(p) for p in data.get("polos_planta", [-1])]
    zeros_planta = [float(z) for z in data.get("zeros_planta", [])]
    ganho_planta = float(data.get("ganho_planta", 1.0))
    polos_controlador = [float(p) for p in data.get("polos_controlador", [])]
    zeros_controlador = [float(z) for z in data.get("zeros_controlador", [])]
    ganho_controlador = float(data.get("ganho_controlador", 1.0))

    num_planta = ganho_planta * (np.poly(zeros_planta) if zeros_planta else np.array([1.0]))
    den_planta = np.poly(polos_planta) if polos_planta else np.array([1.0])
    num_controlador = ganho_controlador * (np.poly(zeros_controlador) if zeros_controlador else np.array([1.0]))
    den_controlador = np.poly(polos_controlador) if polos_controlador else np.array([1.0])

    G_planta = ctl.tf(num_planta, den_planta)
    G_controlador = ctl.tf(num_controlador, den_controlador)
    L = G_controlador * G_planta

    def snap_poles_for_display(poles, tol_imag_abs=1e-2, tol_pair=4e-2, round_decimals=1):
        poles = np.array(poles, dtype=complex)
        poles = np.array([complex(np.real(p), 0.0) if abs(np.imag(p)) <= tol_imag_abs else p for p in poles])
        reals_idx = [i for i, p in enumerate(poles) if abs(p.imag) == 0.0]
        used = set()
        for i in reals_idx:
            if i in used:
                continue
            for j in reals_idx:
                if j <= i or j in used:
                    continue
                if abs(np.real(poles[i]) - np.real(poles[j])) <= tol_pair:
                    target = round((np.real(poles[i]) + np.real(poles[j]))/2.0, round_decimals)
                    poles[i] = complex(target, 0.0)
                    poles[j] = complex(target, 0.0)
                    used.add(j)
                    break
        den_fixed = np.real_if_close(np.poly(poles)).astype(float)
        return poles, den_fixed

    def spread_equal_real_poles_for_plot(poles, shift=0.01, round_key_dec=6):
        poles = np.array(poles, dtype=complex)
        poles_plot = poles.copy()
        groups = {}
        for idx, p in enumerate(poles):
            if abs(p.imag) == 0.0:
                key = round(float(np.real(p)), round_key_dec)
                groups.setdefault(key, []).append(idx)
        for _, idxs in groups.items():
            if len(idxs) > 1:
                for k, idx in enumerate(idxs[1:], start=1):
                    r0 = float(np.real(poles_plot[idxs[0]]))
                    poles_plot[idx] = complex(r0 + k*shift, 0.0)
        return poles_plot

    if tipo == "malha_aberta":
        G_sel = G_planta
        titulo = "Diagrama de Polos e Zeros (Malha Aberta - Planta)"
    elif tipo == "erro":
        G_sel = ctl.feedback(ctl.tf([1.0], [1.0]), L)
        titulo = "Diagrama de Polos e Zeros do Erro (E/R)"
    elif tipo == "perturbacao":
        G_sel = ctl.feedback(G_planta, G_controlador)
        titulo = "Diagrama de Polos e Zeros da Perturbação (Y/Q)"
    else:
        G_sel = ctl.feedback(L)
        titulo = "Diagrama de Polos e Zeros (Malha Fechada Y/R)"

    num = np.array(G_sel.num).flatten()
    den = np.array(G_sel.den).flatten()
    zeros = np.roots(num) if num.size else np.array([])
    polos = np.roots(den) if den.size else np.array([])

    polos, den = snap_poles_for_display(polos)
    polos_plot = spread_equal_real_poles_for_plot(polos, shift=0.01)

    plot_pz_closed = {
        "data": [
            {"x": np.real(zeros).tolist(), "y": np.imag(zeros).tolist(), "mode": "markers", "name": "Zeros", "marker": {"color": "blue", "size": 12, "symbol": "circle"}},
            {"x": np.real(polos_plot).tolist(), "y": np.imag(polos_plot).tolist(), "mode": "markers", "name": "Polos", "marker": {"color": "red", "size": 14, "symbol": "x"}}
        ],
        "layout": {"title": titulo, "xaxis": {"title": "Re", "zeroline": True}, "yaxis": {"title": "Im", "zeroline": True, "scaleanchor": "x", "scaleratio": 1}, "showlegend": True}
    }

    return jsonify({
        "plot_pz_closed": plot_pz_closed,
        "den_cl": den.tolist(),
        "poles_cl": [{"re": float(np.real(p)), "im": float(np.imag(p))} for p in polos]
    })


# Feedback por e-mail
@app.route('/enviar_feedback', methods=['POST'])
def enviar_feedback():
    data = request.get_json()
    texto = data.get('feedback', '')
    remetente = 'syscoufsc@gmail.com'
    senha = 'jvey wybi xcnm znko'
    destinatario = 'syscoufsc@gmail.com'

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


# Nyquist imagens (página 2 e 4)
@app.route('/nyquist_pagina2', methods=['POST'])
def nyquist_pagina2():
    data = request.get_json()
    polos_planta = [float(p) for p in data.get("polos_planta", [-1])]
    zeros_planta = [float(z) for z in data.get("zeros_planta", [0])]

    zeros_planta_filtrados = [z for z in zeros_planta if abs(z) > 1e-8]
    num_planta = np.poly(zeros_planta_filtrados) if zeros_planta_filtrados else np.array([1.0])
    den_planta = np.poly(polos_planta)
    G_planta = ctl.tf(num_planta, den_planta)

    fig, ax = plt.subplots(figsize=(7, 4))
    ctl.nyquist_plot(G_planta, omega=np.logspace(-2, 2, 500), ax=ax, color='b')
    ax.set_title("Diagrama de Nyquist")
    ax.set_xlabel("Re")
    ax.set_ylabel("Im")
    ax.grid(True)
    plt.tight_layout()

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
    num_controlador = ganho_controlador * (np.poly(zeros_controlador_filtrados) if zeros_controlador_filtrados else np.array([1.0]))
    den_controlador = np.poly(polos_controlador_filtrados) if polos_controlador_filtrados else np.array([1.0])

    G_open = ctl.tf(np.polymul(num_planta, num_controlador), np.polymul(den_planta, den_controlador))

    fig, ax = plt.subplots(figsize=(7, 4))
    ctl.nyquist_plot(G_open, omega=np.logspace(-2, 2, 500), ax=ax, color='b')
    ax.set_title("Diagrama de Nyquist")
    ax.set_xlabel("Re")
    ax.set_ylabel("Im")
    ax.grid(True)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    return jsonify({"nyquist_img": img_base64})


# Outras utilidades
@app.route('/simular_saida', methods=['POST'])
def simular_saida():
    data = request.get_json()
    num = [float(x) for x in data.get("num", [1])]
    den = [float(x) for x in data.get("den", [1, 1])]
    t_final = float(data.get("t_final", 40))
    n_points = int(data.get("n_points", 200))
    try:
        system = scipy.signal.TransferFunction(num, den)
        t = np.linspace(0, t_final, n_points)
        t, y = scipy.signal.step(system, T=t)
        return jsonify({"t": t.tolist(), "y": y.tolist()})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# Discretização
@app.route('/atualizar_discreto', methods=['POST'])
def atualizar_discreto():
    data = request.get_json()
    ordem = int(data.get("ordem", 2))
    polos = [float(data.get(f"polo_{i+1}", -1)) for i in range(ordem)]
    zeros = [float(data.get(f"zero_{i+1}", 0)) for i in range(ordem)]
    Ts = float(data.get("Ts", 0.1))

    num = np.poly([z for z in zeros if abs(z) > 1e-8]) if any(abs(z) > 1e-8 for z in zeros) else np.array([1.0])
    den = np.poly([p for p in polos if abs(p) > 1e-8]) if any(abs(p) > 1e-8 for p in polos) else np.array([1.0])
    Gs = ctl.tf(num, den)

    Gz = ctl.sample_system(Gs, Ts, method='tustin')

    T_cont, y_cont = ctl.step_response(Gs, T=np.linspace(0, Ts*50, 500))
    T_disc = np.arange(0, Ts*50, Ts)
    tout, y_disc = ctl.step_response(Gz, T=T_disc)

    latex_Gs = f"\\[ G(s) = \\frac{{{latex_poly(num, 's')}}}{{{latex_poly(den, 's')}}} \\]"
    return jsonify({
        "latex_Gs": latex_Gs,
        "plot_continuo": {"x": T_cont.tolist(), "y": y_cont.tolist()},
        "plot_discreto": {"x": tout.tolist(), "y": y_disc.tolist()}
    })


# PID
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

    if ctrl_type == "P":
        latex_ctrl = r"\[ G_c(s) = %.2f \]" % K
    elif ctrl_type == "I":
        latex_ctrl = r"\[ G_c(s) = \frac{%.2f}{%.2f\,s} \]" % (K, Ti)
    elif ctrl_type == "PI":
        latex_ctrl = r"\[ G_c(s) = %.2f \left(1 + \frac{1}{%.2f\,s}\right) \]" % (K, Ti)
    elif ctrl_type == "PD":
        latex_ctrl = r"\[ G_c(s) = %.2f \left(1 + %.2f\,s \frac{%.2f}{s+%.2f}\right) \]" % (K, Td, N, N)
    else:
        latex_ctrl = r"\[ G_c(s) = %.2f \left(1 + \frac{1}{%.2f\,s} + \frac{%.2f\,s\,%.2f}{s+%.2f}\right) \]" % (K, Ti, Td, N, N)

    return jsonify({"latex_plant": latex_plant, "latex_ctrl": latex_ctrl})

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
    else:
        numc = [K*Td*N, K*N, K]
        denc = [Ti, Ti*N, 0]
        Gc = ctl.tf(numc, denc)

    sys_cl = ctl.feedback(Gc*G, 1)
    T = np.linspace(0, 40, 400)
    T, y = ctl.step_response(sys_cl, T)
    _, u = ctl.forced_response(Gc, T, 1 - y)

    plot_processo = {"data": [{"x": T.tolist(), "y": y.tolist(), "type": "scatter", "name": "Saída do Processo"}],
                     "layout": {"title": "Saída do Processo", "xaxis": {"title": "Tempo (s)"}, "yaxis": {"title": "y(t)"}}}
    plot_controlador = {"data": [{"x": T.tolist(), "y": u.tolist(), "type": "scatter", "name": "Saída do Controlador"}],
                        "layout": {"title": "Saída do Controlador", "xaxis": {"title": "Tempo (s)"}, "yaxis": {"title": "u(t)"}}}
    return jsonify({"plot_processo": plot_processo, "plot_controlador": plot_controlador})


# Estados (matrizes M, C, K)
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

    return {"equation": eq_latex, "A_latex": A_latex}


# Alocação de polos — inclui Filtro
@app.route('/alocacao_polos_backend', methods=['POST'])
def alocacao_polos_backend():
    data = request.get_json()

    polos_planta = [float(p) for p in data.get("polos_planta", [-0.0758])]
    zeros_planta = [float(z) for z in data.get("zeros_planta", [])]
    ganho_planta = float(data.get("ganho_planta", 1.0))
    polos_controlador = [float(p) for p in data.get("polos_controlador", [])]
    zeros_controlador = [float(z) for z in data.get("zeros_controlador", [])]
    ganho_controlador = float(data.get("ganho_controlador", 1.0))
    ts_multiplier = float(data.get("ts_multiplier", 0.5))

    filtro_ativo = bool(data.get("filtro_ativo", False))
    polos_filtro = [float(p) for p in data.get("polos_filtro", [])]
    ganho_filtro = float(data.get("ganho_filtro", 1.0))

    desired_order = int(data.get("desired_order", 2))
    desired_poles_type = data.get("desired_poles_type", "2nd_equal")

    num_planta = ganho_planta * (np.poly(zeros_planta) if zeros_planta else np.array([1.0]))
    den_planta = np.poly(polos_planta) if polos_planta else np.array([1.0])
    num_controlador = ganho_controlador * (np.poly(zeros_controlador) if zeros_controlador else np.array([1.0]))
    den_controlador = np.poly(polos_controlador) if polos_controlador else np.array([1.0])

    G_planta = ctl.tf(num_planta, den_planta)
    G_controlador = ctl.tf(num_controlador, den_controlador)
    L = G_controlador * G_planta
    G_closed = ctl.feedback(L)

    Dp, Dc = den_planta, den_controlador
    Np, Nc = num_planta, num_controlador
    poly_char_coeffs = np.polyadd(np.polymul(Dp, Dc), np.polymul(Np, Nc))

    T = np.linspace(0, 50, 1000)
    _, yout_open_planta = ctl.step_response(G_planta, T)
    _, yout_closed = ctl.step_response(G_closed, T)

    S = ctl.feedback(ctl.tf([1.0], [1.0]), L)
    Tq = ctl.feedback(G_planta, G_controlador)
    _, e_step = ctl.step_response(S, T)
    _, yq_step = ctl.step_response(Tq, T)

    def ts5_open_from_poles(poles):
        poles = np.array(poles, dtype=complex)
        if poles.size == 0 or np.any(np.real(poles) >= -1e-12):
            return None
        slow_re = float(np.max(np.real(poles)))
        alpha = -slow_re
        tol_re = max(1e-3, 1e-2*alpha)
        group = np.array([p for p in poles if abs(np.real(p) - slow_re) <= tol_re], dtype=complex)
        complex_dom = [p for p in group if abs(np.imag(p)) > 1e-8]
        if len(complex_dom) >= 1:
            p = complex_dom[0]; wn = abs(p)
            if wn <= 0: return None
            zeta = -np.real(p)/wn
            if zeta <= 0: return None
            return 3.0/(zeta*wn)
        m = len(group)
        coeff = 6.3 if m >= 3 else (4.8 if m == 2 else 3.0)
        return coeff/alpha

    def settling_time_5(t, y, pct=0.05):
        if len(t) == 0 or len(y) == 0: return 0.0
        y_final = float(y[-1])
        tol = pct * (abs(y_final) if abs(y_final) > 1e-8 else max(1.0, float(np.max(np.abs(y)))))
        idx = np.where(np.abs(y - y_final) > tol)[0]
        return float(t[idx[-1] + 1]) if len(idx) > 0 and (idx[-1] + 1) < len(t) else float(t[-1])

    polos_pl = ctl.poles(G_planta)
    ts_aberta_formula = ts5_open_from_poles(polos_pl)
    ts_aberta = float(ts_aberta_formula) if ts_aberta_formula is not None else settling_time_5(T, yout_open_planta)
    ts_fechada = settling_time_5(T, yout_closed)

    try:
        poly_caracteristico = f"\\( {latex_poly(poly_char_coeffs, 's')} \\)"
    except Exception:
        poly_caracteristico = ""

    ts_desejado = float(ts_aberta) * float(ts_multiplier)
    poly_desejado = ""
    pd_value_latex = ""
    if ts_desejado > 1e-12 and np.isfinite(ts_desejado):
        if desired_order == 1:
            Pd = 3.0 / ts_desejado
            coeffs = np.poly([-Pd])
            poly_desejado = f"\\( {latex_poly(coeffs, 's')} \\)"
            pd_value_latex = f"\\( P_d = {Pd:.4g} \\)"
        elif desired_order == 2:
            if desired_poles_type == "2nd_distinct":
                c = 1.5
                a = (3.0 + 1.5/c) / ts_desejado
                b = c * a
                coeffs = np.array([1.0, a + b, a * b])
                poly_desejado = f"\\( {latex_poly(coeffs, 's')} \\)"
                pd_value_latex = f"\\( p_{{lento}} = {a:.3g},\\ p_{{ráp}} = {b:.3g}\\;\\)"
            else:
                Pd = 4.8 / ts_desejado
                coeffs = np.array([1.0, 2.0*Pd, Pd**2])
                poly_desejado = f"\\( {latex_poly(coeffs, 's')} \\)"
                pd_value_latex = f"\\( P_d = {Pd:.4g} \\)"
        else:
            Pd = 6.3 / ts_desejado
            coeffs = np.poly([-Pd, -Pd, -Pd])
            poly_desejado = f"\\( {latex_poly(coeffs, 's')} \\)"
            pd_value_latex = f"\\( P_d = {Pd:.4g} \\)"

    # Filtro F(s) aplicado à saída em malha fechada
    if filtro_ativo and polos_filtro:
        num_filtro = [ganho_filtro]
        den_filtro = np.poly(polos_filtro)
        F = ctl.tf(num_filtro, den_filtro)
    else:
        F = ctl.tf([1.0], [1.0])

    Y_filt = F * G_closed
    _, yout_filt = ctl.step_response(Y_filt, T)

    plot_closed_filt = {
        "data": [{"x": T.tolist(), "y": yout_filt.tolist(), "mode": "lines", "name": "Y/R filtrado", "line": { "width": 3}}],
        "layout": {"title": "Resposta ao Degrau (Malha Fechada + Filtro)", "xaxis": {"title": "Tempo (s)", "range": [0, 10]}, "yaxis": {"title": "Amplitude"}}
    }
    plot_closed = {
        "data": [{"x": T.tolist(), "y": yout_closed.tolist(), "mode": "lines", "name": "Y/R = L/(1+L)", "line": { "width": 3}}],
        "layout": {"title": "Resposta ao Degrau (Malha Fechada)", "xaxis": {"title": "Tempo (s)", "range": [0, 10]}, "yaxis": {"title": "Amplitude"}}
    }
    plot_open = {
        "data": [{"x": T.tolist(), "y": yout_open_planta.tolist(), "mode": "lines", "name": "Planta (Malha Aberta)", "line": { "width": 3}}],
        "layout": {"title": "Resposta ao Degrau (Malha Aberta - Planta)", "xaxis": {"title": "Tempo (s)", "range": [0, 10]}, "yaxis": {"title": "Amplitude"}}
    }
    plot_er = {
        "data": [{"x": T.tolist(), "y": e_step.tolist(), "mode": "lines", "name": "E/R = 1/(1+CG)", "line": { "width": 3}}],
        "layout": {"title": "Erro frente a degrau (E/R = 1/(1+CG))", "xaxis": {"title": "Tempo (s)", "range": [0, 10]}, "yaxis": {"title": "e(t)"}}
    }
    plot_yq = {
        "data": [{"x": T.tolist(), "y": yq_step.tolist(), "mode": "lines", "name": "Y/Q = G/(1+CG)"}],
        "layout": {"title": "Saída frente a degrau de perturbação (Y/Q = G/(1+CG))", "xaxis": {"title": "Tempo (s)", "range": [0, 10]}, "yaxis": {"title": "y(t)"}}
    }

    try:
        if filtro_ativo and polos_filtro:
            # DPz do sistema filtrado: F(s) * G_closed
            num_filt = np.polymul(np.array(F.num).flatten(), np.array(G_closed.num).flatten())
            den_filt = np.polymul(np.array(F.den).flatten(), np.array(G_closed.den).flatten())
            zeros_closed = np.roots(num_filt) if num_filt.size else np.array([])
            poles_closed = np.roots(den_filt) if den_filt.size else np.array([])
        else:
            num_closed = np.array(G_closed.num).flatten()
            den_closed = np.array(G_closed.den).flatten()
            zeros_closed = np.roots(num_closed) if num_closed.size else np.array([])
            poles_closed = np.roots(den_closed) if den_closed.size else np.array([])
    except Exception:
        zeros_closed, poles_closed = np.array([]), np.array([])

    plot_pz_closed = {
        "data": [
            {"x": np.real(zeros_closed).tolist(), "y": np.imag(zeros_closed).tolist(), "mode": "markers", "name": "Zeros", "marker": {"color": "blue", "size": 12, "symbol": "circle"}},
            {"x": np.real(poles_closed).tolist(), "y": np.imag(poles_closed).tolist(), "mode": "markers", "name": "Polos", "marker": {"color": "red", "size": 14, "symbol": "x"}}
        ],
        "layout": {"title": "Diagrama de Polos e Zeros (Malha Fechada)", "xaxis": {"title": "Re", "zeroline": True}, "yaxis": {"title": "Im", "zeroline": True, "scaleanchor": "x", "scaleratio": 1}, "showlegend": True}
    }

    try:
        zeros_open = np.roots(num_planta)
        poles_open = np.roots(den_planta)
    except Exception:
        zeros_open, poles_open = np.array([]), np.array([])

    plot_pz_open = {
        "data": [
            {"x": np.real(zeros_open).tolist(), "y": np.imag(zeros_open).tolist(), "mode": "markers", "name": "Zeros", "marker": {"color": "blue", "size": 12, "symbol": "circle"}},
            {"x": np.real(poles_open).tolist(), "y": np.imag(poles_open).tolist(), "mode": "markers", "name": "Polos", "marker": {"color": "red", "size": 14, "symbol": "x"}}
        ],
        "layout": {"title": "Diagrama de Polos e Zeros (Malha Aberta - Planta)", "xaxis": {"title": "Re", "zeroline": True}, "yaxis": {"title": "Im", "zeroline": True, "scaleanchor": "x", "scaleratio": 1}, "showlegend": True}
    }

    latex_planta = f"\\( G(s) = {ganho_planta:.3g} \\cdot \\frac{{{latex_factored(zeros_planta, 's')}}}{{{latex_factored(polos_planta, 's')}}} \\)"
    latex_controlador = f"\\( G_c(s) = {ganho_controlador:.3g} \\cdot \\frac{{{latex_factored(zeros_controlador, 's')}}}{{{latex_factored(polos_controlador, 's')}}} \\)"

    return jsonify({
        "tempo_assentamento_aberta": round(float(ts_aberta), 3),
        "tempo_assentamento_fechada": round(float(ts_fechada), 3),
        "ts_desejado": round(float(ts_desejado), 3),
        "pd_value": pd_value_latex,
        "poly_caracteristico": poly_caracteristico,
        "poly_desejado": poly_desejado,
        "latex_planta": latex_planta,
        "latex_controlador": latex_controlador,
        "plot_pz_closed": plot_pz_closed,
        "plot_pz_open": plot_pz_open,
        "plot_closed": plot_closed,
        "plot_open": plot_open,
        "plot_er": plot_er,
        "plot_yq": plot_yq,
        "plot_closed_filt": plot_closed_filt
    })


# Página 2 — Malha aberta
@app.route('/atualizar_pagina2', methods=['POST'])
def atualizar_pagina2():
    data = request.get_json()
    polos_planta = [float(p) for p in data.get("polos_planta", [-1])]
    zeros_planta = [float(z) for z in data.get("zeros_planta", [0])]

    zeros_planta_filtrados = [z for z in zeros_planta if abs(z) > 1e-8]
    num_planta = np.poly(zeros_planta_filtrados) if zeros_planta_filtrados else np.array([1.0])
    den_planta = np.poly(polos_planta) if polos_planta else np.array([1.0])

    G_planta = ctl.tf(num_planta, den_planta)

    latex_planta_polinomial = f"\\[ G(s) = \\frac{{{latex_poly(num_planta, 's')}}}{{{latex_poly(den_planta, 's')}}} \\]"
    latex_planta_fatorada   = f"\\[ G(s) = \\frac{{{latex_factored(zeros_planta, 's')}}}{{{latex_factored(polos_planta, 's')}}} \\]"
    latex_planta_parcial    = f"\\[ G(s) = {latex_partial_fraction(num_planta, den_planta, 's')[3:-3]} \\]"

    zeros = np.roots(num_planta)
    polos = np.roots(den_planta)
    plot_pz_data = {
        "data": [
            {"x": np.real(zeros).tolist(), "y": np.imag(zeros).tolist(), "mode": "markers", "name": "Zeros", "marker": {"color": "blue", "size": 12, "symbol": "circle"}},
            {"x": np.real(polos).tolist(), "y": np.imag(polos).tolist(), "mode": "markers", "name": "Polos", "marker": {"color": "red", "size": 14, "symbol": "x"}}
        ],
        "layout": {"title": "Diagrama de Polos e Zeros", "xaxis": {"title": "Re", "zeroline": True}, "yaxis": {"title": "Im", "zeroline": True, "scaleanchor": "x", "scaleratio": 1}, "showlegend": True}
    }

    T = np.linspace(0, 20, 500)
    _, yout = ctl.step_response(G_planta, T)
    plot_open_data = {
        "data": [{"x": T.tolist(), "y": yout.tolist(), "mode": "lines", "name": "Resposta ao Degrau (Malha Aberta)"}],
        "layout": {"title": "Resposta ao Degrau (Malha Aberta)", "xaxis": {"title": "Tempo (s)"}, "yaxis": {"title": "Amplitude"}}
    }

    return jsonify({
        "latex_planta_polinomial": latex_planta_polinomial,
        "latex_planta_fatorada":   latex_planta_fatorada,
        "latex_planta_parcial":    latex_planta_parcial,
        "plot_pz_data": plot_pz_data,
        "plot_open_data": plot_open_data
    })


# Sinais (FT genérica) + Bode opcional
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

    bode_data = None
    if data.get("bode", False):
        try:
            omega = np.logspace(-2, 2, 500)
            mag, phase, omega = ctl.bode(G, omega=omega, dB=True, plot=False)
            bode_data = {
                "data": [
                    {"x": omega.tolist(), "y": (20*np.log10(mag)).tolist(), "type": "scatter", "mode": "lines", "name": "Magnitude"},
                    {"x": omega.tolist(), "y": np.degrees(phase).tolist(),   "type": "scatter", "mode": "lines", "name": "Fase", "yaxis": "y2"}
                ],
                "layout": {
                    "title": "Diagrama de Bode",
                    "xaxis": {"title": "Frequência (rad/s)", "type": "log"},
                    "yaxis": {"title": "Magnitude (dB)"},
                    "yaxis2": {"title": "Fase (graus)", "overlaying": "y", "side": "right"},
                    "legend": {"x": 0, "y": 1.1, "orientation": "h"}
                }
            }
        except Exception:
            bode_data = None

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
        "step_response": {"T": T.tolist(), "y": yout.tolist()},
        "bode_data": bode_data
    })


# EDO -> FT e resposta
@app.route('/sinais_edo', methods=['POST'])
def sinais_edo():
    import sympy as sp
    from scipy.signal import lti, step
    data = request.get_json()
    eq_str = data.get("edo", "")
    t = np.linspace(0, 20, 500)
    try:
        y = sp.Function('y')
        u = sp.Function('u')
        t_sym = sp.symbols('t')
        eq = sp.sympify(eq_str.replace("=", "-(") + ")", locals={'y': y(t_sym), "u": u(t_sym)})
        eq = sp.Eq(eq, 0)
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


# Página 4 — Malha fechada com Filtro (rota separada)
@app.route('/novo_grafico_fechado', methods=['POST'])
def novo_grafico_fechado():
    data = request.get_json()
    polos_planta = [float(p) for p in data.get("polos_planta", [-1])]
    zeros_planta = [float(z) for z in data.get("zeros_planta", [0])]
    polos_controlador = [float(p) for p in data.get("polos_controlador", [-1])]
    zeros_controlador = [float(z) for z in data.get("zeros_controlador", [0])]
    ganho_controlador = float(data.get("ganho_controlador", 1.0))
    ganho_planta = float(data.get("ganho_planta", 1.0))

    num_planta = ganho_planta * (np.poly(zeros_planta) if zeros_planta else np.array([1.0]))
    den_planta = np.poly(polos_planta) if polos_planta else np.array([1.0])
    num_controlador = ganho_controlador * (np.poly(zeros_controlador) if zeros_controlador else np.array([1.0]))
    den_controlador = np.poly(polos_controlador) if polos_controlador else np.array([1.0])

    G_planta = ctl.tf(num_planta, den_planta)
    G_controlador = ctl.tf(num_controlador, den_controlador)
    G_closed = ctl.feedback(G_planta * G_controlador)

    T = np.linspace(0, 50, 1000)
    _, yout_closed = ctl.step_response(G_closed, T)

    t_perturb_fechada = float(data.get("t_perturb_fechada", 20))
    amp_perturb_fechada = float(data.get("amp_perturb_fechada", 0.5))
    u_ref = np.ones_like(T)
    u_ref[T >= t_perturb_fechada] += amp_perturb_fechada
    _, yout_closed_ref2 = ctl.forced_response(G_closed, T, u_ref)

    _, yout_open = ctl.forced_response(G_planta, T, np.ones_like(T))

    plot_closed_data = {
        "data": [
            {"x": T.tolist(), "y": yout_closed.tolist(), "mode": "lines", "name": "Sem Perturbação", "line": {"color": "#077FFF", "width": 3}},
            {"x": T.tolist(), "y": yout_closed_ref2.tolist(), "mode": "lines", "name": "Com Perturbação", "line": {"color": "#ff9800", "dash": "dash", "width": 2}},
            {"x": T.tolist(), "y": yout_open.tolist(), "mode": "lines", "name": "Malha Aberta", "line": {"color": "#06B900", "dash": "dash", "width": 3}}
        ],
        "layout": {"title": "Resposta ao Degrau", "xaxis": {"title": "Tempo (s)", "range": [0, 10]}, "yaxis": {"title": "Amplitude"}}
    }

    L = G_planta * G_controlador
    S = ctl.feedback(ctl.tf([1.0], [1.0]), L)
    Tq = ctl.feedback(G_planta, G_controlador)
    _, e_step = ctl.step_response(S, T)
    _, yq_step = ctl.step_response(Tq, T)

    error_closed_data = {"data": [{"x": T.tolist(), "y": e_step.tolist(), "mode": "lines", "name": "E/R", "line": {"color": "#000000", "dash": "solid", "width": 2}}]}
    perturb_closed_data = {"data": [{"x": T.tolist(), "y": yq_step.tolist(), "mode": "lines", "name": "Y/Q", "line": {"dash": "dash", "color": "#9c27b0"}}]}

    latex_planta_polinomial = f"\\[ G(s) = \\frac{{{latex_poly(num_planta, 's')}}}{{{latex_poly(den_planta, 's')}}} \\]"
    latex_planta_fatorada   = f"\\[ G(s) = \\frac{{{latex_factored(zeros_planta, 's')}}}{{{latex_factored(polos_planta, 's')}}} \\]"
    latex_planta_parcial    = latex_partial_fraction(num_planta, den_planta, 's')
    latex_controlador_polinomial = f"\\[ G_c(s) = {ganho_controlador:.3g} \\cdot \\frac{{{latex_poly(np.poly(zeros_controlador) if zeros_controlador else [1.0], 's')}}}{{{latex_poly(den_controlador, 's')}}} \\]"
    latex_controlador_fatorada   = f"\\[ G_c(s) = {ganho_controlador:.3g} \\cdot \\frac{{{latex_factored(zeros_controlador, 's')}}}{{{latex_factored(polos_controlador, 's')}}} \\]"
    latex_controlador_parcial    = f"\\[ G_c(s) = {ganho_controlador:.3g} \\cdot {latex_partial_fraction(np.poly(zeros_controlador) if zeros_controlador else [1.0], den_controlador, 's')[3:-3]} \\]"

    # Filtro (aplicado sobre a saída de malha fechada)
    polos_filtro = [float(p) for p in data.get("polos_filtro", [])]
    ganho_filtro = float(data.get("ganho_filtro", 1.0))
    filtro_ativo = bool(data.get("filtro_ativo", False))

    if filtro_ativo and polos_filtro:
        num_filtro = [ganho_filtro]
        den_filtro = np.poly(polos_filtro)
        F = ctl.tf(num_filtro, den_filtro)
    else:
        F = ctl.tf([1.0], [1.0])

    Y_filt = F * G_closed
    _, yout_filt = ctl.step_response(Y_filt, T)
    plot_closed_filt = {
        "data": [{"x": T.tolist(), "y": yout_filt.tolist(), "mode": "lines", "name": "Y/R filtrado"}],
        "layout": {"title": "Resposta ao Degrau (Malha Fechada + Filtro)", "xaxis": {"title": "Tempo (s)", "range": [0, 10]}, "yaxis": {"title": "Amplitude"}}
    }

    return jsonify({
        "latex_planta": latex_planta_polinomial,
        "latex_planta_fatorada": latex_planta_fatorada,
        "latex_planta_parcial": latex_planta_parcial,
        "latex_controlador_polinomial": latex_controlador_polinomial,
        "latex_controlador_fatorada": latex_controlador_fatorada,
        "latex_controlador_parcial": latex_controlador_parcial,
        "plot_closed_data": plot_closed_data,
        "error_closed_data": error_closed_data,
        "perturb_closed_data": perturb_closed_data,
        "plot_closed_filt": plot_closed_filt
    })


if __name__ == '__main__':
    app.run(debug=True)
