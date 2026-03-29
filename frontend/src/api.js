import axios from "axios";
const B = "/api";
export const api = {
  status:          ()      => axios.get(`${B}/status`),
  metrics:         ()      => axios.get(`${B}/metrics`),
  fi:              ()      => axios.get(`${B}/feature-importance`),
  upload:          (file)  => { const f=new FormData(); f.append("file",file); return axios.post(`${B}/upload`,f); },
  drift:           (month) => axios.post(`${B}/drift?month=${encodeURIComponent(month||"")}`),
  explain:         (month) => axios.post(`${B}/explain?month=${encodeURIComponent(month||"")}`),
  finetune:        (month) => axios.post(`${B}/retrain/finetune?month=${encodeURIComponent(month||"")}`),
  sliding:         (month) => axios.post(`${B}/retrain/sliding?month=${encodeURIComponent(month||"")}`),
  predict:         ()      => axios.post(`${B}/predict`),
  nextMonthPrompt: ()      => axios.get(`${B}/next-month-prompt`),
  logbook:         ()      => axios.get(`${B}/logbook`),
  downloadCSV:     ()      => `${B}/predict/download`,
};
