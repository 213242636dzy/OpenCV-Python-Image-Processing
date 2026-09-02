"""可复用的实验秒表。"""

from __future__ import annotations

from PySide6.QtCore import QElapsedTimer, QObject, QTimer, Signal


class ExperimentClock(QObject):
    """从读取背景图开始计时，支持暂停、继续和清零。"""

    tick = Signal(int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._clock = QElapsedTimer()
        self._accumulated_ms = 0
        self._active = False
        self._display_timer = QTimer(self)
        self._display_timer.setInterval(100)
        self._display_timer.timeout.connect(lambda: self.tick.emit(self.elapsed_ms()))

    def start(self, reset: bool = True) -> None:
        if reset:
            self._accumulated_ms = 0
        self._clock.start()
        self._active = True
        self._display_timer.start()
        self.tick.emit(self.elapsed_ms())

    def pause(self) -> None:
        if self._active:
            self._accumulated_ms += self._clock.elapsed()
            self._active = False
            self._display_timer.stop()
            self.tick.emit(self.elapsed_ms())

    def resume(self) -> None:
        if not self._active:
            self._clock.start()
            self._active = True
            self._display_timer.start()

    def reset(self) -> None:
        self._accumulated_ms = 0
        if self._active:
            self._clock.restart()
        self.tick.emit(0)

    def elapsed_ms(self) -> int:
        return self._accumulated_ms + (self._clock.elapsed() if self._active else 0)

    @property
    def active(self) -> bool:
        return self._active
