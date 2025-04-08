import prometheus_client as prom
from prometheus_client import Counter, Histogram, Gauge
import time

# Create metrics
MESSAGES_POLLED = Counter(
    'uniswap_listener_messages_polled_total', 
    'Number of messages polled from the blockchain',
    ['pool_address', 'pool_name']
)

MESSAGES_PRODUCED = Counter(
    'uniswap_listener_messages_produced_total', 
    'Number of messages produced to Kafka',
    ['pool_address', 'pool_name']
)

MESSAGES_BY_TOPIC = Counter(
    'uniswap_listener_messages_by_topic_total', 
    'Number of messages produced to Kafka by topic',
    ['topic', 'pool_address', 'pool_name']
)

EVENT_PROCESSING_TIME = Histogram(
    'uniswap_listener_event_processing_seconds',
    'Time spent processing an event',
    ['event_type']
)

ERROR_COUNT = Counter(
    'uniswap_listener_errors_total',
    'Number of errors encountered',
    ['error_type']
)

# Start metrics server
def start_metrics_server(port=8001):
    """Start Prometheus metrics server on the specified port."""
    prom.start_http_server(port)
    print(f"Prometheus metrics server started on port {port}")

# Context manager for measuring event processing time
class EventProcessingTimer:
    def __init__(self, event_type):
        self.event_type = event_type
        
    def __enter__(self):
        self.start_time = time.time()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        processing_time = time.time() - self.start_time
        EVENT_PROCESSING_TIME.labels(event_type=self.event_type).observe(processing_time) 