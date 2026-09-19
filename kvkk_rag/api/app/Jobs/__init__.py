# Arka plan isleri. Kuyruk altyapisi yok; FastAPI BackgroundTasks ile yanit
# dondukten sonra ayni surecte calisir. Job.dispatch(background) / Job.handle().
from .base import Job

__all__ = ["Job"]
