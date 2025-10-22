import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import Home from "./Home.jsx";
import Indexdiscreto from "./indexdiscreto.jsx";
import Indexblocos from "./indexblocos.jsx";

export default function Root() {
  const getRoute = () => (window.location.hash.replace(/^#/, "") || "/");
  const [route, setRoute] = useState(getRoute());

  useEffect(() => {
    if (!window.location.hash) {
      window.location.hash = "/"; 
      setRoute("/");              
    }
    const onHashChange = () => setRoute(getRoute());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  if (route === "/discreto") return <Indexdiscreto />;
  if (route === "/blocos") return <Indexblocos />;
  return <Home />;
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);