class WorkerRunState:
    """Track one active QThread-style worker and reject duplicate starts.

    Qt signals can arrive after a newer worker has started or after a widget has
    moved on. Callers keep the returned token and ignore results that no longer
    belong to the active worker.
    """

    def __init__(self):
        self._worker = None
        self._token = 0

    @property
    def worker(self):
        return self._worker

    def is_running(self):
        if self._worker is None:
            return False
        try:
            return self._worker.isRunning()
        except RuntimeError:
            self._worker = None
            return False

    def begin(self, worker):
        if self.is_running():
            return None
        self._token += 1
        self._worker = worker
        return self._token

    def owns(self, token):
        return self._worker is not None and token == self._token

    def finish(self, token):
        if not self.owns(token):
            return False
        self._worker = None
        return True

    def clear_if_current(self, token):
        if self.owns(token):
            self._worker = None
