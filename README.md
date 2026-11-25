
# News Application

## Overview

A Django-based news publishing application that allows readers, journalists and editors to interact with news content through role-based access control.

The application uses Django REST Framework to provide API functionality for managing publishers, articles, newsletters and subscriptions.

## Features

- User registration and authentication.
- Role-based access for readers, journalists and editors.
- Editors register and or create publishers.
- Publisher and journalist subscriptions.
- Article creation, editing, deletion and approval.
- Newsletter creation, editing, deletion and approval.
- Editor approval of articles and newsletters.
- Email notifications following content approval.
- Browsing publishers, journalists and published content.
- REST API endpoints for content and subscription management.
- Automated testing with Django's test framework.

## Technologies Used

- Python
- Django
- Django REST Framework
- MariaDB
- HTML and CSS
- unittest.mock for testing and mocking external dependencies.

## Installation and Setup

### Prerequisites

- Python 3.10 or later (or the version specified by the project).
- pip
- Git
- MariaDB

### 1. Clone the repository


Navigate to the application directory:

```bash
cd NewsApplication/news_app
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate the environment.

**Windows:**

```bash
.venv\Scripts\activate
```

**macOS/Linux:**

```bash
source .venv/bin/activate
```

### 3. Install dependencies

If a requirements file is included:

```bash
pip install -r requirements.txt
```

Otherwise:

```bash
pip install django djangorestframework mysqlclient
```

### 4. MariaDB Configuration

- Ensure MariaDB is installed and the service is running.
- Ensure the application database and database user already exist.
- Activate the Django virtual environment.
- Install the MariaDB database connector if not already installed:

```bash
pip install mysqlclient
```

- Verify the existing database configuration in `settings.py`.
- Retain the provided database name, username, password, host and port.
- Ensure the configured database name matches the existing MariaDB database.

The existing database configuration is:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'news_app.db',
        'USER': 'django_user',
        'PASSWORD': 'SuperStrongPassword000',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}
```

- Do not create the MariaDB database or database user as part of these instructions.
- Do not modify the existing database credentials in `settings.py`.

### 5. Check the Django configuration

```bash
python manage.py check
```

### 6. Apply migrations

Generate migrations:

```bash
python manage.py makemigrations
```

Apply migrations to create the application tables:

```bash
python manage.py migrate
```

### 7. Create an administrator account (optional)

```bash
python manage.py createsuperuser
```

### 8. Start the development server

```bash
python manage.py runserver
```

Access the application at:

http://127.0.0.1:8000/

---

## Application Structure

```text
NewsApplication/
│
├── news_app/
│   ├── manage.py
│   ├── good_to_know/
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── tests.py
│   │   ├── templates/
│   │   └── migrations/
│   │
│   └── project configuration
│
│
└── README.md
```

## API Endpoints

All API endpoints require token authentication unless otherwise stated.

- **GET `/api/articles/`** – Retrieve all approved articles.
- **POST `/api/articles/`** – Allow journalists to create articles, either independently or under an affiliated publisher.
- **GET `/api/subscribed/`** – Allow readers to retrieve approved articles from their subscribed publishers and journalists.
- **GET `/api/articles/<article_id>/`** – Retrieve an individual article, subject to approval and ownership permissions.
- **PUT `/api/articles/<article_id>/`** – Allow journalists to edit their own articles and editors to edit articles belonging to their publishers.
- **DELETE `/api/articles/<article_id>/`** – Allow journalists to delete their own articles and editors to delete articles belonging to their publishers.
- **POST `/api/approved/`** – Receive and verify an approved article following distribution.
- **GET `/api/newsletters/`** – Retrieve all approved newsletters.
- **GET `/api/newsletters/<newsletter_id>/`** – Retrieve an individual newsletter, with additional access for its journalist author and assigned publisher editors.
- **POST `/api/newsletters/<newsletter_id>/approve/`** – Allow editors to approve newsletters belonging to their assigned publishers.
- **GET `/api/users/?publisher_id=<id>`** – Allow editors to retrieve readers subscribed to a specified publisher they manage.
- **GET `/api/publishers/`** – Retrieve a list of all publishers.

### API Features

- **Authentication:** Token-based authentication protects API endpoints.
- **Role-based permissions:** Access is restricted according to reader, journalist and editor roles.
- **Content approval:** Publisher-affiliated articles and newsletters require editorial approval before publication.
- **Subscription filtering:** Readers can retrieve content from their subscribed publishers and journalists.
- **Data validation:** Serializers and model validation ensure submitted data meets application requirements.
- **Content distribution:** Approved articles are distributed to subscribers by email and forwarded to the approved articles API.

### Run all tests

```bash
python manage.py test 
```

### Run system checks

```bash
python manage.py check
```

---


## User Roles and Permissions

The application supports three user roles:

| Role | Main responsibilities | Restrictions |
|---|---|---|
| **Reader** | Browse approved content; subscribe and unsubscribe from publishers and journalists; view subscribed content. | Cannot create, edit, delete or approve content; cannot access management functions. |
| **Journalist** | Create and manage their own articles and newsletters; view their subscribers. | Cannot approve content; cannot access editor-only or reader-only functions. |
| **Editor** | Review, edit, delete and approve articles and newsletters associated with their publisher; view publisher subscribers. | Cannot manage content belonging to other publishers without authorisation. |

All permissions are enforced through the application's authentication and authorisation controls.

---

## Future Improvements

Potential future enhancements include:

- Improved content search and filtering.
- Expanded automated test coverage.
- Production deployment.

---

## Project Summary

The News Application provides a role-based publishing platform built with Django and Django REST Framework.

It supports content creation, editorial approval, newsletter management and reader subscriptions, with separate permissions for each user role.

MariaDB provides the relational database backend for application data.

