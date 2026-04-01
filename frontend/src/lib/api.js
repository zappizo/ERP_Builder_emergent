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
    return "";
  }

  return normalizeBaseUrl(origin) || "http://127.0.0.1:8001";
}

const backendUrl = resolveBackendUrl();
const API = backendUrl ? `${backendUrl}/api` : "/api";

export async function createProject(name, prompt) {
  const { data } = await axios.post(`${API}/projects`, { name, prompt });
  return data;
}

export async function listProjects() {
  const { data } = await axios.get(`${API}/projects`);
  return data;
}

export async function getProject(id) {
  const { data } = await axios.get(`${API}/projects/${id}`);
  return data;
}

export async function deleteProject(id) {
  const { data } = await axios.delete(`${API}/projects/${id}`);
  return data;
}

export async function getMessages(projectId) {
  const { data } = await axios.get(`${API}/projects/${projectId}/messages`);
  return data;
}

export async function sendChat(projectId, message) {
  const { data } = await axios.post(`${API}/projects/${projectId}/chat`, { message });
  return data;
}

export async function getPipelineStage(projectId, stage) {
  const { data } = await axios.get(`${API}/projects/${projectId}/pipeline/${stage}`);
  return data;
}
