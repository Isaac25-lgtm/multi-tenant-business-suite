import os


bind = f"0.0.0.0:{os.getenv('PORT', '10000')}"
workers = max(1, int(os.getenv('WEB_CONCURRENCY', '2')))
threads = max(1, int(os.getenv('GUNICORN_THREADS', '2')))
worker_class = os.getenv('GUNICORN_WORKER_CLASS', 'gthread')
timeout = int(os.getenv('GUNICORN_TIMEOUT', '120'))
graceful_timeout = int(os.getenv('GUNICORN_GRACEFUL_TIMEOUT', '30'))
keepalive = int(os.getenv('GUNICORN_KEEPALIVE', '5'))
max_requests = int(os.getenv('GUNICORN_MAX_REQUESTS', '1000'))
max_requests_jitter = int(os.getenv('GUNICORN_MAX_REQUESTS_JITTER', '100'))
worker_tmp_dir = os.getenv('GUNICORN_WORKER_TMP_DIR', '/tmp')
preload_app = os.getenv('GUNICORN_PRELOAD', '1').strip().lower() in {'1', 'true', 'yes', 'on'}
accesslog = '-'
errorlog = '-'
capture_output = True
loglevel = os.getenv('GUNICORN_LOG_LEVEL', 'info')
