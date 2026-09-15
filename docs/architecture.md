# Architecture

## System Architecture

```mermaid
graph TD
    A[User / Browser] -->|HTTP| B[Frontend - React / Next.js]

    B -->|REST API| C[Backend - FastAPI]

    C --> D[Data Processing - Python / Pandas]
    D --> E[Predictive ML - Scikit-learn]

    C --> F[(PostgreSQL Database)]

    E -->|Risk / Prediction| C
    C -->|Readiness & Maintenance Insights| B

    B --> G[AI Copilot]
    G -->|User Query| C
    C -->|Context & Analysis| G
