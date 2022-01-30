# Builder image
FROM python:3.10-slim-bullseye as builder

# Install required libs
RUN apt-get update && apt-get install -y --no-install-recommends --no-install-suggests \
    python3-dev \
    libpq-dev \
    gcc \
    && apt-get remove --purge --autoremove -y \
    && apt-get clean autoclean \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Create a virtual environment and activate it
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH=$VIRTUAL_ENV/bin:$PATH

# Copy file of project dependencies
COPY requirements.in .

# Compile and install any needed packages specified in requirements.in
# ToDo: Check for fixes for compatibility between pip-tools and pip 22.0 version
# pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir pip==21.3.1 && \
    pip install --no-cache-dir pip-tools && \
    pip-compile --quiet --output-file=/opt/requirements.txt && \
    pip-sync /opt/requirements.txt --pip-args '--no-cache-dir'

# Final image
FROM python:3.10-slim-bullseye

# Install required libs
RUN apt-get update && apt-get install -y --no-install-recommends --no-install-suggests \
    libpq-dev \
    && apt-get remove --purge --autoremove -y \
    && apt-get clean autoclean \
    && rm -rf /var/lib/apt/lists/*

# Copy the virtual environment from the previous image
COPY --from=builder /opt/venv /opt/venv

# Activate the virtual environment and set the envs
ENV VIRTUAL_ENV=/opt/venv
ENV PATH=$VIRTUAL_ENV/bin:$PATH
ENV SYSTEM_USER_ID=1000 SYSTEM_USER=micro_user SERVICE_NAME=customers
ENV PROJECT_HOME=/home/$SYSTEM_USER
ENV PROJECT_ROOT=$PROJECT_HOME/$SERVICE_NAME
ENV PYTHONPATH=$PROJECT_HOME:$PYTHONPATH PYTHONSTARTUP=$PROJECT_ROOT/.python_startup.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONBREAKPOINT=ipdb.set_trace

# Create and set user
RUN useradd -mr -u $SYSTEM_USER_ID $SYSTEM_USER
USER $SYSTEM_USER

# Set the working directory
WORKDIR $PROJECT_ROOT

# Copy generated requirements.txt from the builder
COPY --from=builder /opt/requirements.txt $PROJECT_HOME
