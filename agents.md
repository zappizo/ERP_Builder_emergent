# AGENTS.md — AI ERP Builder

## Mission
Build a production-ready SaaS platform called **AI ERP Builder**.

This platform lets a business user describe their business and workflow in plain language. The system then:
- gathers requirements,
- asks clarifying questions,
- generates a structured ERP blueprint,
- passes the blueprint to a code generation layer,
- produces a usable ERP application,
- allows iterative revisions through prompting,
- supports one-click deployment,
- supports automation integrations through n8n.

The result must be startup-grade, modular, secure, scalable, and user-friendly.

---

## Product Summary
The platform includes:

1. **Frontend SaaS App**
   - project dashboard
   - prompt intake UI
   - clarification chat UI
   - blueprint/spec viewer
   - generation progress UI
   - generated ERP preview shell
   - revision / change request UI
   - deployment UI
   - automation / n8n UI
   - settings / API configuration UI
   - project versions/history UI

2. **Backend Orchestration API**
   - authentication
   - project lifecycle management
   - prompt and requirement session handling
   - blueprint versioning
   - generation orchestration
   - deployment orchestration
   - logs, audit trail, and notifications
   - queue-based background jobs

3. **Planning Layer**
   - requirement analysis
   - clarification questioning
   - business workflow inference
   - ERP module inference
   - entity and relationship inference
   - RBAC inference
   - automation opportunity detection
   - JSON blueprint generation

4. **Code Generation Layer**
   - consumes blueprint JSON
   - generates modular ERP code
   - supports partial regeneration by changed scope
   - produces maintainable production-quality app structure

5. **Deployment and Automation Layer**
   - one-click deployment pipeline
   - Dockerized services
   - deployment config handling
   - status/log tracking
   - n8n automation support

---

## Core Build Objective
Generate the full repository as a **real buildable application**, not a toy demo.

The code must:
- be production-oriented,
- be modular,
- be strongly typed where applicable,
- use clean folder structures,
- include validation and error handling,
- include environment-driven config,
- avoid hardcoded secrets,
- support scale-minded architecture,
- be easy to extend later.

Do not produce shallow boilerplate.
Do not leave critical paths as vague TODOs.
Do not hardcode provider-specific assumptions unless encapsulated behind adapters.

---

## Required Engineering Standards

### General
- Prefer maintainability over hacks.
- Prefer clarity over unnecessary abstraction.
- Use clean naming conventions.
- Keep module boundaries clear.
- Separate concerns across UI, API, services, workers, and schemas.
- Add comments only where they improve maintainability or explain integration boundaries.

### Security
- Never hardcode API keys.
- Use environment variables for all secrets and external service credentials.
- Validate all external input.
- Sanitize outputs where needed.
- Protect all authenticated routes.
- Build RBAC-ready authorization foundations.
- Add audit logging for important actions.
- Consider prompt injection and unsafe code generation risks.
- Do not blindly execute AI-generated artifacts.

### Reliability
- Validate Planning API outputs against schemas.
- Validate Code Creator API outputs/metadata where applicable.
- Add retry logic for transient failures.
- Handle malformed AI outputs gracefully.
- Use queues for long-running operations.
- Track job statuses and logs.
- Support resumable or retryable pipelines where possible.

### Scalability
- Design for background workers.
- Use PostgreSQL.
- Add indexing strategy.
- Support multiple projects per user.
- Make generation and deployment asynchronous.
- Keep storage abstraction clean.

---

## Recommended Stack
Use a coherent, production-sensible stack.

### Preferred Default Stack
- **Frontend:** Next.js + TypeScript + Tailwind CSS
- **Backend:** FastAPI + Python
- **Database:** PostgreSQL
- **ORM:** SQLAlchemy
- **Auth:** JWT/session strategy with refresh support
- **Workers:** Celery + Redis or equivalent
- **Realtime updates:** WebSockets or SSE
- **Infra:** Docker + docker-compose
- **Automation integration:** n8n-compatible webhooks and workflow templates

