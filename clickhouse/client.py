import os
import clickhouse_connect


class LazyClickHouseClient:
    """Lazy wrapper for ClickHouse client that connects only when first used."""
    
    def __init__(self):
        self._client = None
    
    def _get_client(self):
        """Get or create the ClickHouse client connection."""
        if self._client is None:
            self._client = clickhouse_connect.get_client(
                host=os.getenv('CLICKHOUSE_HOST', 'localhost'),
                port=int(os.getenv('CLICKHOUSE_PORT', 8123)),
                username=os.getenv('CLICKHOUSE_USER', 'default'),
                password=os.getenv('CLICKHOUSE_PASSWORD', ''),
                database=os.getenv('CLICKHOUSE_DATABASE', 'default'),
            )
        return self._client
    
    def __getattr__(self, name):
        """Proxy attribute access to the underlying client."""
        return getattr(self._get_client(), name)


client = LazyClickHouseClient()