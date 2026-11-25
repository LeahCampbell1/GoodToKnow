
# News Application

## Overview

A Django-based news publishing application that allows readers, journalists and editors to interact with news content through role-based access control.

Built using Django and Django REST Framework, the application supports article and newsletter management, editorial approval, publisher and journalist subscriptions, and email notifications.

### Key Features

- User registration and token-based authentication.
- Role-based permissions for readers, journalists and editors.
- Publisher registration and management.
- Article and newsletter creation, editing and approval.
- Reader subscriptions to publishers and journalists.
- Browsing approved articles and newsletters.
- Email notifications following content approval.
- REST API endpoints for content and subscription management.
- Automated testing using Django's test framework.

### Technologies

- Python and Django
- Django REST Framework
- MariaDB
- Gunicorn
- Docker and Docker Compose
- HTML and CSS

---

## Installation and Setup (Virtual Environment)

### Prerequisites

- Git
- Python (use a version supported by the project dependencies).
- pip
- MariaDB
- A MariaDB database and user configured for the application.

### 1. Clone the repository

```bash
git clone <repository-url>
cd NewsApplication/news_app
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
```

**Windows:**

```bash
.venv\Scripts\activate
```

**macOS/Linux:**

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure MariaDB

Ensure MariaDB is installed and running, and that the application database and database user already exist.

Check the database configuration in Django's `settings.py`. Configure the database name, username, password, host and port to match your local MariaDB installation.

The application uses the MySQL database backend and requires `mysqlclient`.

### 5. Run database migrations

```bash
python manage.py migrate
```

### 6. Create an administrator account (optional)

```bash
python manage.py createsuperuser
```

### 7. Run the application

```bash
python manage.py runserver
```

Access the application at:

http://127.0.0.1:8000/

---

## Running with Docker

The application includes a Dockerfile and Docker Compose configuration (`docker.yml`) to build and run the Django application alongside a MariaDB database.

Docker Compose manages both containers, database connectivity, persistent storage and application startup.

### Prerequisites

- Git
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/macOS), or Docker Engine and the Docker Compose plugin (Linux).
- Docker must be installed and running.

No local Python or MariaDB installation is required when using Docker.

### 1. Clone the repository

```bash
git clone <repository-url>
cd NewsApplication/news_app
```

Ensure the following files are present in the application directory:

- `Dockerfile`
- `docker.yml`
- `requirements.txt`
- `manage.py`

### 2. Create the environment file

Docker Compose requires a `.env` file in the same directory as `docker.yml`.

Create a file named `.env` and add the following configuration:

```env
DB_NAME=news_app
DB_USER=django_user
DB_PASSWORD=your_database_password
DB_ROOT_PASSWORD=your_root_password
```

Replace the example passwords with your own secure values.

The variables configure the MariaDB database, application user and root account. Docker Compose uses them to initialise the database container and passes the environment file to the Django container.

Ensure any additional environment variables required by the Django application, such as its secret key or email configuration, are also provided if required by your project settings.

**Important:** Do not commit `.env` or real database credentials to version control.

### 3. Build and start the containers

From the directory containing `docker.yml`, run:

```bash
docker compose -f docker.yml up --build -d
```

This command:

- Builds the Django application image using the Dockerfile.
- Downloads the MariaDB 11.4 image if it is not already available.
- Creates the application and database containers.
- Creates the persistent Docker volumes.
- Starts MariaDB and waits for its health check to pass.
- Runs Django database migrations automatically.
- Collects static files.
- Starts Gunicorn on port 8000.

The `-d` option runs the containers in the background.

### 4. Check that the containers are running

```bash
docker compose -f docker.yml ps
```

Both `web` and `db` containers should be running. The database should report a healthy status.

To view application logs:

```bash
docker compose -f docker.yml logs -f
```

To view only the Django application logs:

```bash
docker compose -f docker.yml logs -f web
```

Press `Ctrl+C` to stop following the logs. This does not stop the containers.

### 5. Access the application

Once the containers have started successfully, open:

http://localhost:8000/

The Django application is served through Gunicorn inside the web container.

### 6. Create an administrator account (optional)

To create a Django superuser inside the running web container:

```bash
docker compose -f docker.yml exec web python manage.py createsuperuser
```

### 7. Stop the containers

To stop and remove the containers:

```bash
docker compose -f docker.yml down
```

This preserves the named Docker volumes, including the MariaDB database and collected static and media files.

To stop the containers and delete all persistent volumes:

```bash
docker compose -f docker.yml down -v
```

**Warning:** The second command permanently deletes the database and other data stored in the named volumes.

### Docker Configuration Summary

| Component | Configuration |
|---|---|
| Web application | Django |
| Application server | Gunicorn |
| Database | MariaDB 11.4 |
| Application port | 8000 |
| Docker image | `leahcampbell/news-app-web:latest` |
| Database storage | `mariadb_data` |
| Static file storage | `static_data` |
| Media file storage | `media_data` |

The Docker Compose configuration automatically handles database startup dependencies, migrations and static file collection. Named volumes ensure database and application files persist when containers are stopped or recreated.

---

## Testing and System Checks

Run the automated Django test suite from the activated virtual environment:

```bash
python manage.py test
```

Alternatively, run tests inside the Docker container:

```bash
docker compose -f docker.yml exec web python manage.py test
```

Run Django system checks:

```bash
python manage.py check
```

---

## Application Roles

The application supports three main user roles:

| Role | Responsibilities |
|---|---|
| **Reader** | Browse approved content and subscribe or unsubscribe from publishers and journalists. |
| **Journalist** | Create and manage their own articles and newsletters and view their subscribers. |
| **Editor** | Manage and approve articles and newsletters associated with their publisher and view publisher subscribers. |

Access to application features is controlled through authentication and role-based permissions.

---

## API Overview

The REST API provides endpoints for managing articles, newsletters, publishers, users and subscriptions.

| Endpoint | Description |
|---|---|
| `GET /api/articles/` | Retrieve approved articles. |
| `POST /api/articles/` | Create articles. |
| `GET /api/articles/<article_id>/` | Retrieve an individual article. |
| `PUT /api/articles/<article_id>/` | Edit an article. |
| `DELETE /api/articles/<article_id>/` | Delete an article. |
| `GET /api/subscribed/` | Retrieve content from subscribed publishers and journalists. |
| `GET /api/newsletters/` | Retrieve approved newsletters. |
| `GET /api/newsletters/<newsletter_id>/` | Retrieve an individual newsletter. |
| `POST /api/newsletters/<newsletter_id>/approve/` | Approve a newsletter. |
| `GET /api/users/?publisher_id=<id>` | Retrieve subscribers to a publisher. |
| `GET /api/publishers/` | Retrieve publishers. |

API permissions and authentication are enforced according to user roles.

---

## Documentation

The project includes Sphinx documentation covering the application's implementation and supporting functionality.

Refer to the project's Sphinx documentation for additional technical information.

---

## Future Improvements

Potential improvements include enhanced content search and filtering, expanded automated test coverage and production deployment.
