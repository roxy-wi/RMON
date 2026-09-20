import logging
import random
import signal
import threading
import time

import runtime_health
from app import app
from app.modules.db.db_model import conn
from app.modules.operations import queue

logger = logging.getLogger(__name__)


class LeaseGuard:
    """Cancel Ansible before a lease expires, even if the renewal query hangs."""
    def __init__(self):
        self.lost = False
        self.renewed()

    def renewed(self):
        self.deadline = time.monotonic() + queue.LEASE_SECONDS - 60

    def cancelled(self):
        return self.lost or time.monotonic() >= self.deadline


class Worker:
    def __init__(self):
        self.stop_event = threading.Event()
        self.idle_delay = 2.0
        self.error_delay = 5.0
        self.next_recovery = 0.0
        self.next_artifact_cleanup = 0.0

    def stop(self, *_):
        self.stop_event.set()

    def wait(self, seconds, ready=True):
        deadline = time.monotonic() + seconds
        while not self.stop_event.is_set():
            runtime_health.pulse('operations', ready=ready)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            self.stop_event.wait(min(5, remaining))

    def execute(self, task_id, owner):
        guard = LeaseGuard()
        done = threading.Event()
        result = {}

        def run():
            try:
                with app.app_context():
                    payload = queue.load_payload(task_id, owner)
                    from app.modules.service.installation import execute_installation
                    execute_installation(payload['inventory'], payload['server_ips'], payload['role'],
                                         cancel_callback=guard.cancelled)
                    result['inventory'] = payload['inventory']
            except Exception as error:
                logger.error('Agent operation %s failed (%s)', task_id, type(error).__name__)
                result['error'] = 'Agent operation failed. Check SSH access and the operations service logs.'
            finally:
                try:
                    conn.close()
                finally:
                    done.set()

        thread = threading.Thread(target=run, name=f'agent-operation-{task_id}', daemon=False)
        thread.start()
        next_renew = time.monotonic() + 30
        lost = False
        while not done.wait(5):
            runtime_health.pulse('operations', ready=not lost and not self.stop_event.is_set())
            if not lost and time.monotonic() >= next_renew:
                try:
                    lost = not queue.renew(task_id, owner)
                except Exception as error:
                    logger.error('Cannot renew operation %s (%s); cancelling execution', task_id, type(error).__name__)
                    lost = True
                finally:
                    conn.close()
                if lost:
                    guard.lost = True
                else:
                    guard.renewed()
                next_renew = time.monotonic() + 30
        thread.join()
        if lost or guard.cancelled():
            logger.warning('Operation %s lost its lease; completion was not recorded', task_id)
            return
        from app.modules.common.agent_transport import record_applied
        if not queue.finish(task_id, owner, result.get('error'),
                            on_success=lambda: record_applied(result['inventory'])):
            logger.warning('Operation %s completion rejected after lease expiry', task_id)

    def step(self):
        try:
            if time.monotonic() >= self.next_recovery:
                queue.recover_expired()
                self.next_recovery = time.monotonic() + 60
            claimed = queue.claim()
            runtime_health.pulse('operations', ready=not self.stop_event.is_set())
            if claimed:
                self.execute(*claimed)
                self.idle_delay = 2.0
            elif time.monotonic() >= self.next_artifact_cleanup:
                # Each operations container owns its Ansible files; the separate
                # scheduler cannot clean files in this container's filesystem.
                from app.jobs import delete_ansible_artifacts
                delete_ansible_artifacts()
                self.next_artifact_cleanup = time.monotonic() + 86400
            self.error_delay = 5.0
            return bool(claimed)
        finally:
            conn.close()

    def run(self):
        with app.app_context():
            while not self.stop_event.is_set():
                try:
                    if self.step():
                        continue
                except Exception as error:
                    logger.error('Operations service unavailable (%s); retrying in %.0fs',
                                 type(error).__name__, self.error_delay)
                    self.wait(self.error_delay, ready=False)
                    self.error_delay = min(300, self.error_delay * 2)
                    continue
                self.wait(min(30, self.idle_delay * random.uniform(1, 1.15)))
                self.idle_delay = min(30, self.idle_delay * 2)
        runtime_health.pulse('operations', ready=False)


def main():
    worker = Worker()
    signal.signal(signal.SIGTERM, worker.stop)
    signal.signal(signal.SIGINT, worker.stop)
    worker.run()
