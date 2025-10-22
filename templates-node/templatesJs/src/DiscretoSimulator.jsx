import React, { useEffect, useState } from "react";
import Plot from "react-plotly.js";
import { MathJax, MathJaxContext } from "better-react-mathjax";
import HamburgerMenu from "./menu"; 

// Configuração do MathJax para renderização de LaTeX.
// - loader: define entradas/saídas do MathJax
// - tex.inlineMath: padrões de delimitadores para inline math
const mathJaxConfig = {
  loader: { load: ["input/tex", "output/chtml"] },
  tex: { inlineMath: [["$", "$"], ["\\(", "\\)"]] }
};

export default function DiscretoSimulator() {
  // Estados principais do simulador:
  const [Ts, setTs] = useState(0.1);
  const [polos, setPolos] = useState([-1]);
  const [zeros, setZeros] = useState([0]);

  // Estados para LaTeX das funções de transferência e dados dos gráficos
  const [latexGs, setLatexGs] = useState("G(s) = \\frac{1}{s+1}");
  const [latexGz, setLatexGz] = useState("G(z) = \\frac{1-z^{-1}}{z-0.5}");
  const [plotCont, setPlotCont] = useState({ x: [0, 0.1, 0.2, 0.3, 0.4, 0.5], y: [0, 0.095, 0.181, 0.259, 0.329, 0.393] });
  const [plotDisc, setPlotDisc] = useState({ x: [0, 0.1, 0.2, 0.3, 0.4, 0.5], y: [0, 0.09, 0.17, 0.24, 0.30, 0.35] });

  // Mensagens de erro/aviso e horizonte de visualização dos plots
  const [erro, setErro] = useState("");
  const [horizonte, setHorizonte] = useState(5); // Define o range [0, horizonte] no eixo X

  // Efeito responsável por:
  // - Validar a FT (impede mais zeros que polos)
  // - Sincronizar com o backend quando Ts/polos/zeros mudarem
  // - Aplicar um "debounce" curto e cancelar requisições antigas
  useEffect(() => {
    // Regra: FT imprópria (mais zeros que polos) -> bloqueia atualização
    if (zeros.length > polos.length) {
      setErro("A FT é imprópria (há mais zeros do que polos). Remova zeros ou adicione polos.");
      return;
    }

    // Cria um AbortController para poder cancelar a requisição se os estados mudarem rapidamente
    const ctrl = new AbortController();

    // Debounce mínimo para agrupar mudanças rápidas
    const t = setTimeout(() => atualizarDiscreto(ctrl.signal), 10);

    // Cleanup: cancela a chamada e o timeout se o efeito rodar novamente/desmontar
    return () => {
      ctrl.abort();
      clearTimeout(t);
    };
  }, [Ts, polos, zeros]);

  /**
   * Chama o backend para recalcular o sistema discretizado e a resposta.
   * - Envia Ts, polos e zeros via POST.
   * - Trata avisos (mantém os gráficos anteriores, mas atualiza LaTeX).
   * - Atualiza LaTeX, dados dos gráficos e horizonte quando sucesso.
   * - Faz fallback local em caso de erro de rede (mantém exemplo simples).
   */
  async function atualizarDiscreto(signal) {
    const data = { Ts, polos, zeros };

    try {
      const res = await fetch("http://localhost:5000/atualizar_discreto", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
        signal, // permite cancelamento via AbortController
      });

      const json = await res.json();
      if (!res.ok) throw new Error(json?.message || "Falha no backend");

      // Caso o backend retorne um aviso, exibimos e evitamos sobrescrever os gráficos
      if (json.warning) {
        setErro(json.warning);
        // Ainda assim, atualiza os LaTeX para refletir os fatores inseridos
        if (json.latex_Gs) setLatexGs(json.latex_Gs);
        if (json.latex_Gz) setLatexGz(json.latex_Gz);
        return;
      }

      // Atualizações "felizes" com fallbacks seguros
      setLatexGs(json.latex_Gs || "G(s) = \\frac{1}{s+1}");
      setLatexGz(json.latex_Gz || "G(z) = \\frac{1-z^{-1}}{z-0.5}");
      if (json.plot_continuo) setPlotCont(json.plot_continuo);
      if (json.plot_discreto) setPlotDisc(json.plot_discreto);
      if (json.horizonte) setHorizonte(json.horizonte);
      setErro("");
    } catch (e) {
      // Se a chamada foi abortada, apenas ignora (é um fluxo normal do efeito)
      if (e.name === "AbortError") return;

      // Fallback quando não há backend acessível
      setErro("Erro ao conectar com o backend. Usando dados simulados.");
      setLatexGs("G(s) = \\frac{1}{s+1}");
      setLatexGz("G(z) = \\frac{1-z^{-1}}{z-0.5}");
    }
  }

  /**
   * Converte números em string com vírgula decimal para Number do JS.
   * Aceita:
   *  - number (retorna direto)
   *  - string "0,1" -> 0.1  |  "0.1" -> 0.1
   */
  const parseLocaleNumber = (val) => {
    if (typeof val === "number") return val;
    if (typeof val === "string") return parseFloat(val.replace(",", "."));
    return NaN;
  };

  /** Atualiza o período de amostragem (Ts) apenas se o valor for válido */
  function handleTsChange(value) {
    const v = parseLocaleNumber(value);
    if (Number.isFinite(v)) setTs(v);
  }

  /** Atualiza um polo (índice idx) preservando os demais */
  function handlePoloChange(idx, value) {
    const v = parseLocaleNumber(value);
    const arr = [...polos];
    arr[idx] = Number.isFinite(v) ? v : 0;
    setPolos(arr);
  }

  /** Atualiza um zero (índice idx) preservando os demais */
  function handleZeroChange(idx, value) {
    const v = parseLocaleNumber(value);
    const arr = [...zeros];
    arr[idx] = Number.isFinite(v) ? v : 0;
    setZeros(arr);
  }

  /** Adiciona/Remove polos e zeros (operações imutáveis nos arrays de estado) */
  function addPolo() { setPolos(p => [...p, -1]); }
  function removePolo(i) { setPolos(p => p.filter((_, idx) => idx !== i)); }
  function addZero() { setZeros(z => [...z, 0]); }
  function removeZero(i) { setZeros(z => z.filter((_, idx) => idx !== i)); }

  // Estilos reutilizados nos inputs
  const sliderStyle = { width: "150px", marginRight: "8px" };
  const inputStyle = { width: "50px", marginLeft: "8px" };

  // Itens do menu (o componente ocultará o link da página atual)
  const menuItems = [
    { label: "Contínuo", href: "/continuo" },
    { label: "Discreto", href: "/discreto" },
    { label: "Alocação de Polos", href: "/alocacao" },
    { label: "Sobre", href: "/sobre" }
  ];

  return (
    // Contexto do MathJax (necessário para renderizar fórmulas LaTeX)
    <MathJaxContext version={3} config={mathJaxConfig}>
      {/* Barra superior com título e botão hamburger */}
      <div
        className="top-bar"
        style={{
          display: "flex",
          alignItems: "center",
          border: "2px solid #ffffff",
          justifyContent: "center",
          position: "relative",
          width: "100%",
          background: "#fff",
          boxShadow: "0 2px 8px #0001",
          padding: "8px 0 4px 0",
          minHeight: "38px",
          zIndex: 100
        }}
      >
        {/* Usa o componente HamburgerMenu no topo (lado esquerdo) */}
         <HamburgerMenu items={menuItems} currentHref="/discreto" /> 

        {/* Título centralizado da página */}
        <div
          className="page-title"
          style={{
            flex: 1,
            textAlign: "center",
            fontSize: "1.3em",
            fontWeight: "bold",
            color: "#1976d2",
            display: "flex",  
            alignItems: "center",
            justifyContent: "center",
            gap: "12px"
          }}
        >
          Simulador de Resposta Discreta
        </div>
      </div>

      {/* Espaçador entre a barra de título e o conteúdo principal */}
      <div style={{ height: "10px" }} />

      {/* Container do conteúdo principal */}
      <div className="container" style={{
        maxWidth: "1100px", margin: "32px auto", marginTop:"5px",
        background: "#fff", borderRadius: "10px",
        boxShadow: "0 2px 12px #0001", padding: "32px 24px 24px 24px"
      }}>
        {/* Exibição de erros/avisos do backend/validação */}
        {erro && <div style={{ color: "red", marginBottom: "12px" }}>{erro}</div>}

        {/* Seção de parâmetros: edição de polos/zeros e Ts */}
        <div className="param-section" style={{ display: "flex", gap: "32px", flexWrap: "wrap", marginBottom: "24px" }}>
          {/* Coluna de controles numéricos */}
          <div className="param-block" style={{ minWidth: "280px", flex: 1 }}>
            <b>Polos (contínuos):</b>
            <div style={{ marginTop: "10px" }}>
              {polos.map((p, i) => (
                <div key={`p-${i}`} style={{ marginBottom: "8px", display: "flex", alignItems: "center" }}>
                  <span style={{ width: 54 }}>Polo {i + 1}:</span>
                  {/* Slider e input numérico sincronizados para cada polo */}
                  <input type="range" min={-10} max={1} step={0.01} value={p} style={sliderStyle}
                         onChange={e => handlePoloChange(i, e.target.value)} />
                  <input type="number" step="0.01" min={-10} max={1} value={p} style={inputStyle}
                         onChange={e => handlePoloChange(i, e.target.value)} />
                  <button style={{ marginLeft: 8 }} onClick={() => removePolo(i)}>Remover</button>
                </div>
              ))}
              <button onClick={addPolo}>Adicionar Polo</button>
            </div>

            <div style={{ marginTop: "16px" }}>
              <b>Zeros (contínuos):</b>
              <div style={{ marginTop: "10px" }}>
                {zeros.map((z, i) => (
                  <div key={`z-${i}`} style={{ marginBottom: "8px", display: "flex", alignItems: "center" }}>
                    <span style={{ width: 54 }}>Zero {i + 1}:</span>
                    {/* Slider e input numérico sincronizados para cada zero */}
                    <input type="range" min={-10} max={10} step={0.01} value={z} style={sliderStyle}
                           onChange={e => handleZeroChange(i, e.target.value)} />
                    <input type="number" step="0.01" min={-10} max={10} value={z} style={inputStyle}
                           onChange={e => handleZeroChange(i, e.target.value)} />
                    <button style={{ marginLeft: 8 }} onClick={() => removeZero(i)}>Remover</button>
                  </div>
                ))}
                <button onClick={addZero}>Adicionar Zero</button>
              </div>
            </div>

            {/* Controle do período de amostragem Ts */}
            <div style={{ marginTop: "16px" }}>
              <label htmlFor="Ts" style={{ marginRight: 8 }}>Período de Amostragem (Ts):</label>
              {/* Slider de Ts */}
              <input
                type="range"
                min={0.001}
                max={5.000}
                step={0.001}
                value={Ts}
                style={{ width: 160, marginRight: 8 }}
                onChange={e => handleTsChange(e.target.value)}
                onInput={e => handleTsChange(e.target.value)}
              />
              {/* Input numérico de Ts com sufixo "s" */}
              <span style={{ position: "relative", display: "inline-block", marginLeft: 8 }}>
                <input
                  id="Ts"
                  type="number"
                  min="0.001"
                  max="10"
                  step="0.01"
                  value={Ts}
                  style={{ width: "50px" }}
                  onChange={e => handleTsChange(e.target.value)}
                />
                {/* Sufixo visual "s" (segundos) */}
                <span
                  style={{
                    position: "absolute",
                    right: 6,
                    top: "50%",
                    transform: "translateY(-50%)",
                    color: "#666",
                    pointerEvents: "none"
                  }}
                >
                  s
                </span>
              </span>
            </div>
          </div>
                          
          {/* Coluna com as FTs em LaTeX (centradas) */}
          <div className="param-block" style={{ minWidth: "280px", flex: 1 }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
              <div style={{ display: "flex", justifyContent: "center", fontWeight: "bold", marginBottom: 6 }}>
                Função de Transferência no Domínio Contínuo:
              </div>
              {/* Container centralizado da FT contínua */}
              <div
                className="latex-container"
                style={{
                  background: "#ffffffff",
                  borderRadius: "6px",
                  padding: "12px 16px",
                  marginBottom: "16px",
                  fontSize: "1.2em",
                  wordBreak: "break-word",
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center"
                }}
              >
                <MathJax dynamic>{`\\(${latexGs}\\)`}</MathJax>
              </div>

              <div style={{ display: "flex", justifyContent: "center", fontWeight: "bold", marginBottom: 6 }}>
                Função de Transferência no Domínio Discreto:
              </div>
              {/* Container centralizado da FT discreta */}
              <div
                className="latex-container"
                style={{
                  background: "#ffffffff",
                  borderRadius: "6px",
                  padding: "12px 16px",
                  marginBottom: "12px",
                  fontSize: "1.2em",
                  wordBreak: "break-word",
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center"
                }}
              >
                <MathJax dynamic>{`\\(${latexGz}\\)`}</MathJax>
              </div>
            </div>
          </div>
        </div>

        {/* Área dos gráficos de resposta ao degrau */}
        <div style={{ display: "flex", gap: "32px", flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: "320px" }}>
            <h4>Resposta ao Degrau (Contínua)</h4>
            <Plot
              data={[{ x: plotCont.x, y: plotCont.y, mode: "lines", name: "Contínua" }]}
              layout={{ xaxis: { title: "Tempo (s)", range: [0, horizonte] }, yaxis: { title: "Saída" }, margin: { t: 20 } }}
              config={{ displayModeBar: false }}
              style={{ width: "100%", height: "300px" }}
            />
          </div>
          <div style={{ flex: 1, minWidth: "320px" }}>
            <h4>Resposta ao Degrau (Discreta)</h4>
            <Plot
              data={[{
                x: plotDisc.x, y: plotDisc.y, mode: "markers+lines",
                marker: { size: 7, color: "#ff9800" }, line: { dash: "dot", color: "#ff9800" }, name: "Discreta"
              }]}
              layout={{ xaxis: { title: "Tempo (s)", range: [0, horizonte] }, yaxis: { title: "Saída" }, margin: { t: 20 } }}
              config={{ displayModeBar: false }}
              style={{ width: "100%", height: "300px" }}
            />
          </div>
        </div>
      </div>
    </MathJaxContext>
  );
}
