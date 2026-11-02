import React from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/dm-sans";
import "@fontsource-variable/noto-sans-kr";
import App from "./App";
import "./styles.css";
import "./reference.css";
import "./research.css";

createRoot(document.getElementById("root")).render(<App />);
