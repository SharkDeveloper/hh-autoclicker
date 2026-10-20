"""
Kafka consumer для worker-сервиса.
Читает задачи из топика apply-jobs, запускает autoclicker, публикует результаты.
"""
import json
import logging
import os
import re
import sys
from datetime import datetime
from typing import Dict, Any, List

from kafka import KafkaConsumer, KafkaProducer
from cryptography.fernet import Fernet

# Добавляем директорию worker в sys.path для импорта модулей
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logger import get_module_logger