This stack may be adjusted if a better production rationale is given, but keep it consistent.

---

## Expected High-Level Architecture

### Frontend Responsibilities
- user auth screens
- dashboard and project management
- prompt intake
- clarification chat
- blueprint visualizer
- generation progress
- generated ERP preview shell
- iterative change request interface
- deployment control page
- automation page
- settings and API configuration page

### Backend Responsibilities
- auth
- project CRUD
- requirement session handling
- blueprint generation orchestration
- versioning
- code generation job orchestration
- deployment job orchestration
- logging and tracing
- queue management
- notification hooks

### Planning Layer Responsibilities
- analyze business context
- ask follow-up questions
- detect ambiguity/missing requirements
- infer workflows/modules/entities/roles
- produce normalized structured JSON
- support revision workflows

### Code Generation Layer Responsibilities
- consume normalized blueprints
- create modular ERP code instructions
- support changed-module regeneration
- preserve version consistency

### Deployment Layer Responsibilities
- deployment config intake
- build/release orchestration
- logs/status exposure
- rollback-aware versioning
- automation hooks

---

## Product Features to Implement

### 1. User / Workspace / Project Management
- sign up / login
- profile
- multiple projects
- project lifecycle states
- version history
- clone project/version
- save draft

### 2. Prompt Intake
- large input area for business prompt
- templates/examples
- prompt validation
- metadata storage

### 3. Clarification Engine
- question/answer thread
- persistent requirement session
- completeness scoring
- resume later
- structured extraction from responses

### 4. Blueprint Generator
Generate structured JSON specs for:
- business summary
- domain/type
- ERP modules
- workflows
- entities and fields
- relationships
- forms
- dashboards
- reports
- roles
- permissions
- automations
- AI features
- validations
- integrations
- deployment preferences

### 5. Code Generation Pipeline
- trigger generation jobs
- track job status/logs
- support partial regeneration
- store outputs/metadata
- maintain version history

### 6. Generated ERP Expectations
Depending on the user’s business, generated ERPs should be able to support:
- CRM
- HRM
- inventory
- finance/accounting basics
- service/work order management
- dashboards/reports
- notifications
- audit logs
- role-based access control
- workflow automation
- AI helpers/assistants

### 7. Iterative Editing
- natural-language change request input
- blueprint update flow
- changed-scope detection
- partial regeneration
- version diff/changelog

### 8. Deployment
- one-click deployment flow
- deployment settings form
- environment placeholders
- status/log tracking
- rollback-friendly structure

### 9. n8n Integration
- workflow templates
- webhook-based triggers
- ERP event hooks
- basic automation recipe definitions

---

## Required Data Models
At minimum, include models/tables for:
- users
- projects
- prompts
- requirement_sessions
- clarification_questions
- clarification_answers
- blueprint_versions
- generation_jobs
- generated_artifacts
- project_versions
- deployments
- deployment_logs
- api_configurations
- automation_workflows
- audit_logs
- notifications
- user_sessions

All major tables should include:
- primary key
- created_at
- updated_at
- status fields where appropriate
- foreign keys
- indexing considerations
- soft delete where appropriate

---

## Required JSON Contracts
Define strict schemas for:
- prompt intake payload
- clarification question object
- clarification answer object
- normalized requirement model
- ERP blueprint
- modules
- workflows
- entities
- fields
- relationships
- roles and permissions
- automation recipes
- code generation job spec
- deployment config
- change request spec
- blueprint diff spec

All AI-facing outputs must be schema-validated.

---

## API Expectations
Implement serious backend APIs for:
- auth
- projects
- prompts
- requirement sessions
- clarification Q/A
- blueprint generation
- version retrieval
- code generation jobs
- job status/logs
- deployments
- deployment status/logs
- n8n workflow registration/listing
- settings/api configuration
- notifications

Use clean route grouping and request/response schemas.

