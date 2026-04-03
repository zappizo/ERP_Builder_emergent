from __future__ import annotations

import json
import re
from textwrap import dedent
from typing import Any


def _slugify(value: Any, fallback: str) -> str:
    candidate = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return candidate or fallback


def _normalize_roles(master_json: dict[str, Any]) -> list[dict[str, Any]]:
    raw_roles = ((master_json.get("auth") or {}).get("roles") or []) if isinstance(master_json, dict) else []
    permissions_map = ((master_json.get("auth") or {}).get("permissions") or {}) if isinstance(master_json, dict) else {}
    roles: list[dict[str, Any]] = []

    for index, raw_role in enumerate(raw_roles, start=1):
        if isinstance(raw_role, dict):
            name = str(raw_role.get("name") or raw_role.get("id") or f"Role {index}")
            raw_permissions = raw_role.get("permissions") or permissions_map.get(_slugify(name, f"role-{index}")) or []
        else:
            name = str(raw_role or f"Role {index}")
            raw_permissions = permissions_map.get(_slugify(name, f"role-{index}")) or []
        roles.append(
            {
                "id": _slugify(name, f"role-{index}"),
                "name": name,
                "permissions": [str(permission) for permission in raw_permissions if permission not in (None, "", [], {})],
            }
        )

    if roles:
        return roles

    return [
        {"id": "administrator", "name": "Administrator", "permissions": ["manage", "approve", "configure"]},
        {"id": "operations-manager", "name": "Operations Manager", "permissions": ["view", "create", "update", "approve"]},
        {"id": "team-member", "name": "Team Member", "permissions": ["view", "create", "update"]},
    ]


def _build_demo_users(roles: list[dict[str, Any]]) -> list[dict[str, str]]:
    demo_users: list[dict[str, str]] = []
    used_slugs: set[str] = set()
    for index, role in enumerate(roles, start=1):
        slug_base = role["id"]
        slug = slug_base
        suffix = 2
        while slug in used_slugs:
            slug = f"{slug_base}-{suffix}"
            suffix += 1
        used_slugs.add(slug)
        demo_users.append(
            {
                "id": str(index),
                "name": f"{role['name']} Demo",
                "role": role["name"],
                "email": f"{slug}@demo.local",
                "password": f"{slug}123",
            }
        )
    return demo_users


