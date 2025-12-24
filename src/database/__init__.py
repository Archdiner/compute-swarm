"""
Database integration layer for ComputeSwarm
"""

from src.database.client import DatabaseClient, get_db_client

__all__ = ["DatabaseClient", "get_db_client"]
