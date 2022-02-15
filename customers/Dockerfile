# syntax=docker/dockerfile:1.2

# Builder image
FROM python:3.10-slim-bullseye as builder

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Create a virtual environment and activate it
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH=$VIRTUAL_ENV/bin:$PATH

# Copy file of project dependencies
COPY customers/requirements.in .

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
ENV VIRTUAL_ENV=/opt/venv
ENV PATH=$VIRTUAL_ENV/bin:$PATH
ENV SYSTEM_USER_ID=1000 SYSTEM_USER=micro_user SERVICE_NAME=customers
ENV PROJECT_HOME=/home/$SYSTEM_USER
ENV PROJECT_ROOT=$PROJECT_HOME/$SERVICE_NAME
ENV PROTOBUFS_ROOT=$PROJECT_HOME/protobufs
ENV PYTHONPATH=$PROTOBUFS_ROOT:$PROJECT_HOME:$PYTHONPATH PYTHONSTARTUP=$PROJECT_ROOT/.python_startup.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONBREAKPOINT=ipdb.set_trace

# Create and set user
RUN useradd -mr -u $SYSTEM_USER_ID $SYSTEM_USER
USER $SYSTEM_USER

# Set the working directory
WORKDIR $PROJECT_HOME

# Copy generated requirements.txt from the builder
COPY --from=builder --chown=$SYSTEM_USER_ID /opt/requirements.txt .

# Create gRPC files and certs
COPY --chown=$SYSTEM_USER_ID protobufs/auth.proto $PROTOBUFS_ROOT/auth.proto
COPY --chown=$SYSTEM_USER_ID ca.pem .
RUN --mount=type=secret,id=ca.key,uid=1000 \
    python3 -m grpc_tools.protoc -I $PROTOBUFS_ROOT --python_out=$PROTOBUFS_ROOT \
    --grpc_python_out=$PROTOBUFS_ROOT $PROTOBUFS_ROOT/auth.proto && \
    openssl req -nodes -newkey rsa:4096 -keyout server.key -out server.csr -subj /CN=$SERVICE_NAME && \
    openssl x509 -req -in server.csr -CA ca.pem -CAkey /run/secrets/ca.key -set_serial 1 -out server.pem
