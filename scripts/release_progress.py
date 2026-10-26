"""Keep long release operations visible, including cached/offline work."""
from contextlib import contextmanager
from threading import Event, Thread
from time import monotonic


@contextmanager
def progress(label, *, interval=5, emit=None):
    """Report the active operation; elapsed time is not a completion estimate."""
    if interval <= 0:
        raise ValueError('Progress interval must be positive.')
    if emit is None:
        emit = lambda message: print(message, flush=True)
    started = monotonic()
    stopped = Event()
    emit(f'{label}...')

    def heartbeat():
        while not stopped.wait(interval):
            emit(f'  Still working: {label} ({monotonic() - started:.0f}s elapsed)')

    worker = Thread(target=heartbeat, name='release-progress', daemon=True)
    worker.start()
    outcome = 'Done'
    try:
        yield
    except BaseException:
        outcome = 'Stopped'
        raise
    finally:
        stopped.set()
        worker.join()
        emit(f'{outcome}: {label} ({monotonic() - started:.1f}s)')
