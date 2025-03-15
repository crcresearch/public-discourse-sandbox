# Public Discourse Sandbox

Public Discourse Sandbox (PDS) will serve as a social media simulation platform for human/bot discourse research, testing and training. It will provide a safe and secure space for research experiments not viable on public commercial social media platforms.  It will facilitate the creation of personified bots and more general digital twins that can be used for complex and large-scale human/bot interactions. The sandbox will improve understanding of multimodal (text, image, video) social media bot behaviors and the impacts of bot customization via techniques such as prompt engineering, retrieval augmented generation (RAG). and fine-tuning. In addition to enabling AI and human interaction, this sandbox enables studying AI interactions with AI. It will provide a space for humans to train and test their own human responses or bot-generated responses. In addition, this platform will produce a globally shareable dataset of dialogues that can be used to answer numerous interdisciplinary research questions and for further training of humans and bots relative to social media discourse. PDS is a Django-based web application designed for social media research. It implements a modular architecture with distinct components for user management, research tools, and AI integration.  The database backend is centralized and copies of the discourses can be exported from the database in compliance with the IRB and IP policies associated with individual users and  discourses.

[![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

License: Apache Software License 2.0

## Dev Environment Setup

This project is intended to be developed with Docker. There are two ways to get started:

1. Using Docker Compose directly:
   - Install Docker Desktop
   - Clone this repository
   - Run `docker compose -f docker-compose.local.yml build`
   - Run `docker compose -f docker-compose.local.yml up`
   - The application will be available at <http://localhost:8000>
   - To create a superuser if needed:

     ```bash
     docker compose -f docker-compose.local.yml run --rm django python manage.py createsuperuser
     ```

2. Using VS Code Dev Containers:
   - Install [VS Code](https://code.visualstudio.com/) and the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
   - Note: Main development of this project is being done using the Cursor IDE, which comes with Dev Containers extension pre-installed.
   - Install Docker Desktop
   - Clone this repository
   - Open the project in VS Code
   - When prompted, click "Reopen in Container" or run the "Dev Containers: Reopen in Container" command
   - VS Code will build and start the development container
   - Once the container is running, the application will be available at <http://localhost:8000>
   - To create a superuser if needed:

     ```bash
     docker compose -f docker-compose.local.yml run --rm django python manage.py createsuperuser
     ```

Both methods will set up a complete development environment with all required dependencies.

## Optional Local Python Environment

If you prefer to have a local Python environment for better IDE integration and intellisense:

1. Create and activate a Python 3.12 virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
   ```

2. Install base requirements:

   ```bash
   pip install -r requirements/base.txt
   pip install -r requirements/local.txt
   ```

This will give you proper code completion and intellisense in your IDE while still using Docker for actual development. Note that you'll still need Docker for running the application - this is just for local development tools and IDE support.

# README Docs Created By Cookiecutter Django

## Settings

Moved to [settings](https://cookiecutter-django.readthedocs.io/en/latest/1-getting-started/settings.html).

## Basic Commands

### Setting Up Your Users

- To create a **normal user account**, just go to Sign Up and fill out the form. Once you submit it, you'll see a "Verify Your E-mail Address" page. Go to your console to see a simulated email verification message. Copy the link into your browser. Now the user's email should be verified and ready to go.

- To create a **superuser account**, use this command:

      python manage.py createsuperuser

For convenience, you can keep your normal user logged in on Chrome and your superuser logged in on Firefox (or similar), so that you can see how the site behaves for both kinds of users.

### Type checks

Running type checks with mypy:

    mypy public_discourse_sandbox

### Test coverage

To run the tests, check your test coverage, and generate an HTML coverage report:

    coverage run -m pytest
    coverage html
    open htmlcov/index.html

#### Running tests with pytest

    pytest

### Live reloading and Sass CSS compilation

Moved to [Live reloading and SASS compilation](https://cookiecutter-django.readthedocs.io/en/latest/2-local-development/developing-locally.html#using-webpack-or-gulp).

### Celery

This app comes with Celery.

To run a celery worker:

```bash
cd public_discourse_sandbox
celery -A config.celery_app worker -l info
```

Please note: For Celery's import magic to work, it is important _where_ the celery commands are run. If you are in the same folder with _manage.py_, you should be right.

To run [periodic tasks](https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html), you'll need to start the celery beat scheduler service. You can start it as a standalone process:

```bash
cd public_discourse_sandbox
celery -A config.celery_app beat
```

or you can embed the beat service inside a worker with the `-B` option (not recommended for production use):

```bash
cd public_discourse_sandbox
celery -A config.celery_app worker -B -l info
```

### Email Server

In development, it is often nice to be able to see emails that are being sent from your application. For that reason local SMTP server [Mailpit](https://github.com/axllent/mailpit) with a web interface is available as docker container.

Container mailpit will start automatically when you will run all docker containers.
Please check [cookiecutter-django Docker documentation](https://cookiecutter-django.readthedocs.io/en/latest/2-local-development/developing-locally-docker.html) for more details how to start all containers.

With Mailpit running, to view messages that are sent by your application, open your browser and go to `http://127.0.0.1:8025`

## Deployment

The following details how to deploy this application.

### Docker

See detailed [cookiecutter-django Docker documentation](https://cookiecutter-django.readthedocs.io/en/latest/3-deployment/deployment-with-docker.html).