---

## Frontend UX Expectations
Build polished, modern SaaS pages for:
- login / register
- dashboard
- new project
- prompt intake
- clarification chat
- blueprint viewer
- generation progress
- generated ERP preview shell
- revision/change request page
- deployment page
- automation page
- project history page
- settings page

UI must be responsive and production-feeling.
Include loading, error, and empty states.

---

## AI Integration Rules
The platform will receive real API keys later.
Until then:
- create provider adapters,
- create clear interfaces,
- use env placeholders,
- keep provider-specific logic isolated,
- make the system easy to swap between planning/code providers later.

### Planning Adapter Must Support
- generate clarification questions
- convert final requirements into blueprint JSON
- revise blueprint from change requests
- infer modules/entities/workflows/roles

### Code Creator Adapter Must Support
- consume blueprint JSON
- generate app/module instructions
- support changed-module regeneration
- return structured job metadata

---

## Quality Bar for Generated Code
Every output should aim for:
- clean architecture
- production-minded defaults
- buildable source files
- no missing core files
- strong schema validation
- reusable components
- sensible service abstractions
- proper error handling
- sensible test scaffolding
- clear README and setup docs

Do not stop at design only.
Generate actual code and file contents.

---

## Build Sequence
Follow this implementation order:

### Phase 1 — Foundation
1. explain final architecture
2. define exact stack
3. define folder structure
4. define database schema
5. define JSON contracts
6. define backend route map
7. define frontend route/page map
8. define AI orchestration pipeline
9. define deployment architecture

### Phase 2 — Backend Core
Build:
- backend app scaffold
- config/env system
- auth foundation
- models
- migrations setup
- schemas/DTOs
- services
- repositories if used
- queue/job layer
- logging
- API routes

### Phase 3 — Frontend Core
Build:
- app shell
- auth screens
- dashboard
- project screens
- prompt intake UI
- clarification chat UI
- blueprint view UI
- progress/status UI
- deployment UI
- settings UI

### Phase 4 — AI Orchestration
Build:
- planning adapter interfaces
- code creator adapter interfaces
- schema validation
- retry handling
- malformed output handling
- version-aware orchestration
- partial regeneration pipeline

### Phase 5 — Deployment and Automation
Build:
- Docker setup
- worker setup
- deployment orchestration scaffold
- n8n hooks/templates
- artifact/log tracking

### Phase 6 — Documentation and Polish
Add:
- README
- env examples
- architecture docs
- sample JSON blueprints
- sample prompts
- seed data
- local dev instructions

---

## Output Requirements for the Coding Agent
When generating code:
- show file paths clearly,
- include full file contents for important files,
- do not omit essential infrastructure files,
- continue across multiple responses if needed,
- preserve consistency across files,
- make assumptions explicitly once, then proceed.

When something cannot be fully implemented without real API keys or provider details:
- build a clean adapter interface,
- add placeholders through config,
- document exactly where real credentials or provider calls will be inserted.

---

## Non-Negotiables
- No hardcoded secrets
- No fake production claims without structure to support them
- No shallow mock-only architecture presented as finished
- No brittle monolith if modular separation is clearly needed
- No skipping schema validation for AI outputs
- No skipping versioning for blueprints and generations
- No skipping job/status tracking for long-running tasks

---

## Sample Build Prompt for the Agent
Use this instruction internally while building:

> Build AI ERP Builder as a production-grade SaaS platform with Next.js frontend, FastAPI backend, PostgreSQL persistence, queue-backed long-running jobs, schema-validated AI orchestration, modular architecture, versioned blueprint generation, partial regeneration support, deployment scaffolding, and n8n automation support. Generate actual code and file structures, not just high-level plans.

---

## Completion Standard
The repository should feel like a serious MVP for a startup building an AI-powered ERP generation platform.

It should be ready for:
- local development,
- real provider integration later,
- iterative feature expansion,
- deployment hardening,
- production-minded evolution.

