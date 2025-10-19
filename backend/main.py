import csv
import os
from contextlib import asynccontextmanager
from typing import List

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


# --- Data Models (Pydantic) ---
# Defines the data structure for API responses, ensuring type safety.
class Task(BaseModel):
    title: str
    description: str | None
    author: str
    url: str
    assignee: str | None
    milestone: str | None


class ProjectSummary(BaseModel):
    id: str
    name: str
    review_task_count: int


# --- Configuration ---
# Load sensitive data and configuration from environment variables.
GITLAB_URL = os.getenv("GITLAB_URL", "https://gitlab.azcuba.cu")
PRIVATE_TOKEN = os.getenv("GITLAB_TOKEN")
LABEL_TO_TRACK = "PARA REVISIÓN"
PROJECTS: dict[str, str] = {}


# --- Lifespan Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager. Code here runs on application startup.
    Loads the project list from the CSV file into memory.
    """
    print("--- [STARTUP] Loading projects from CSV... ---")
    load_projects_from_csv()
    yield
    print("--- [SHUTDOWN] Application is shutting down. ---")


def load_projects_from_csv():
    """
    Reads the projects.csv file and populates the global PROJECTS dictionary.
    Handles potential file errors gracefully.
    """
    global PROJECTS
    try:
        with open("projects.csv", mode="r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                project_id = row.get("project_id")
                project_name = row.get("project_name")
                if project_id and project_name:
                    PROJECTS[project_id.strip()] = project_name.strip()
            print(f"✅ Projects loaded successfully: {len(PROJECTS)} found.")
    except Exception as e:
        print(
            f"🚨 FATAL ERROR: Could not read 'projects.csv'. The application may not function correctly. Error: {e}"
        )


app = FastAPI(title="GitLab Task Monitor API", version="1.0.0", lifespan=lifespan)


# --- Business Logic (GitLab API Interaction) ---
def get_issues_from_gitlab(project_id: str) -> List[dict] | None:
    """
    Fetches open issues with a specific label from a GitLab project.
    Designed for robustness, handling both API and network errors.

    Args:
        project_id (str): The ID of the GitLab project.

    Returns:
        List[dict] | None: A list of issue objects if successful, None on failure.
    """
    if not PRIVATE_TOKEN:
        raise HTTPException(
            status_code=500, detail="GitLab token is not configured on the server."
        )

    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
    params = {"state": "opened", "labels": LABEL_TO_TRACK}
    api_url = f"{GITLAB_URL}/api/v4/projects/{project_id}/issues"

    try:
        # verify=False is used for self-hosted GitLab instances with self-signed certs.
        response = requests.get(
            api_url, headers=headers, params=params, verify=False, timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(
            f"    - ⚠️ API Warning: Call failed for project {project_id}. Status: {http_err.response.status_code}"
        )
        return None
    except requests.exceptions.RequestException as e:
        print(
            f"    - ⚠️ Network Warning: Call failed for project {project_id}. Error: {e}"
        )
        return None


# --- API Endpoints ---
@app.get("/projects/", response_model=List[ProjectSummary])
def get_projects_summary():
    """
    Returns a summary of all configured projects, including the count of tasks for review.
    It gracefully skips any projects where the GitLab API call fails.
    """
    if not PROJECTS:
        return []

    summary_list = []
    print("\n--- [LOG] Starting project scan... ---")
    for project_id, project_name in PROJECTS.items():
        print(f"  - Processing: '{project_name}' (ID: {project_id})")
        issues = get_issues_from_gitlab(project_id)
        if issues is None:
            continue

        summary_list.append(
            ProjectSummary(
                id=project_id, name=project_name, review_task_count=len(issues)
            )
        )
    print("--- [LOG] Project scan finished. ---\n")
    return summary_list


@app.get("/projects/{project_id}/review_tasks/", response_model=List[Task])
def get_project_review_tasks(project_id: str):
    """
    Retrieves all issues marked for review for a specific GitLab project.

    This endpoint queries the GitLab API for a given project ID and transforms
    the raw issue data into a structured list of Task objects. It is designed
    to be resilient, returning an empty list if the upstream API call fails,
    thus preventing errors in the frontend.

    Args:
        project_id (str): The ID of the GitLab project to query.

    Raises:
        HTTPException(404): If the provided project_id is not found in the
                            server's configured list of projects.

    Returns:
        List[Task]: A list of Task objects, each representing an issue
                    marked for review. Returns an empty list if no tasks
                    are found or if the GitLab API call fails.
    """
    if project_id not in PROJECTS:
        raise HTTPException(status_code=404, detail="Project not found.")

    issues = get_issues_from_gitlab(project_id)

    # Graceful handling of API failures.
    if issues is None:
        return []

    task_list = []
    for issue in issues:
        # Safely extract nested data, providing defaults to prevent crashes.
        assignee_name = (
            issue["assignees"][0].get("name") if issue.get("assignees") else None
        )
        milestone_title = (
            issue["milestone"].get("title") if issue.get("milestone") else None
        )

        task_list.append(
            Task(
                title=issue.get("title", "N/A"),
                description=issue.get("description"),
                author=issue.get("author", {}).get("name", "N/A"),
                url=issue.get("web_url", "#"),
                assignee=assignee_name,
                milestone=milestone_title,
            )
        )
    return task_list
