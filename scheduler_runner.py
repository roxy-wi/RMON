"""Run the RMON scheduler as a single dedicated process."""

import os
import threading
import runtime_health
from apscheduler.executors.pool import ThreadPoolExecutor


os.environ['RMON_SCHEDULER_ENABLED'] = '1'

from app import scheduler  # noqa: E402


def main():
    if not scheduler.running:
        raise RuntimeError('The scheduler did not start')
    scheduler.scheduler.add_executor(ThreadPoolExecutor(1), alias='process-health')
    scheduler.add_job(id='process-health', func=runtime_health.pulse, args=['scheduler'],
                      trigger='interval', seconds=5, executor='process-health', max_instances=1, coalesce=True)
    runtime_health.pulse('scheduler')
    threading.Event().wait()


if __name__ == '__main__':
    main()
