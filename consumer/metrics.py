import prometheus_client as prom
from prometheus_client import Counter, Histogram, Gauge
import time

# Create metrics
MESSAGES_CONSUMED = Counter(
    'uniswap_consumer_messages_consumed_total', 
    'Number of messages consumed from Kafka',
    ['topic']
)

MESSAGES_PROCESSED = Counter(
    'uniswap_consumer_messages_processed_total', 
    'Number of messages successfully processed and stored',
    ['topic']
)

MAX_BLOCK_NUMBER = Gauge(
    'uniswap_consumer_max_block_number',
    'Maximum block number processed by the consumer',
    ['pool_address']
)

BATCH_SIZE = Histogram(
    'uniswap_consumer_batch_size',
    'Size of the message batch processed',
    ['topic']
)

PROCESSING_TIME = Histogram(
    'uniswap_consumer_processing_seconds',
    'Time spent processing a batch of messages',
    ['topic']
)

ERROR_COUNT = Counter(
    'uniswap_consumer_errors_total',
    'Number of errors encountered',
    ['error_type']
)

ACTIVE = Gauge(
    'uniswap_consumer_active',
    'Whether the consumer service is active'
)

# Start metrics server
def start_metrics_server(port=8002):
    """Start Prometheus metrics server on the specified port."""
    prom.start_http_server(port)
    print(f"Prometheus metrics server started on port {port}")

# Context manager for measuring batch processing time
class BatchProcessingTimer:
    def __init__(self, topic):
        self.topic = topic
        
    def __enter__(self):
        self.start_time = time.time()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        processing_time = time.time() - self.start_time
        PROCESSING_TIME.labels(topic=self.topic).observe(processing_time) 