def build_functional_template_frontend_bundle(
    master_json: dict[str, Any],
    modules: list[dict[str, Any]],
    profile: dict[str, Any],
) -> dict[str, Any]:
    roles = _normalize_roles(master_json)
    demo_users = _build_demo_users(roles)
    schema_payload = json.dumps(
        {
            "system": master_json.get("system", {}),
            "template": profile,
            "modules": modules,
            "auth": {"roles": roles, "demo_users": demo_users},
        },
        indent=2,
    )

    app_jsx = dedent(
        """
        import "./styles/template.css";
        import { useEffect, useState } from "react";
        import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
        import AuthScreen from "./components/AuthScreen";
        import Layout from "./components/Layout";
        import Dashboard from "./pages/Dashboard";
        import ModuleWorkspace from "./pages/ModuleWorkspace";
        import { api, clearStoredSession, hydrateStoredSession, persistStoredSession, setSessionHeaders } from "./lib/api";
        import { SessionContext } from "./lib/session";

        export default function App() {
          const [session, setSession] = useState(() => hydrateStoredSession());
          const [pending, setPending] = useState(false);
          const [error, setError] = useState("");

          useEffect(() => {
            if (session?.headers) {
              setSessionHeaders(session.headers);
              return;
            }
            setSessionHeaders({});
          }, [session]);

          async function handleLogin(credentials) {
            setPending(true);
            setError("");
            try {
              const response = await api.login(credentials);
              persistStoredSession(response);
              setSession(response);
            } catch (loginError) {
              setError(loginError.message || "Unable to sign in.");
            } finally {
              setPending(false);
            }
          }

          function handleLogout() {
            clearStoredSession();
            setSession(null);
            setError("");
          }

          if (!session) {
            return <AuthScreen onLogin={handleLogin} pending={pending} error={error} />;
          }

          return (
            <SessionContext.Provider value={{ session, setSession, onLogout: handleLogout }}>
              <BrowserRouter>
                <Layout>
                  <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/:moduleId" element={<ModuleWorkspace />} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </Layout>
              </BrowserRouter>
            </SessionContext.Provider>
          );
        }
        """
    ).strip()

    auth_screen_jsx = dedent(
        """
        import { useState } from "react";
        import { erpSchema } from "../data/schema";

        const initialDemo = erpSchema.auth?.demo_users?.[0] || { email: "", password: "" };

        export default function AuthScreen({ onLogin, pending, error }) {
          const [formState, setFormState] = useState({
            email: initialDemo.email || "",
            password: initialDemo.password || "",
          });

          function updateField(event) {
            const { name, value } = event.target;
            setFormState((current) => ({ ...current, [name]: value }));
          }

          function submit(event) {
            event.preventDefault();
            onLogin(formState);
          }

          function loginAsUser(user) {
            const nextState = { email: user.email, password: user.password };
            setFormState(nextState);
            onLogin(nextState);
          }

          return (
            <div className="erp-auth-shell">
              <div className="erp-auth-backdrop" />
              <section className="erp-auth-card">
                <div className="erp-auth-copy">
                  <p className="erp-eyebrow">{erpSchema.template?.hero_kicker || "Generated ERP"}</p>
                  <h1 className="erp-heading">{erpSchema.system.name}</h1>
                  <p className="erp-auth-body">
                    {erpSchema.template?.hero_body ||
                      "Use the seeded demo accounts to explore a fully wired ERP preview with backend actions."}
                  </p>
                </div>

                <form className="erp-form-stack" onSubmit={submit}>
                  <label className="erp-field">
                    <span className="erp-label">Email</span>
                    <input
                      className="erp-input"
                      name="email"
                      type="email"
                      value={formState.email}
                      onChange={updateField}
                      placeholder="name@demo.local"
                      autoComplete="username"
                      required
                    />
                  </label>

                  <label className="erp-field">
                    <span className="erp-label">Password</span>
                    <input
                      className="erp-input"
                      name="password"
                      type="password"
                      value={formState.password}
                      onChange={updateField}
                      placeholder="Enter password"
                      autoComplete="current-password"
                      required
                    />
                  </label>

                  {error ? <div className="erp-message erp-message-error">{error}</div> : null}

                  <button className="erp-button erp-button-primary" disabled={pending} type="submit">
                    {pending ? "Signing in..." : "Login to Preview"}
                  </button>
                </form>

                <div className="erp-demo-users">
                  <div className="erp-toolbar">
                    <div>
                      <p className="erp-label">Seeded Roles</p>
                      <h2 className="erp-heading erp-section-title">Demo Accounts</h2>
                    </div>
                    <span className="erp-badge erp-badge-ready">{erpSchema.auth?.demo_users?.length || 0} ready</span>
                  </div>
                  <div className="erp-card-grid">
                    {(erpSchema.auth?.demo_users || []).map((user) => (
                      <button
                        key={user.email}
                        type="button"
                        className="erp-demo-user"
                        onClick={() => loginAsUser(user)}
                        disabled={pending}
                      >
                        <span className="erp-avatar">{user.name.slice(0, 1)}</span>
                        <span className="erp-demo-copy">
                          <strong>{user.name}</strong>
                          <span>{user.role}</span>
                          <span>{user.email}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              </section>
            </div>
          );
        }
        """
    ).strip()

    layout_jsx = dedent(
        """
        import { Link, useLocation } from "react-router-dom";
        import { erpSchema } from "../data/schema";
        import { useSession } from "../lib/session";

        export default function Layout({ children }) {
          const location = useLocation();
          const { session, onLogout } = useSession();
          const isTopbar = erpSchema.template?.layout_mode === "topbar";
          const navItems = erpSchema.modules.map((module) => ({
            id: module.id,
            path: `/${module.path || module.id}`,
            name: module.name,
            short: (module.name || "M").slice(0, 1).toUpperCase(),
          }));

          return (
            <div className="erp-shell">
              <div className={isTopbar ? "block" : "lg:flex"}>
                {!isTopbar ? (
                  <aside className="erp-sidebar hidden lg:flex lg:w-[var(--erp-sidebar-width)] lg:flex-col lg:justify-between lg:px-5 lg:py-6">
                    <div className="space-y-6">
                      <div>
                        <p className="erp-eyebrow">{erpSchema.template?.hero_kicker || "ERP shell"}</p>
                        <h1 className="erp-heading mt-3 text-2xl font-semibold">{erpSchema.system.name}</h1>
                        <p className="erp-muted mt-3 text-sm leading-6">
                          {erpSchema.template?.summary || "Functional workspace generated from the current blueprint."}
                        </p>
                      </div>

                      <nav className="space-y-2">
                        <Link
                          to="/"
                          className={`erp-nav-link ${location.pathname === "/" ? "erp-nav-link-active" : ""}`}
                        >
                          <span className="erp-nav-icon">D</span>
                          <span>Overview</span>
                        </Link>
                        {navItems.map((item) => {
                          const active = location.pathname === item.path;
                          return (
                            <Link
                              key={item.id}
                              to={item.path}
                              className={`erp-nav-link ${active ? "erp-nav-link-active" : ""}`}
                            >
                              <span className="erp-nav-icon">{item.short}</span>
                              <span>{item.name}</span>
                            </Link>
                          );
                        })}
                      </nav>
                    </div>

                    <div className="erp-subpanel rounded-[24px] p-4">
                      <p className="erp-label">Signed in as</p>
                      <h2 className="erp-heading mt-2 text-lg font-semibold">{session.user.name}</h2>
                      <p className="erp-muted mt-1 text-sm">{session.user.role}</p>
                      <button type="button" className="erp-button erp-button-secondary mt-4 w-full" onClick={onLogout}>
                        Logout
                      </button>
                    </div>
                  </aside>
                ) : null}

                <div className="flex min-h-screen flex-1 flex-col">
                  <header className="erp-topbar sticky top-0 z-20 m-3 rounded-[28px] px-4 py-4 md:px-5">
                    <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
                      <div>
                        <p className="erp-eyebrow">{erpSchema.template?.reference_project || "Template reference"}</p>
                        <h1 className="erp-heading mt-2 text-2xl font-semibold md:text-3xl">
                          {erpSchema.template?.hero_title || `${erpSchema.system.name} Control Room`}
                        </h1>
                      </div>

                      <div className="erp-topbar-actions">
                        <div className="erp-pill erp-pill-neutral">{session.user.name}</div>
                        <div className="erp-pill erp-pill-neutral">{session.user.role}</div>
                        <div className="erp-pill erp-pill-positive">
                          {erpSchema.modules.length} modules connected
                        </div>
                        <button type="button" className="erp-button erp-button-secondary" onClick={onLogout}>
                          Logout
                        </button>
                      </div>
                    </div>

                    <nav className={`mt-4 flex flex-wrap gap-2 ${isTopbar ? "" : "lg:hidden"}`}>
                      <Link
                        to="/"
                        className={`erp-nav-link ${location.pathname === "/" ? "erp-nav-link-active" : ""}`}
                      >
                        <span className="erp-nav-icon">D</span>
                        <span>Overview</span>
                      </Link>
                      {navItems.map((item) => {
                        const active = location.pathname === item.path;
                        return (
                          <Link
                            key={item.id}
                            to={item.path}
                            className={`erp-nav-link ${active ? "erp-nav-link-active" : ""}`}
                          >
                            <span className="erp-nav-icon">{item.short}</span>
                            <span>{item.name}</span>
                          </Link>
                        );
                      })}
                    </nav>
                  </header>

                  <main className="flex-1 px-3 pb-6 md:px-4 xl:px-6">
                    <div className="mx-auto w-full max-w-7xl" style={{ padding: "var(--erp-shell-padding)" }}>
                      {children}
                    </div>
                  </main>
                </div>
              </div>
            </div>
          );
        }
        """
    ).strip()

    dashboard_jsx = dedent(
        """
        import { useEffect, useState } from "react";
        import { Link } from "react-router-dom";
        import { erpSchema } from "../data/schema";
        import { api } from "../lib/api";
        import { useSession } from "../lib/session";

        function toneClass(status) {
          if (status === "negative") {
            return "erp-pill erp-pill-negative";
          }
          if (status === "positive") {
            return "erp-pill erp-pill-positive";
          }
          return "erp-pill erp-pill-neutral";
        }

        export default function Dashboard() {
          const { session } = useSession();
          const [state, setState] = useState({ loading: true, error: "", data: null });

          async function loadDashboard() {
            setState((current) => ({ ...current, loading: true, error: "" }));
            try {
              const data = await api.dashboard();
              setState({ loading: false, error: "", data });
            } catch (error) {
              setState({ loading: false, error: error.message || "Unable to load dashboard.", data: null });
            }
          }

          useEffect(() => {
            loadDashboard();
          }, [session.user.id]);

          const metrics = state.data?.metrics || erpSchema.template?.kpi_metrics || [];
          const moduleCards = state.data?.modules || [];
          const recentActivity = state.data?.recent_activity || [];
          const workflowQueue = state.data?.workflow_queue || [];

          return (
            <div className="space-y-6">
              <section className="erp-hero rounded-[32px] p-6 md:p-8">
                <div className="erp-toolbar">
                  <div className="space-y-3">
                    <p className="erp-eyebrow">Welcome back</p>
                    <h2 className="erp-heading text-3xl font-semibold md:text-4xl">{session.user.name}</h2>
                    <p className="max-w-3xl text-sm leading-7 erp-muted">
                      {erpSchema.template?.hero_body ||
                        "This dashboard stays aligned to the saved template while every card is backed by a working API."}
                    </p>
                  </div>

                  <button type="button" className="erp-button erp-button-primary" onClick={loadDashboard}>
                    Refresh Metrics
                  </button>
                </div>
              </section>

              {state.error ? <div className="erp-message erp-message-error">{state.error}</div> : null}

              <section className="grid gap-4 md:grid-cols-3">
                {metrics.map((metric) => (
                  <article key={metric.id || metric.label} className="erp-panel rounded-[28px] p-5">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="erp-label">{metric.label}</p>
                        <h3 className="erp-heading mt-3 text-3xl font-semibold">{metric.value}</h3>
                        <p className="erp-muted mt-3 text-sm">{metric.trend}</p>
                      </div>
                      <span className={toneClass(metric.status)}>{metric.status || "live"}</span>
                    </div>
                  </article>
                ))}
              </section>

              <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
                <div className="erp-panel rounded-[28px] p-5">
                  <div className="erp-toolbar">
                    <div>
                      <p className="erp-label">Modules</p>
                      <h3 className="erp-heading erp-section-title">Connected Workspaces</h3>
                    </div>
                    <span className="erp-badge erp-badge-ready">{moduleCards.length} active</span>
                  </div>

                  <div className="erp-card-grid mt-5">
                    {moduleCards.map((module) => (
                      <article key={module.id} className="erp-subpanel rounded-[24px] p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <h4 className="erp-heading text-xl font-semibold">{module.name}</h4>
                            <p className="erp-muted mt-2 text-sm">{module.summary}</p>
                          </div>
                          <span className="erp-pill erp-pill-neutral">{module.record_count} records</span>
                        </div>
                        <div className="mt-4 grid gap-3 sm:grid-cols-2">
                          <div className="erp-mini-stat">
                            <span>Open items</span>
                            <strong>{module.open_count}</strong>
                          </div>
                          <div className="erp-mini-stat">
                            <span>Actions</span>
                            <strong>{(module.available_actions || []).length}</strong>
                          </div>
                        </div>
                        <Link className="erp-button erp-button-secondary mt-4 w-full justify-center" to={`/${module.path || module.id}`}>
                          Open Workspace
                        </Link>
                      </article>
                    ))}
                  </div>
                </div>

                <div className="space-y-6">
                  <section className="erp-panel rounded-[28px] p-5">
                    <div className="erp-toolbar">
                      <div>
                        <p className="erp-label">Queue</p>
                        <h3 className="erp-heading erp-section-title">Workflow Attention</h3>
                      </div>
                    </div>
                    {workflowQueue.length ? (
                      <ul className="erp-list mt-4">
                        {workflowQueue.map((item) => (
                          <li key={`${item.module_id}-${item.record_id}`} className="erp-list-item">
                            <div>
                              <strong>{item.title}</strong>
                              <p className="erp-muted mt-1 text-sm">{item.module_name}</p>
                            </div>
                            <span className="erp-pill erp-pill-neutral">{item.status}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <div className="erp-empty mt-4">No workflows need attention right now.</div>
                    )}
                  </section>

                  <section className="erp-panel rounded-[28px] p-5">
                    <div className="erp-toolbar">
                      <div>
                        <p className="erp-label">Activity</p>
                        <h3 className="erp-heading erp-section-title">Recent System Events</h3>
                      </div>
                    </div>
                    {recentActivity.length ? (
                      <ul className="erp-list mt-4">
                        {recentActivity.map((event) => (
                          <li key={`${event.id}-${event.record_id}`} className="erp-list-item">
                            <div>
                              <strong>{event.message}</strong>
                              <p className="erp-muted mt-1 text-sm">
                                {event.actor_name} • {event.module_name || event.module_id}
                              </p>
                            </div>
                            <span className="erp-muted text-sm">{event.created_at}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <div className="erp-empty mt-4">
                        {state.loading ? "Loading activity..." : "Activity will appear here as actions run."}
                      </div>
                    )}
                  </section>
                </div>
              </section>
            </div>
          );
        }
        """
    ).strip()

    module_workspace_jsx = dedent(
        """
        import { useEffect, useState } from "react";
        import { Link, useParams } from "react-router-dom";
        import { erpSchema } from "../data/schema";
        import { api } from "../lib/api";
        import { useSession } from "../lib/session";

        function toInputType(fieldName) {
          const normalized = String(fieldName || "").toLowerCase();
          if (normalized.includes("date")) {
            return "date";
          }
          if (normalized.includes("amount") || normalized.includes("price") || normalized.includes("qty")) {
            return "number";
          }
          if (normalized.includes("email")) {
            return "email";
          }
          return "text";
        }

        function buildInitialValues(moduleDefinition) {
          const fields = (moduleDefinition?.entities?.[0]?.fields || [])
            .filter((field) => !["id", "status", "created_at", "updated_at", "workflow_stage"].includes(field))
            .slice(0, 6);

          if (!fields.length) {
            return { name: "", notes: "" };
          }

          return fields.reduce((accumulator, field) => {
            accumulator[field] = "";
            return accumulator;
          }, {});
        }

        export default function ModuleWorkspace() {
          const { moduleId } = useParams();
          const { session } = useSession();
          const moduleDefinition =
            erpSchema.modules.find((item) => item.id === moduleId || item.path === moduleId) || erpSchema.modules[0];
          const [workspace, setWorkspace] = useState({ loading: true, error: "", data: null });
          const [values, setValues] = useState(() => buildInitialValues(moduleDefinition));
          const [note, setNote] = useState("");
          const [banner, setBanner] = useState("");
          const [busyRecordId, setBusyRecordId] = useState("");

          useEffect(() => {
            setValues(buildInitialValues(moduleDefinition));
            setNote("");
            setBanner("");
          }, [moduleDefinition.id]);

          async function loadWorkspace() {
            setWorkspace((current) => ({ ...current, loading: true, error: "" }));
            try {
              const data = await api.moduleSummary(moduleDefinition.id);
              setWorkspace({ loading: false, error: "", data });
            } catch (error) {
              setWorkspace({ loading: false, error: error.message || "Unable to load workspace.", data: null });
            }
          }

          useEffect(() => {
            loadWorkspace();
          }, [moduleDefinition.id, session.user.id]);

          function updateValue(event) {
            const { name, value } = event.target;
            setValues((current) => ({ ...current, [name]: value }));
          }

          async function createRecord(event) {
            event.preventDefault();
            setBanner("");
            try {
              await api.createRecord(moduleDefinition.id, { values, note });
              setValues(buildInitialValues(moduleDefinition));
              setNote("");
              setBanner("Record created successfully.");
              await loadWorkspace();
            } catch (error) {
              setBanner(error.message || "Unable to create record.");
            }
          }

          async function runAction(recordId, action) {
            setBusyRecordId(recordId);
            setBanner("");
            try {
              await api.runAction(moduleDefinition.id, recordId, action, note);
              setBanner(`Action '${action}' completed.`);
              await loadWorkspace();
            } catch (error) {
              setBanner(error.message || "Unable to run action.");
            } finally {
              setBusyRecordId("");
            }
          }

          const data = workspace.data;
          const formFields = (data?.form_fields || []).filter(
            (field) => !["id", "status", "created_at", "updated_at", "workflow_stage"].includes(field.name),
          );
          const records = data?.records || [];
          const activity = data?.recent_activity || [];

          return (
            <div className="space-y-6">
              <section className="erp-panel rounded-[28px] p-5">
                <div className="erp-toolbar">
                  <div>
                    <p className="erp-label">{moduleDefinition.name}</p>
                    <h2 className="erp-heading erp-section-title">{data?.module?.headline || `${moduleDefinition.name} Workspace`}</h2>
                    <p className="erp-muted mt-2 text-sm">{data?.module?.summary || moduleDefinition.summary}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button type="button" className="erp-button erp-button-secondary" onClick={loadWorkspace}>
                      Refresh
                    </button>
                    <Link to="/" className="erp-button erp-button-secondary">
                      Back to Dashboard
                    </Link>
                  </div>
                </div>

                <div className="mt-5 grid gap-4 md:grid-cols-3">
                  <div className="erp-mini-stat">
                    <span>Visible records</span>
                    <strong>{records.length}</strong>
                  </div>
                  <div className="erp-mini-stat">
                    <span>Role access</span>
                    <strong>{session.user.role}</strong>
                  </div>
                  <div className="erp-mini-stat">
                    <span>Workflow actions</span>
                    <strong>{(data?.available_actions || []).length}</strong>
                  </div>
                </div>
              </section>

              {workspace.error ? <div className="erp-message erp-message-error">{workspace.error}</div> : null}
              {banner ? <div className="erp-message">{banner}</div> : null}

              <section className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
                <form className="erp-panel rounded-[28px] p-5" onSubmit={createRecord}>
                  <div className="erp-toolbar">
                    <div>
                      <p className="erp-label">Create</p>
                      <h3 className="erp-heading erp-section-title">New {data?.module?.entity_name || "Record"}</h3>
                    </div>
                    <span className="erp-pill erp-pill-neutral">{formFields.length} fields</span>
                  </div>

                  <div className="erp-form-grid mt-5">
                    {formFields.length ? (
                      formFields.map((field) => (
                        <label key={field.name} className="erp-field">
                          <span className="erp-label">{field.label}</span>
                          <input
                            className="erp-input"
                            name={field.name}
                            type={field.input_type || toInputType(field.name)}
                            value={values[field.name] || ""}
                            onChange={updateValue}
                            placeholder={`Enter ${String(field.label || field.name).toLowerCase()}`}
                          />
                        </label>
                      ))
                    ) : (
                      <div className="erp-empty">This workspace did not define custom fields, so the generator will create a simple record entry.</div>
                    )}
                  </div>

                  <label className="erp-field mt-4">
                    <span className="erp-label">Operator Note</span>
                    <textarea
                      className="erp-textarea"
                      name="note"
                      rows="4"
                      value={note}
                      onChange={(event) => setNote(event.target.value)}
                      placeholder="Optional implementation note, approval comment, or context"
                    />
                  </label>

                  <div className="erp-form-actions mt-5">
                    <button type="submit" className="erp-button erp-button-primary">
                      Save Record
                    </button>
                    <button
                      type="button"
                      className="erp-button erp-button-secondary"
                      onClick={() => {
                        setValues(buildInitialValues(moduleDefinition));
                        setNote("");
                      }}
                    >
                      Reset Form
                    </button>
                  </div>
                </form>

                <section className="erp-panel rounded-[28px] p-5">
                  <div className="erp-toolbar">
                    <div>
                      <p className="erp-label">Live Data</p>
                      <h3 className="erp-heading erp-section-title">Working Buttons and Records</h3>
                    </div>
                    <span className="erp-badge erp-badge-ready">{records.length} loaded</span>
                  </div>

                  {records.length ? (
                    <div className="erp-table-wrap mt-5">
                      <table className="erp-table">
                        <thead>
                          <tr>
                            <th>Record</th>
                            <th>Status</th>
                            <th>Owner</th>
                            <th>Workflow</th>
                            <th>Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {records.map((record) => (
                            <tr key={record.id}>
                              <td>
                                <div className="font-semibold text-white">{record.title}</div>
                                <div className="erp-muted mt-1 text-sm">{record.summary}</div>
                              </td>
                              <td>
                                <span className="erp-pill erp-pill-neutral">{record.status}</span>
                              </td>
                              <td>{record.owner}</td>
                              <td>{record.workflow_stage}</td>
                              <td>
                                <div className="erp-record-actions">
                                  {(record.actions || []).map((action) => (
                                    <button
                                      key={`${record.id}-${action}`}
                                      type="button"
                                      className="erp-button erp-button-secondary"
                                      disabled={busyRecordId === record.id}
                                      onClick={() => runAction(record.id, action)}
                                    >
                                      {busyRecordId === record.id ? "Working..." : action}
                                    </button>
                                  ))}
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="erp-empty mt-5">
                      {workspace.loading ? "Loading records..." : "No records yet. Use the form to create the first one."}
                    </div>
                  )}
                </section>
              </section>

              <section className="erp-panel rounded-[28px] p-5">
                <div className="erp-toolbar">
                  <div>
                    <p className="erp-label">Audit Trail</p>
                    <h3 className="erp-heading erp-section-title">Recent Workspace Activity</h3>
                  </div>
                </div>

                {activity.length ? (
                  <ul className="erp-list mt-5">
                    {activity.map((event) => (
                      <li key={`${event.id}-${event.record_id}`} className="erp-list-item">
                        <div>
                          <strong>{event.message}</strong>
                          <p className="erp-muted mt-1 text-sm">{event.actor_name} • {event.actor_role}</p>
                        </div>
                        <span className="erp-muted text-sm">{event.created_at}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="erp-empty mt-5">Actions from this workspace will appear here.</div>
                )}
              </section>
            </div>
          );
        }
        """
    ).strip()

    api_js = dedent(
        """
        const STORAGE_KEY = "generated-erp-session";
        let sessionHeaders = {};

        function withBase(path) {
          const base = (import.meta.env.VITE_API_BASE_URL || "").replace(/\\/+$/, "");
          return `${base}${path}`;
        }

        async function request(path, init = {}) {
          const isFormData = init.body instanceof FormData;
          const response = await fetch(withBase(path), {
            headers: {
              Accept: "application/json",
              ...(isFormData ? {} : { "Content-Type": "application/json" }),
              ...sessionHeaders,
              ...(init.headers || {}),
            },
            ...init,
          });

          const text = await response.text();
          let payload = {};
          try {
            payload = text ? JSON.parse(text) : {};
          } catch (_error) {
            payload = { detail: text };
          }

          if (!response.ok) {
            throw new Error(payload.detail || payload.error || `Request failed with status ${response.status}`);
          }

          return payload;
        }

        export function setSessionHeaders(headers) {
          sessionHeaders = headers || {};
        }

        export function hydrateStoredSession() {
          if (typeof window === "undefined") {
            return null;
          }

          const raw = window.localStorage.getItem(STORAGE_KEY);
          if (!raw) {
            return null;
          }

          try {
            const parsed = JSON.parse(raw);
            setSessionHeaders(parsed.headers || {});
            return parsed;
          } catch (_error) {
            window.localStorage.removeItem(STORAGE_KEY);
            return null;
          }
        }

        export function persistStoredSession(session) {
          if (typeof window !== "undefined") {
            window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
          }
          setSessionHeaders(session?.headers || {});
        }

        export function clearStoredSession() {
          if (typeof window !== "undefined") {
            window.localStorage.removeItem(STORAGE_KEY);
          }
          setSessionHeaders({});
        }

        export const api = {
          login: (payload) => request("/api/auth/login", { method: "POST", body: JSON.stringify(payload) }),
          me: () => request("/api/auth/me"),
          roles: () => request("/api/meta/roles"),
          dashboard: () => request("/api/dashboard"),
          workflowEvents: () => request("/api/workflow/events"),
          moduleSummary: (moduleId) => request(`/api/modules/${moduleId}`),
          createRecord: (moduleId, payload) =>
            request(`/api/modules/${moduleId}/records`, { method: "POST", body: JSON.stringify(payload) }),
          runAction: (moduleId, recordId, action, note = "") =>
            request(`/api/modules/${moduleId}/records/${recordId}/actions`, {
              method: "POST",
              body: JSON.stringify({ action, note }),
            }),
        };
        """
    ).strip()

    session_js = dedent(
        """
        import { createContext, useContext } from "react";

        export const SessionContext = createContext(null);

        export function useSession() {
          const value = useContext(SessionContext);
          if (!value) {
            throw new Error("Session context is not available.");
          }
          return value;
        }
        """
    ).strip()

    template_css = dedent(
        f"""
        :root {{
          --erp-primary: {profile["primary_color"]};
          --erp-accent: {profile["accent_color"]};
          --erp-accent-cyan: {profile["accent_cyan"]};
          --erp-background: {profile["background_color"]};
          --erp-surface: {profile["surface_color"]};
          --erp-text: {profile["text_color"]};
          --erp-muted: {profile["muted_color"]};
          --erp-disabled: {profile["disabled_color"]};
          --erp-border: {profile["border_color"]};
          --erp-success: {profile["success_color"]};
          --erp-danger: {profile["danger_color"]};
          --erp-font-heading: {profile["font_heading"]};
          --erp-font-body: {profile["font_body"]};
          --erp-shell-padding: {profile["container_padding"]};
          --erp-card-gap: {profile["card_gap"]};
          --erp-radius: {profile["border_radius"]};
          --erp-sidebar-width: {profile["sidebar_width"]};
        }}

        * {{
          box-sizing: border-box;
        }}

        html {{
          background: var(--erp-background);
        }}

        body {{
          margin: 0;
          min-width: 320px;
          min-height: 100vh;
          color: var(--erp-text);
          font-family: var(--erp-font-body);
          background:
            radial-gradient(circle at top left, color-mix(in srgb, var(--erp-primary) 18%, transparent) 0%, transparent 34%),
            radial-gradient(circle at top right, color-mix(in srgb, var(--erp-accent) 18%, transparent) 0%, transparent 30%),
            linear-gradient(180deg, color-mix(in srgb, var(--erp-background) 92%, black 8%) 0%, var(--erp-background) 52%, #05080f 100%);
        }}

        button,
        input,
        textarea {{
          font: inherit;
        }}

        button {{
          cursor: pointer;
        }}

        a {{
          color: inherit;
          text-decoration: none;
        }}

        #root {{
          min-height: 100vh;
        }}

        .erp-shell {{
          min-height: 100vh;
          color: var(--erp-text);
        }}

        .erp-sidebar {{
          position: sticky;
          top: 0;
          height: 100vh;
          border-right: 1px solid var(--erp-border);
          background: color-mix(in srgb, var(--erp-surface) 84%, var(--erp-background) 16%);
          backdrop-filter: blur(18px);
        }}

        .erp-topbar,
        .erp-panel,
        .erp-subpanel,
        .erp-auth-card {{
          border: 1px solid var(--erp-border);
          background: color-mix(in srgb, var(--erp-surface) 84%, transparent 16%);
          box-shadow: 0 28px 90px rgba(0, 0, 0, 0.28);
          backdrop-filter: blur(18px);
        }}

        .erp-topbar-actions,
        .erp-form-actions,
        .erp-record-actions {{
          display: flex;
          flex-wrap: wrap;
          gap: 0.75rem;
          align-items: center;
        }}

        .erp-hero {{
          border: 1px solid color-mix(in srgb, var(--erp-primary) 28%, var(--erp-border) 72%);
          background:
            radial-gradient(circle at top right, color-mix(in srgb, var(--erp-accent-cyan) 22%, transparent) 0%, transparent 32%),
            linear-gradient(135deg, color-mix(in srgb, var(--erp-primary) 20%, var(--erp-surface) 80%) 0%, color-mix(in srgb, var(--erp-accent) 14%, var(--erp-background) 86%) 100%);
        }}

        .erp-auth-shell {{
          position: relative;
          display: grid;
          place-items: center;
          min-height: 100vh;
          padding: 24px;
        }}

        .erp-auth-backdrop {{
          position: absolute;
          inset: 0;
          background:
            radial-gradient(circle at center, color-mix(in srgb, var(--erp-primary) 18%, transparent) 0%, transparent 38%),
            radial-gradient(circle at bottom right, color-mix(in srgb, var(--erp-accent) 20%, transparent) 0%, transparent 28%);
          pointer-events: none;
        }}

        .erp-auth-card {{
          position: relative;
          z-index: 1;
          width: min(1100px, 100%);
          display: grid;
          gap: 24px;
          padding: 28px;
          border-radius: 32px;
        }}

        .erp-auth-body,
        .erp-muted {{
          color: var(--erp-muted);
        }}

        .erp-heading {{
          margin: 0;
          font-family: var(--erp-font-heading);
          letter-spacing: -0.03em;
        }}

        .erp-section-title {{
          font-size: 1.5rem;
        }}

        .erp-eyebrow,
        .erp-label {{
          margin: 0;
          color: var(--erp-muted);
          font-size: 0.72rem;
          font-weight: 700;
          letter-spacing: 0.18em;
          text-transform: uppercase;
        }}

        .erp-form-stack,
        .erp-demo-users,
        .erp-list,
        .erp-field {{
          display: grid;
          gap: 1rem;
        }}

        .erp-form-grid,
        .erp-card-grid {{
          display: grid;
          gap: 1rem;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        }}

        .erp-input,
        .erp-textarea {{
          width: 100%;
          border: 1px solid var(--erp-border);
          border-radius: 18px;
          background: color-mix(in srgb, var(--erp-background) 40%, var(--erp-surface) 60%);
          color: var(--erp-text);
          padding: 0.88rem 1rem;
          outline: none;
        }}

        .erp-button {{
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 0.6rem;
          border-radius: 999px;
          border: 1px solid var(--erp-border);
          padding: 0.78rem 1rem;
          font-size: 0.88rem;
          font-weight: 700;
        }}

        .erp-button:disabled {{
          cursor: not-allowed;
          opacity: 0.68;
        }}

        .erp-button-primary {{
          color: white;
          border-color: transparent;
          background: linear-gradient(135deg, color-mix(in srgb, var(--erp-primary) 86%, white 14%) 0%, color-mix(in srgb, var(--erp-accent) 76%, var(--erp-primary) 24%) 100%);
        }}

        .erp-button-secondary {{
          color: var(--erp-text);
          background: color-mix(in srgb, var(--erp-background) 34%, var(--erp-surface) 66%);
        }}

        .erp-nav-link {{
          display: flex;
          align-items: center;
          gap: 0.85rem;
          border-radius: 18px;
          border: 1px solid transparent;
          padding: 0.9rem 0.95rem;
          color: var(--erp-muted);
        }}

        .erp-nav-link-active {{
          color: white;
          border-color: color-mix(in srgb, var(--erp-primary) 40%, var(--erp-border) 60%);
          background: linear-gradient(135deg, color-mix(in srgb, var(--erp-primary) 28%, transparent) 0%, color-mix(in srgb, var(--erp-accent) 18%, transparent) 100%);
        }}

        .erp-nav-icon,
        .erp-avatar {{
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border-radius: 999px;
          color: white;
          background: linear-gradient(135deg, color-mix(in srgb, var(--erp-primary) 82%, white 18%) 0%, color-mix(in srgb, var(--erp-accent-cyan) 72%, white 28%) 100%);
        }}

        .erp-nav-icon {{
          width: 2rem;
          height: 2rem;
          font-size: 0.78rem;
          font-weight: 700;
          text-transform: uppercase;
        }}

        .erp-avatar {{
          width: 38px;
          height: 38px;
          font-size: 0.82rem;
          font-weight: 700;
          text-transform: uppercase;
        }}

        .erp-pill,
        .erp-badge {{
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border-radius: 999px;
          padding: 0.42rem 0.8rem;
          font-size: 0.74rem;
          font-weight: 800;
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }}

        .erp-pill-positive,
        .erp-badge-ready {{
          background: color-mix(in srgb, var(--erp-success) 16%, transparent);
          color: var(--erp-success);
        }}

        .erp-pill-negative {{
          background: color-mix(in srgb, var(--erp-danger) 16%, transparent);
          color: var(--erp-danger);
        }}

        .erp-pill-neutral {{
          background: color-mix(in srgb, var(--erp-primary) 14%, transparent);
          color: color-mix(in srgb, var(--erp-primary) 84%, white 16%);
        }}

        .erp-demo-user,
        .erp-mini-stat,
        .erp-list-item {{
          border: 1px solid var(--erp-border);
          border-radius: 22px;
          background: color-mix(in srgb, var(--erp-background) 20%, transparent);
          padding: 1rem 1.1rem;
        }}

        .erp-mini-stat {{
          display: grid;
          gap: 0.35rem;
        }}

        .erp-list {{
          list-style: none;
          padding: 0;
          margin: 0;
        }}

        .erp-list-item {{
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 1rem;
        }}

        .erp-message {{
          border-radius: 20px;
          border: 1px solid color-mix(in srgb, var(--erp-success) 24%, var(--erp-border) 76%);
          background: color-mix(in srgb, var(--erp-success) 12%, transparent);
          color: var(--erp-text);
          padding: 0.95rem 1rem;
        }}

        .erp-message-error {{
          border-color: color-mix(in srgb, var(--erp-danger) 30%, var(--erp-border) 70%);
          background: color-mix(in srgb, var(--erp-danger) 12%, transparent);
        }}

        .erp-empty {{
          border-radius: 24px;
          border: 1px dashed color-mix(in srgb, var(--erp-primary) 35%, var(--erp-border) 65%);
          color: var(--erp-muted);
          padding: 1.2rem;
          background: color-mix(in srgb, var(--erp-background) 18%, transparent);
        }}

        .erp-table-wrap {{
          overflow-x: auto;
          border-radius: 24px;
          border: 1px solid var(--erp-border);
          background: color-mix(in srgb, var(--erp-surface) 88%, transparent);
        }}

        .erp-table {{
          width: 100%;
          min-width: 720px;
          border-collapse: collapse;
        }}

        .erp-table th,
        .erp-table td {{
          padding: 1rem 1.15rem;
          border-bottom: 1px solid color-mix(in srgb, var(--erp-border) 74%, transparent);
          text-align: left;
        }}

        .erp-table th {{
          color: var(--erp-muted);
          font-size: 0.72rem;
          font-weight: 800;
          letter-spacing: 0.16em;
          text-transform: uppercase;
        }}

        @media (min-width: 980px) {{
          .erp-auth-card {{
            grid-template-columns: 1fr 1fr;
            align-items: start;
          }}
        }}

        @media (max-width: 1023px) {{
          :root {{
            --erp-shell-padding: 18px;
          }}

          .erp-auth-card {{
            padding: 22px;
          }}

          .erp-table {{
            min-width: 620px;
          }}
        }}
        """
    ).strip()

    return {
        "files": [
            {"path": "src/App.jsx", "language": "jsx", "content": app_jsx},
            {"path": "src/components/AuthScreen.jsx", "language": "jsx", "content": auth_screen_jsx},
            {"path": "src/components/Layout.jsx", "language": "jsx", "content": layout_jsx},
            {"path": "src/pages/Dashboard.jsx", "language": "jsx", "content": dashboard_jsx},
            {"path": "src/pages/ModuleWorkspace.jsx", "language": "jsx", "content": module_workspace_jsx},
            {"path": "src/lib/api.js", "language": "js", "content": api_js},
            {"path": "src/lib/session.js", "language": "js", "content": session_js},
            {"path": "src/styles/template.css", "language": "css", "content": template_css},
            {"path": "src/data/schema.js", "language": "js", "content": f"export const erpSchema = {schema_payload};"},
        ],
        "dependencies": {
            "react": "^18.3.1",
            "react-router-dom": "^6.30.1",
            "tailwindcss": "^3.4.17",
        },
    }
