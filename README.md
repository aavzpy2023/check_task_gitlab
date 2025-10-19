# GitLab Review Task Dashboard

![Python](https://img.shields.io/badge/Python-3.11-blue.svg) ![FastAPI](https://img.shields.io/badge/FastAPI-0.103-green.svg) ![Streamlit](https://img.shields.io/badge/Streamlit-1.33-ff4b4b.svg) ![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)

![Dashboard Screenshot](URL_TO_YOUR_SCREENSHOT.png)

A full-stack dashboard I designed and built to solve a real-world business problem: monitoring GitLab issues marked for review across a large portfolio of projects. As a QA Lead overseeing 40+ active projects, I engineered this tool to automate a tedious manual process, providing a centralized, real-time view of all pending review tasks.

The application is built with a modern, decoupled frontend/backend architecture and is fully containerized with Docker for development and production environments.

## The Problem It Solves

In a large development environment, manually tracking issues that require QA review across dozens of GitLab projects is time-consuming, inefficient, and prone to human error. This workflow creates bottlenecks, delays feedback to developers and testers, and makes it difficult for leads to get a high-level overview of the team's workload. This dashboard automates the entire process, providing an "at-a-glance" status of all tasks pending review.

## Architecture & Technology Stack

The system is architected as two distinct services communicating via an internal API, orchestrated by Docker Compose.

* **Backend (FastAPI):**
  * A robust API service written in Python using **FastAPI**.
  * Periodically fetches issue data from the **GitLab API** for multiple projects.
  * Handles errors gracefully (e.g., network timeouts, invalid project IDs) to ensure the service remains stable.
  * Reads project configurations from an external `projects.csv` file for easy management without code changes.
  * **Technologies:** `FastAPI`, `uvicorn`, `requests`.

* **Frontend (Streamlit):**
  * A dynamic and interactive web interface built with **Streamlit**.
  * Consumes the FastAPI backend to get real-time project and task data.
  * Features a responsive two-column layout with a sticky navigation menu for active projects, prioritized by task count.
  * Uses **Pandas** for data manipulation and presentation.
  * **Technologies:** `Streamlit`, `requests`, `pandas`.

* **DevOps:**
  * **Docker & Docker Compose:** The entire application is containerized with a multi-stage `Dockerfile.backend` and `Dockerfile.frontend`.
  * Docker compose file for local development (`docker-compose.yml`).

---

## Project Status & Roadmap

The dashboard is currently fully functional for its core purpose of monitoring and displaying tasks.

### Future Roadmap

* **[ ] LLM Integration for Summarization:** Integrate a Large Language Model (LLM) to provide natural language summaries of pending tasks (e.g., "There are 5 critical tasks for Project Alpha, mostly assigned to John Doe"). The initial proof-of-concept for context acquisition and formatting (`script.py`) is included in this repository.

* **[ ] Historical Analytics:** Add a database (e.g., SQLite or PostgreSQL) to store historical task data, allowing for trend analysis (e.g., average time in review per project).
* **[ ] User Authentication:** Implement a login system to personalize the dashboard and restrict access.

---

## Getting Started

### Prerequisites

* Docker & Docker Compose
* A GitLab instance and a Personal Access Token with `api` scope.

### Setup & Launch

1. **Clone the repository:**

    ```bash
    git clone [YOUR-REPOSITORY-URL]
    cd check_task_gitlab
    ```

2. **Configure Environment:**
    Create a `.env` file from the provided template:

    ```bash
    cp .env.example .env
    ```

    Then, edit the `.env` file and add your GitLab URL and token.

3. **Configure Projects:**
    Create a `projects.csv` file from the template:

    ```bash
    cp projects.csv.example projects.csv
    ```

    Then, edit `projects.csv` to include the IDs and names of the projects you want to monitor.

4. **Build and Launch:**
    Use the development compose file to build and run the services:

    ```bash
    docker-compose up --build -d
    ```

5. **Access the Dashboard:**
    Open your browser and navigate to `http://localhost:8501`.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
