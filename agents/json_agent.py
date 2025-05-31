# File: /multi_agent_system/agents/json_agent.py
import json
from pydantic import ValidationError
from typing import Dict, Any
# REMOVED: from core.memory import memory
# REMOVED: from core.action_router import action_router
from agents.models import WebhookData, JsonProcessingResult
from dotenv import load_dotenv

class JsonAgent:
    def __init__(self, memory_instance, action_router_instance): # ADDED memory_instance
        self.memory = memory_instance # Store the memory instance
        self.action_router = action_router_instance # Store the action router instance

    def process(self, process_id: str, json_content: str) -> JsonProcessingResult:
        self.memory.add_entry(process_id, "json_agent_input", {"content": json_content[:200] + "..." if len(json_content) > 200 else json_content}) # Changed: Use self.memory
        
        parsed_data = None
        is_valid_schema = True
        anomalies = []

        try:
            data = json.loads(json_content)
            parsed_data = data
        except json.JSONDecodeError as e:
            is_valid_schema = False
            anomalies.append(f"JSON Decode Error: {e}")
            print(f"JSON Agent: JSON decoding failed: {e}")
            result = JsonProcessingResult(is_valid_schema=is_valid_schema, anomalies=anomalies, parsed_data=None)
            self.memory.add_entry(process_id, "json_agent_output", result.model_dump()) # Changed: Use self.memory
            self.action_router.trigger_anomaly_alert(process_id, {"reason": "JSON_Decode_Error", "details": str(e)})
            return result

        try:
            webhook_event = WebhookData(**data)
            parsed_data = webhook_event.model_dump()
            print("JSON Agent: Data successfully validated against WebhookData schema.")

            if webhook_event.event_type not in ["order_created", "user_signed_up", "payment_failed"]:
                anomalies.append(f"Unexpected event_type: {webhook_event.event_type}")
                is_valid_schema = False
            if not webhook_event.timestamp:
                anomalies.append("Timestamp field is missing or empty.")
                is_valid_schema = False

        except ValidationError as e:
            is_valid_schema = False
            anomalies.append(f"Schema Validation Error: {e}")
            print(f"JSON Agent: Schema validation failed: {e}")
        except Exception as e:
            is_valid_schema = False
            anomalies.append(f"Unexpected error during schema validation: {e}")
            print(f"JSON Agent: Unexpected error: {e}")

        result = JsonProcessingResult(is_valid_schema=is_valid_schema, anomalies=anomalies, parsed_data=parsed_data)
        self.memory.add_entry(process_id, "json_agent_output", result.model_dump()) # Changed: Use self.memory

        if not is_valid_schema:
            self.action_router.trigger_anomaly_alert(process_id, {"reason": "JSON_Schema_Mismatch", "anomalies": anomalies, "data_preview": json_content[:200]})
        else:
            self.action_router.trigger_logging_and_close(process_id, {"message": "JSON processed successfully", "data": parsed_data})

        return result