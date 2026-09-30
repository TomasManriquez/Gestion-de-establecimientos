---
name: project-documentation-standard
description: "Enforces a strict 8-doc standard and gap analysis for project documentation."
version: 1.0.0
author: Hermes Agent
---

# Project Documentation Standard (PDS)

## 1. Mandatory Structure
Every project must maintain a `Documentacion/` folder with:
- `00-README.md`: Purpose, Domain Glossary, Navigation.
- `01-arquitectura.md`: C4 Model, Tech Stack, Layers, Request Lifecycle.
- `02-modelo-datos.md`: Schemas, Pydantic/DTOs, Indexing, Sensitive fields.
- `03-api-contract.md`: Endpoints, Conventions, Breaking Change Policy.
- `04-seguridad-y-acceso.md`: Auth flow, RBAC Matrix, Security Invariants.
- `05-guia-de-extension.md`: Extension recipes, Limits, Tech Debt, DoD.
- `06-decisiones-adr.md`: Architecture Decision Records.
- `07-operacion.md`: Setup, Seeding, Deployment, Backups, Diagnostics.

## 2. Gap Analysis (The 'D' System)
Identify technical debt using the `🔸 D[Number]` notation:
- Example: `🔸 D1 — loss of coordinates. database_service.py:207-219...`
- Every `D` must cite the specific `file:line`.

## 3. Versioning Policy
- `.md` files MUST be versioned in Git.
- `.xlsx`, `.json`, `.csv` MUST be gitignored.

## 4. Verification
1. Cross-reference endpoints with controllers.
2. Validate Mermaid diagrams.
3. Align security invariants with actual tests.
