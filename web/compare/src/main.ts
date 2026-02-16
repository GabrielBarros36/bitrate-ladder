import { formatModeLabel } from "./mode";

const root = document.querySelector("main");
if (root) {
  const note = document.createElement("p");
  note.textContent = `Active default mode: ${formatModeLabel("wipe")}`;
  root.appendChild(note);
}
