from unittest.mock import MagicMock

from app.job_queue import JobQueue


class FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, *args):
        for callback in list(self.callbacks):
            callback(*args)


class FakeWorker:
    def __init__(self):
        self.finished_with_result = FakeSignal()
        self.finished = FakeSignal()
        self.started = False
        self.deleted = False

    def start(self):
        self.started = True

    def deleteLater(self):
        self.deleted = True


def test_job_queue_starts_first_job_and_rejects_duplicate_scope():
    queue = JobQueue()
    first = FakeWorker()
    second = FakeWorker()
    rejected = []

    job_id = queue.submit(
        scope="cleanup",
        title="Scan cleanup",
        worker=first,
        result_signal="finished_with_result",
        on_result=MagicMock(),
    )
    duplicate_id = queue.submit(
        scope="cleanup",
        title="Scan cleanup again",
        worker=second,
        result_signal="finished_with_result",
        on_result=MagicMock(),
        on_rejected=rejected.append,
    )

    assert job_id
    assert duplicate_id == ""
    assert first.started is True
    assert second.started is False
    assert rejected == ["Scan cleanup again is already running or queued."]


def test_job_queue_serializes_different_scopes_and_ignores_stale_results():
    queue = JobQueue()
    first = FakeWorker()
    second = FakeWorker()
    first_result = MagicMock()
    second_result = MagicMock()

    queue.submit(
        scope="cleanup",
        title="Scan cleanup",
        worker=first,
        result_signal="finished_with_result",
        on_result=first_result,
    )
    queue.submit(
        scope="display",
        title="Load display",
        worker=second,
        result_signal="finished_with_result",
        on_result=second_result,
    )

    assert first.started is True
    assert second.started is False

    second.finished_with_result.emit("too early")
    second_result.assert_not_called()

    first.finished_with_result.emit("done")
    first.finished.emit()

    first_result.assert_called_once_with("done")
    assert second.started is True

    second.finished_with_result.emit("loaded")
    second.finished.emit()
    second_result.assert_called_once_with("loaded")
