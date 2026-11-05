
import os
import logging
import multiprocessing
import signal
import time
import uuid

from redis import Redis
from rq import Queue, Worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL")
WORKER_PROCESSES = int(os.getenv("WORKER_PROCESSES", "2"))

if not REDIS_URL:
    raise RuntimeError("REDIS_URL is missing")

if WORKER_PROCESSES < 1:
    raise ValueError("WORKER_PROCESSES must be at least 1")


def run_worker(index):
    connection = Redis.from_url(
        REDIS_URL,
        socket_connect_timeout=10,
        socket_timeout=10,
        health_check_interval=30,
    )

    connection.ping()

    queue = Queue(
        "telegram",
        connection=connection,
    )

    worker = Worker(
        [queue],
        connection=connection,
        name=f"telegram-worker-{index}-{uuid.uuid4().hex[:6]}",
    )

    logger.info("Worker %s starting", index)

    # Only one worker runs the RQ scheduler for delayed retries.
    worker.work(with_scheduler=(index == 1))


def main():
    processes = []

    try:
        for index in range(1, WORKER_PROCESSES + 1):
            process = multiprocessing.Process(
                target=run_worker,
                args=(index,),
                name=f"telegram-worker-{index}",
            )

            process.start()
            processes.append(process)

        logger.info(
            "Started %s Telegram worker processes",
            WORKER_PROCESSES,
        )

        while True:
            for process in processes:
                if not process.is_alive():
                    raise RuntimeError(
                        f"{process.name} stopped unexpectedly"
                    )
            time.sleep(5)

    except KeyboardInterrupt:
        logger.info("Worker shutdown requested")
        print("Worker shutdown requested")

    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()

        for process in processes:
            process.join(timeout=10)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
