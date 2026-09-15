# Setup Guide — MissionReady Copilot

> Complete local development environment setup for the MissionReady Copilot project.

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.12+ | https://python.org |
| Node.js | 18+ (24 recommended) | https://nodejs.org |
| npm | 9+ | Bundled with Node.js |
| Docker Desktop | 24+ | https://docker.com |
| Git | Any recent version | https://git-scm.com |

Docker is recommended for running the local PostgreSQL database.

Alternatively, a cloud PostgreSQL database such as Neon or Supabase can be used by providing its connection string through `DATABASE_URL`.

---

## 1 — Clone the Repository

```bash
git clone https://github.com/DarshitSorathiya/bob-ai-hackathon-Chatpate-4.git

cd bob-ai-hackathon-Chatpate-4
