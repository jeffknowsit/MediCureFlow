# Gunicorn Configuration for MediCureFlow
# Production-ready WSGI server configuration

import multiprocessing
import os

# Server socket
bind = "127.0.0.1:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gevent"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 5

# Restart workers after this many requests, to help prevent memory leaks
restart_worker_after_requests = 10000

# Logging
access_log = "logs/gunicorn_access.log"
error_log = "logs/gunicorn_error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "MediCureFlow"

# Daemonize the Gunicorn process (detach & enter background)
daemon = False

# The Path to a pid file
pidfile = "logs/gunicorn.pid"

# User and group to run as
# user = "www-data"
# group = "www-data"

# Directory to change to when running
# chdir = "/path/to/MediCureFlow"

# Preload application code before worker processes are forked
preload_app = True

# Restart workers gracefully on SIGUSR2
restart_on_reload = True

# Environment
raw_env = [
    "DJANGO_SETTINGS_MODULE=MediCureFlow.settings.production",
]

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# SSL (if terminating SSL at Gunicorn level)
# keyfile = "/path/to/ssl/private.key"
# certfile = "/path/to/ssl/certificate.crt"
# ssl_version = ssl.PROTOCOL_TLSv1_2

# Debugging (for development only)
# reload = True
# reload_extra_files = ["templates/", "static/"]

def when_ready(server):
    """Called just after the server is started."""
    server.log.info("MediCureFlow server is ready. Listening on %s", server.address)

def worker_int(worker):
    """Called just after a worker has been killed by SIGINT."""
    worker.log.info("worker received INT or QUIT signal")

def pre_fork(server, worker):
    """Called just prior to forking the worker subprocess."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def worker_abort(worker):
    """Called when a worker receives the SIGABRT signal."""
    worker.log.info("worker received SIGABRT signal")
