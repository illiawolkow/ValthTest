# Nationality Prediction API

This FastAPI application predicts the likely nationality of a given name by aggregating data from [Nationalize.io](https://nationalize.io/) and provides additional country details from [REST Countries API](https://restcountries.com/). It uses a PostgreSQL database to cache results and manage user authentication.

## Features

- Predicts nationality probabilities for a given name.
- Caches results from external APIs to improve performance and reduce external calls.
- Provides detailed country information.
- User authentication with JWT (signup, login, protected routes).
- Asynchronous operations using FastAPI and SQLAlchemy with `asyncpg`.
- Database migrations managed with Alembic.
- Dockerized for easy setup and deployment.

## Project Structure

```
ValhTest/
├── alembic/                   # Alembic migration scripts
├── app/
│   ├── auth/                  # Authentication logic, JWT, dependencies
│   ├── core/                  # Core application settings, external API interaction
│   ├── routers/               # API endpoint definitions (auth, names)
│   ├── crud.py                # Database Create, Read, Update, Delete operations
│   ├── database.py            # Database engine, session, table creation logic
│   ├── main.py                # FastAPI application entry point and lifespan management
│   ├── models.py              # SQLAlchemy ORM models
│   └── schemas.py             # Pydantic schemas for data validation and serialization
├── tests/                     # Pytest tests for the application
├── .env.example               # Example environment variables
├── .gitignore
├── alembic.ini                # Alembic configuration
├── docker-compose.yml         # Docker Compose configuration
├── Dockerfile                 # Dockerfile for the FastAPI application
├── README.md                  # This file
├── requirements.txt           # Python dependencies
└── wait-for-postgres.sh       # Script to ensure Postgres is ready before app starts
```

## Prerequisites

- Docker ([Install Docker](https://docs.docker.com/get-docker/))
- Docker Compose ([Install Docker Compose](https://docs.docker.com/compose/install/))

## Setup and Running the Application

1.  **Clone the Repository (if applicable)**
    ```bash
    # git clone https://github.com/illiawolkow/ValthTest
    # cd ValthTest
    ```

2.  **Create Environment File**
    Copy the example environment file and customize it if necessary. For local Docker Compose setup, the defaults in `.env.example` are generally sufficient if you haven't changed PostgreSQL credentials or service names in `docker-compose.yml`.
    ```bash
    cp .env.example .env
    ```
    The `.env` file should look like this (defaults shown):
    ```env
    DATABASE_URL="postgresql+asyncpg://valth_user:valth_password@db:5432/valth_db"
    POSTGRES_USER="valth_user"
    POSTGRES_PASSWORD="valth_password"
    POSTGRES_DB="valth_db"

    JWT_SECRET_KEY="your_strong_jwt_secret_key_here"
    ALGORITHM="HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES=30

    NATIONALIZE_API_BASE_URL="https://api.nationalize.io/"
    RESTCOUNTRIES_API_BASE_URL="https://restcountries.com/v3.1/"
    ```
    **Important**: Change `JWT_SECRET_KEY` to a strong, unique secret for production or any sensitive environment.

3.  **Make `wait-for-postgres.sh` Executable**
    This script ensures the application waits for the PostgreSQL database to be ready before starting.
    ```bash
    chmod +x wait-for-postgres.sh
    ```

4.  **Build and Run with Docker Compose**
    This command will build the Docker image for the application (if not already built or if `Dockerfile` changed) and start the `web` (FastAPI app) and `db` (PostgreSQL) services.
    ```bash
    docker-compose up --build
    ```
    - Use `docker-compose up` to start if images are already built.
    - To run in detached mode (in the background), use `docker-compose up -d --build`.

    The application will be available at `http://localhost:8000`.
    The API documentation (Swagger UI) will be at `http://localhost:8000/docs`.
    The alternative API documentation (ReDoc) will be at `http://localhost:8000/redoc`.

5.  **Stopping the Application**
    To stop the services, press `Ctrl+C` in the terminal where `docker-compose up` is running, or use:
    ```bash
    docker-compose down
    ```
    To remove volumes (and thus delete PostgreSQL data), use `docker-compose down -v`.

## Running Tests

Tests are run using `pytest` inside the Docker container. Ensure the services are running (`docker-compose up -d`).

```bash
docker-compose exec web pytest -v
```

## API Endpoints Overview

All application-specific endpoints are prefixed with `/api/v1`.

### Authentication (`/api/v1/auth`)

-   `POST /token`: Login to get an access token. Expects form data with `username` and `password`.
-   `POST /signup`: Register a new user. Expects JSON body with `username`, `email`, `password`, `full_name`.
-   `POST /logout`: Placeholder for logout (client should clear token).
-   `GET /users/me`: Get details for the currently authenticated user.

### Names and Countries (`/api/v1`)

-   `GET /names/`: Predicts nationality for a given name.
    -   Query Parameter: `name` (string, required)
    -   Protected: Requires authentication.
-   `GET /popular-names/`: Retrieves a list of popular names for a given country based on access frequency.
    -   Query Parameter: `country` (string, required, ISO 3166-1 alpha-2 country code, e.g., "US")
    -   Protected: Requires authentication.

### Health Check

-   `GET /health`: A simple health check endpoint.

## Database Migrations (Alembic)

Alembic is used for managing database schema migrations.

-   **To create a new migration script (after changing SQLAlchemy models in `app/models.py`):**
    ```bash
    docker-compose exec web alembic revision -m "your_migration_message"
    ```
    Then edit the generated script in `alembic/versions/` to define the upgrade and downgrade steps.

-   **To apply migrations:**
    Migrations are automatically applied when the `web` service starts due to the command in `docker-compose.yml`:
    `alembic upgrade head`

-   **To downgrade (example):**
    ```bash
    docker-compose exec web alembic downgrade -1 
    ```

## External API Dependencies

-   **Nationalize.io**: Used to predict nationality based on a name. (`https://api.nationalize.io/`)
-   **REST Countries**: Used to fetch detailed information about countries. (`https://restcountries.com/v3.1/`)

These base URLs are configurable via environment variables `NATIONALIZE_API_BASE_URL` and `RESTCOUNTRIES_API_BASE_URL`. 
