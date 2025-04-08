import logging
import traceback
from typing import Dict, Any, List
from sqlalchemy import create_engine, text
import datetime
import json

logger = logging.getLogger(__name__)

class DatabaseClient:
    """Client for interacting with TimescaleDB with dynamic schema support."""

    TYPE_MAPPINGS = {
        str: "TEXT",
        int: "BIGINT",
        float: "FLOAT",
        bool: "INTEGER",
        dict: "TEXT",
        list: "TEXT",
    }
    
    def __init__(self, database_url: str) -> None:
        """
        Initialize the database client.
        
        Args:
            database_url (str): Database connection URL
        """
        self.database_url = database_url
        self.engine = create_engine(database_url)
        
        # Track known tables and their schemas
        self.known_tables = {}
        
        logger.info(f"Connected to database at {database_url}")

    
    def _setup_timescale_for_table_with_connection(self, table_name: str, conn) -> None:
        """Set up a table as a TimescaleDB hypertable with an existing connection."""
        try:
            # Check if the table is already a hypertable
            result = conn.execute(text(
                f"SELECT * FROM timescaledb_information.hypertables WHERE hypertable_name = '{table_name}'"
            ))
            
            if not result.fetchone():
                # Get the information schema to verify column name
                column_check = conn.execute(text(
                    f"SELECT column_name FROM information_schema.columns "
                    f"WHERE table_name = '{table_name}' AND column_name = 'timestamp'"
                ))
                
                timestamp_column = column_check.fetchone()
                if timestamp_column:
                    # Convert the table to a hypertable using the verified column name
                    conn.execute(text(
                        f"SELECT create_hypertable('{table_name}', 'timestamp', if_not_exists => TRUE)"
                    ))
                    logger.info(f"Created TimescaleDB hypertable for {table_name}")
                else:
                    # Log detailed column information for debugging
                    all_columns = conn.execute(text(
                        f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}'"
                    ))
                    column_names = [row[0] for row in all_columns]
                    logger.error(f"Cannot create hypertable for {table_name}: 'timestamp' column not found. Available columns: {column_names}")
                    
                    # Ensure the timestamp column exists by adding it if missing
                    logger.info(f"Attempting to add missing timestamp column to {table_name}")
                    try:
                        conn.execute(text(
                            f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS timestamp TIMESTAMP"
                        ))
                        logger.info(f"Added timestamp column to {table_name}")
                        
                        # Now try creating the hypertable again
                        conn.execute(text(
                            f"SELECT create_hypertable('{table_name}', 'timestamp', if_not_exists => TRUE)"
                        ))
                        logger.info(f"Created TimescaleDB hypertable for {table_name} after adding timestamp column")
                    except Exception as add_column_error:
                        logger.error(f"Failed to add timestamp column to {table_name}: {add_column_error}")
        except Exception as e:
            logger.error(f"Error setting up TimescaleDB hypertable: {e}")
            logger.error(traceback.format_exc())
            raise e
    
    def save_event_batch(self, event_type: str, event_data_batch: List[Dict[str, Any]]) -> bool:
        """
        Save a batch of events to the database.
        """
        if not event_data_batch:
            return True
        
        try:
            # Step 1: Get table info - use lowercase table name
            table_name = f"{event_type.lower()}"
            if table_name not in self.known_tables:
                # Check if table exists in database
                with self.engine.begin() as conn:
                    table_check = conn.execute(text(
                        f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table_name}')"
                    ))
                    if table_check.scalar():
                        # Get table columns
                        columns_query = conn.execute(text(
                            f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}'"
                        ))
                        columns = [row[0] for row in columns_query]
                        self.known_tables[table_name] = columns
                    else:
                        logger.error(f"Table {table_name} does not exist. Tables should be created from ABI at startup.")
                        return False
            
            table_columns = self.known_tables[table_name]
            

            rows = []
            for event_data in event_data_batch:
                row = {}
                
                for key, value in event_data.items():
                    snake_key = ''.join(['_' + c.lower() if c.isupper() else c for c in key]).lstrip('_')
                    if key == 'poolAddress':
                        row['pool_address'] = value
                    elif key == 'transactionHash':
                        row['transaction_hash'] = value
                    elif key == 'blockNumber':
                        row['block_number'] = value
                    elif key == 'poolName':
                        row['pool_name'] = value
                    # Special handling for timestamp
                    elif key == 'timestamp':
                        row['timestamp'] = datetime.datetime.fromtimestamp(value)
                    elif isinstance(value, (dict, list)):
                        row[snake_key] = json.dumps(value)
                    else:
                        # Convert numeric values to strings if they're large
                        if isinstance(value, (int, float)) and abs(value) > 2**53:
                            row[snake_key] = str(value)
                        else:
                            row[snake_key] = value
                
                # Filter the row to include only columns that exist in the table
                filtered_row = {k: v for k, v in row.items() if k in table_columns}
                
                rows.append(filtered_row)
            

            with self.engine.begin() as conn:
                for row in rows:
                    if not row:
                        logger.warning(f"Skipping empty row for {event_type}")
                        continue
                    
                    columns_str = ", ".join(row.keys())
                    placeholders = ", ".join([f":{k}" for k in row.keys()])
                    insert_sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
                    conn.execute(text(insert_sql), row)
            
            logger.info(f"Saved batch of {len(rows)} {event_type} events")
            return True
            
        except Exception as e:
            logger.error(f"Error saving batch of {event_type} events: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def create_tables_from_abi(self, abi_data: List[Dict[str, Any]]) -> None:
        """
        Create tables based on event definitions in the ABI.
        """
        logger.info("Creating tables from ABI definitions")
        
        for item in abi_data:
            if item.get('type') == 'event':
                event_name = item.get('name')
                if not event_name:
                    continue
                    
                # Use lowercase table name
                table_name = event_name.lower()
                logger.info(f"Creating table for event: {event_name} (table: {table_name})")

                if table_name in self.known_tables:
                    logger.info(f"Table {table_name} already exists in known tables, skipping")
                    continue
                
                column_defs = [
                    "id SERIAL",
                    "transaction_hash TEXT",
                    "block_number BIGINT",
                    "pool_address TEXT",
                    "timestamp TIMESTAMP NOT NULL",
                    "pool_name TEXT"
                ]
                
                inputs = item.get('inputs', [])
                for input_def in inputs:
                    name = input_def.get('name')
                    type_str = input_def.get('type')
                    
                    # Convert to snake_case
                    snake_name = ''.join(['_' + c.lower() if c.isupper() else c for c in name]).lstrip('_')
                    
                    sql_type = "TEXT"  # Default to TEXT
                    if type_str:
                        if type_str.startswith('uint') or type_str.startswith('int'):
                            sql_type = "TEXT"
                        elif type_str == 'bool':
                            sql_type = "INTEGER"
                        elif type_str == 'address':
                            sql_type = "TEXT"

                    column_defs.append(f"{snake_name} {sql_type}")
                
                # Add composite primary key including timestamp
                column_defs.append("PRIMARY KEY (id, timestamp)")

                create_table_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(column_defs)})"
                
                with self.engine.begin() as conn:
                    conn.execute(text(create_table_sql))
                    
                    column_check = conn.execute(text(
                        f"SELECT column_name FROM information_schema.columns "
                        f"WHERE table_name = '{table_name}' AND column_name = 'timestamp'"
                    ))
                    if column_check.fetchone():
                        logger.info(f"Timestamp column confirmed in table {table_name}")
                    else:
                        logger.warning(f"Timestamp column not found in {table_name} after creation!")
                    
                    # Setup as TimescaleDB hypertable
                    self._setup_timescale_for_table_with_connection(table_name, conn)
                
                # Get the actual columns to store in known_tables
                with self.engine.begin() as conn:
                    columns_query = conn.execute(text(
                        f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}'"
                    ))
                    columns = [row[0] for row in columns_query]
                    self.known_tables[table_name] = columns
                
                logger.info(f"Created table {table_name} with {len(column_defs)} columns")
    
    def close(self) -> None:
        """Close database connections."""
        if hasattr(self, 'engine'):
            self.engine.dispose()
            logger.info("Database connections closed") 