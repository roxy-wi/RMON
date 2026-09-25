"""Run the durable agent-operation worker outside the web process."""
import os

os.environ['RMON_SCHEDULER_ENABLED'] = '0'

from app.modules.operations.worker import main  # noqa: E402

if __name__ == '__main__':
    main()
