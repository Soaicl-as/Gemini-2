import logging
import queue
import threading

# Configure basic logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Use a thread-safe queue to store logs
log_queue = queue.Queue()

class QueueHandler(logging.Handler):
    """A logging handler that puts logs into a queue."""
    def emit(self, record):
        log_queue.put(self.format(record))

# Add the custom handler to the root logger
root_logger = logging.getLogger()
root_logger.addHandler(QueueHandler())

def get_logs():
    """Retrieves all logs currently in the queue."""
    logs = []
    while not log_queue.empty():
        try:
            logs.append(log_queue.get_nowait())
        except queue.Empty:
            break
    return logs

def log_message(level, message):
    """Logs a message with a specific level."""
    if level.lower() == 'info':
        logging.info(message)
    elif level.lower() == 'warning':
        logging.warning(message)
    elif level.lower() == 'error':
        logging.error(message)
    elif level.lower() == 'debug':
        logging.debug(message)
    else:
        logging.info(f"Unknown log level '{level}': {message}")

