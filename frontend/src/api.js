import axios from "axios";
const B = "/api";
export const api = {
  status:          ()      => axios.get(`${B}/status`),
  metrics:         ()      => axios.get(`${B}/metrics`),
  fi:              ()      => axios.get(`${B}/feature-importance`),
  upload:          (file)  => { const f=new FormData(); f.append("file",file); return axios.post(`${B}/upload`,f); },
  drift:           ()      => axios.post(`${B}/drift`),
  finetune:        ()      => axios.post(`${B}/retrain/finetune`),
  sliding:         ()      => axios.post(`${B}/retrain/sliding`),
  predict:         ()      => axios.post(`${B}/predict`),
  logbook:         ()      => axios.get(`${B}/logbook`),
  storeXAI:        (data)  => axios.post(`${B}/xai/store-explanation`, data),
  downloadCSV:     ()      => `${B}/predict/download`,
};
