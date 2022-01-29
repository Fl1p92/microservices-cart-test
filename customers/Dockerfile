# Builder image
FROM python:3.10-slim-bullseye as builder

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Create a virtual environment and activate it
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" VIRTUAL_ENV="/opt/venv"

# Copy file of project dependencies
COPY requirements.in .

# Compile and install any needed packages specified in requirements.in
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir pip-tools && \
    pip-compile --quiet --output-file=/opt/requirements.txt && \
    pip-sync /opt/requirements.txt --pip-args '--no-cache-dir'

# Final image
FROM python:3.10-slim-bullseye

# Copy the virtual environment from the previous image
COPY --from=builder /opt/venv /opt/venv

# Activate the virtual environment and set the envs
ENV PATH="/opt/venv/bin:$PATH" VIRTUAL_ENV="/opt/venv"
ENV SYSTEM_USER_ID=1000 SYSTEM_USER=micro_user SERVICE_NAME=customers
ENV PROJECT_HOME=/home/$SYSTEM_USER
ENV PROJECT_ROOT=$PROJECT_HOME/$SERVICE_NAME
ENV PYTHONPATH=$PROJECT_ROOT:$PYTHONPATH PYTHONSTARTUP=$PROJECT_ROOT/.python_startup.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONBREAKPOINT=ipdb.set_trace

# Create and set user
RUN useradd -mr -u $SYSTEM_USER_ID $SYSTEM_USER
USER $SYSTEM_USER

# Set the working directory
WORKDIR $PROJECT_ROOT

# Copy generated requirements.txt from the builder
COPY --from=builder /opt/requirements.txt $PROJECT_HOME
