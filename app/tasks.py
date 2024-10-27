import os
import redis

from celery import Celery

app = Celery('tasks', broker='redis://redis:6379')

@app.task
def generate_report_task(author: str, repo: str):
    r = redis.Redis(host='git-cloner-redis', port=6379, db=0, decode_responses=True)
    r.set(f'repo:{repo}', value='cloning')
    os.system(f'cd repos && git clone https://github.com/{author}/{repo}')
    r.delete(f'repo:{repo}')