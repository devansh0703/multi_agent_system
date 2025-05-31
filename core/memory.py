# File: /multi_agent_system/core/memory.py
import json
import redis
import time
import os
from typing import Dict, Any, Optional

class SharedMemory:
    def __init__(self, host='localhost', port=6379, db=0):
        try:
            self.redis_client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
            self.redis_client.ping()
            print(f"Connected to Redis successfully at {host}:{port}!")
        except redis.exceptions.ConnectionError as e:
            print(f"Could not connect to Redis at {host}:{port}: {e}")
            print("Falling back to in-memory dictionary.")
            self.redis_client = None
            self.in_memory_store = {}

    def _get_store(self):
        return self.redis_client if self.redis_client else self.in_memory_store

    def add_entry(self, process_id: str, key: str, data: Any):
        store = self._get_store()
        full_key = f"{process_id}:{key}"
        try:
            if self.redis_client:
                store.set(full_key, json.dumps(data))
            else:
                store[full_key] = json.dumps(data)
        except Exception as e:
            print(f"Error adding entry to memory ({key}): {e}")

    def get_entry(self, process_id: str, key: str) -> Optional[Dict[str, Any]]:
        store = self._get_store()
        full_key = f"{process_id}:{key}"
        try:
            val = store.get(full_key) if self.redis_client else store.get(full_key)
            return json.loads(val) if val else None
        except Exception as e:
            print(f"Error getting entry from memory ({key}): {e}")
            return None

    def update_entry(self, process_id: str, key: str, data: Any):
        self.add_entry(process_id, key, data)

    def get_all_entries_for_process(self, process_id: str) -> Dict[str, Any]:
        store = self._get_store()
        entries = {}
        if self.redis_client:
            keys = store.keys(f"{process_id}:*")
            for key in keys:
                clean_key = key.split(':', 1)[1] if ':' in key else key
                try:
                    entries[clean_key] = json.loads(store.get(key))
                except (json.JSONDecodeError, TypeError):
                    entries[clean_key] = store.get(key)
        else:
            for key, val in store.items():
                if key.startswith(f"{process_id}:"):
                    clean_key = key.split(':', 1)[1] if ':' in key else key
                    try:
                        entries[clean_key] = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        entries[clean_key] = val
        return entries