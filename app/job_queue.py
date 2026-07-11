from collections import deque
from dataclasses import dataclass
from uuid import uuid4

from PySide6.QtCore import QObject, Signal


@dataclass
class QueuedJob:
    id: str
    scope: str
    title: str
    worker: object
    result_signal: str
    on_result: object
    on_started: object = None
    on_finished: object = None
    on_rejected: object = None


class JobQueue(QObject):
    job_started = Signal(str, str)
    job_finished = Signal(str, str)
    job_rejected = Signal(str, str)
    status_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self._active = None
        self._pending = deque()
        self._scopes = set()

    def is_busy(self):
        return self._active is not None

    def has_scope(self, scope):
        return scope in self._scopes

    def submit(
        self,
        *,
        scope,
        title,
        worker,
        result_signal,
        on_result,
        on_started=None,
        on_finished=None,
        on_rejected=None,
    ):
        if scope in self._scopes:
            message = f"{title} is already running or queued."
            if on_rejected:
                on_rejected(message)
            self.job_rejected.emit(scope, message)
            self.status_changed.emit(message)
            return ""

        job = QueuedJob(
            id=str(uuid4()),
            scope=scope,
            title=title,
            worker=worker,
            result_signal=result_signal,
            on_result=on_result,
            on_started=on_started,
            on_finished=on_finished,
            on_rejected=on_rejected,
        )
        self._pending.append(job)
        self._scopes.add(scope)
        self._start_next()
        return job.id

    def _start_next(self):
        if self._active is not None or not self._pending:
            return
        job = self._pending.popleft()
        self._active = job

        signal = getattr(job.worker, job.result_signal)
        signal.connect(lambda *args, job_id=job.id: self._handle_result(job_id, *args))
        job.worker.finished.connect(lambda job_id=job.id: self._handle_finished(job_id))
        job.worker.finished.connect(job.worker.deleteLater)

        if job.on_started:
            job.on_started()
        self.job_started.emit(job.scope, job.title)
        self.status_changed.emit(job.title)
        job.worker.start()

    def _handle_result(self, job_id, *args):
        if self._active is None or self._active.id != job_id:
            return
        self._active.on_result(*args)

    def _handle_finished(self, job_id):
        if self._active is None or self._active.id != job_id:
            return
        job = self._active
        self._active = None
        self._scopes.discard(job.scope)
        if job.on_finished:
            job.on_finished()
        self.job_finished.emit(job.scope, job.title)
        self.status_changed.emit("Ready")
        self._start_next()


_JOB_QUEUE = None


def get_job_queue():
    global _JOB_QUEUE
    if _JOB_QUEUE is None:
        _JOB_QUEUE = JobQueue()
    return _JOB_QUEUE
