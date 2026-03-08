# Application Layout

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the initial application layout for hosted CNA runtime services.

---

## Directory Layout

```text
apps/
├── cna-api/
│   ├── README.md
│   └── main.py
└── cna-worker/
    ├── README.md
    └── main.py
```

---

## Design Position

The application layer is split by runtime responsibility.

- `cna-api` handles ingress, control-plane requests, health, and intake.
- `cna-worker` handles background processing and artifact generation.

---

## Future Growth

This structure should later grow to include:
- routers
- services
- schemas
- storage adapters
- AI adapters
- publish pipeline handlers
