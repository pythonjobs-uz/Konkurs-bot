from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi import FastAPI, Response
import time

message_counter = Counter('bot_messages_total', 'Total messages processed', ['type'])
contest_counter = Counter('contests_total', 'Total contests created', ['status'])
user_counter = Counter('users_total', 'Total users', ['action'])
response_time = Histogram('bot_response_time_seconds', 'Response time')
active_users = Gauge('active_users', 'Currently active users')

def setup_metrics(app: FastAPI):
    @app.get("/metrics")
    async def metrics():
        return Response(generate_latest(), media_type="text/plain")

class MetricsCollector:
    @staticmethod
    def record_message(message_type: str):
        message_counter.labels(type=message_type).inc()
    
    @staticmethod
    def record_contest(status: str):
        contest_counter.labels(status=status).inc()
    
    @staticmethod
    def record_user_action(action: str):
        user_counter.labels(action=action).inc()
    
    @staticmethod
    def record_response_time(duration: float):
        response_time.observe(duration)
    
    @staticmethod
    def set_active_users(count: int):
        active_users.set(count)

metrics = MetricsCollector()
