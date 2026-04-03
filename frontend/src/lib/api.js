import axios from "axios";

function normalizeBaseUrl(url) {
  return url?.trim()?.replace(/\/+$/, "");
}

function resolveBackendUrl() {
  const configured = normalizeBaseUrl(process.env.REACT_APP_BACKEND_URL);
  if (configured && configured !== "undefined" && configured !== "null") {
    return configured;
  }

  if (typeof window === "undefined") {
    return "http://127.0.0.1:8001";
  }

  const { protocol, hostname, port, origin } = window.location;
  if (port === "3000") {
    return `${protocol}//${hostname === "localhost" ? "localhost" : "127.0.0.1"}:8001`;
  }

  return normalizeBaseUrl(origin) || "http://127.0.0.1:8001";
}

const backendUrl = resolveBackendUrl();
const API = backendUrl ? `${backendUrl}/api` : "/api";

export async function createProject(name, prompt, templateId) {
  const payload = { name, prompt };
  if (templateId) {
    payload.template_id = templateId;
  }
  const { data } = await axios.post(`${API}/projects`, payload, { timeout: 12000 });
  return data;
}

export async function listProjectTemplates() {
  const { data } = await axios.get(`${API}/projects/templates`, { timeout: 10000 });
  return data;
}

export async function listProjects() {
  const { data } = await axios.get(`${API}/projects`, { timeout: 10000 });
  return data;
}

export async function getProject(id) {
  const { data } = await axios.get(`${API}/projects/${id}`, { timeout: 10000 });
  return data;
}

export async function deleteProject(id) {
  const { data } = await axios.delete(`${API}/projects/${id}`, { timeout: 10000 });
  return data;
}

export async function getMessages(projectId) {
  const { data } = await axios.get(`${API}/projects/${projectId}/messages`, { timeout: 10000 });
  return data;
}

export async function sendChat(projectId, message) {
  const { data } = await axios.post(`${API}/projects/${projectId}/chat`, { message }, { timeout: 150000 });
  return data;
}

export async function getPipelineStage(projectId, stage) {
  const { data } = await axios.get(`${API}/projects/${projectId}/pipeline/${stage}`, { timeout: 15000 });
  return data;
}

export async function runProjectLocally(projectId) {
  const { data } = await axios.post(`${API}/projects/${projectId}/run-local`, {}, { timeout: 300000 });
  return data;
}
