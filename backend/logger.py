import logging, os
from datetime import datetime

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            f"logs/system_{datetime.now().strftime('%Y%m%d')}.log",
            encoding="utf-8"
        ),
    ]
)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
