from PyQt5.QtCore import QObject, pyqtSignal

from engine.myhkw_api import MyHKWSearchWorker
from models.song import Song


class SearchEngine(QObject):
    result_found = pyqtSignal(Song)
    search_progress = pyqtSignal(str)
    search_finished = pyqtSignal()
    search_error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: MyHKWSearchWorker | None = None

    def search(self, query: str, max_results: int = 30):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait()
        self._worker = MyHKWSearchWorker(query, max_results)
        self._worker.result_found.connect(self.result_found)
        self._worker.progress_text.connect(self.search_progress)
        self._worker.finished.connect(self.search_finished)
        self._worker.search_error.connect(self.search_error)
        self._worker.start()

    def cancel(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait()
