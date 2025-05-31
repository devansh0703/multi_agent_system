# File: /multi_agent_system/core/action_router.py
import time
from typing import Dict, Any

class ActionRouter:
    def __init__(self, memory_instance): # Now requires memory_instance to be passed
        self.memory = memory_instance

    def _simulate_api_call(self, process_id: str, action_type: str, payload: Dict[str, Any]):
        print(f"ActionRouter: Simulating {action_type} call with payload: {payload}")
        time.sleep(0.1)
        result = {"status": "success", "message": f"{action_type} triggered successfully"}
        self.memory.add_entry(process_id, f"action_triggered:{action_type}", {"payload": payload, "result": result})
        return result

    def trigger_crm_escalation(self, process_id: str, issue_details: Dict[str, Any]):
        return self._simulate_api_call(process_id, "CRM_Escalation", issue_details)

    def trigger_risk_alert(self, process_id: str, risk_details: Dict[str, Any]):
        return self._simulate_api_call(process_id, "Risk_Alert", risk_details)

    def trigger_compliance_flag(self, process_id: str, compliance_details: Dict[str, Any]):
        return self._simulate_api_call(process_id, "Compliance_Flag", compliance_details)

    def trigger_summary_generation(self, process_id: str, summary_data: Dict[str, Any]):
        return self._simulate_api_call(process_id, "Summary_Generation", summary_data)

    def trigger_logging_and_close(self, process_id: str, log_data: Dict[str, Any]):
        return self._simulate_api_call(process_id, "Log_and_Close", log_data)

    def trigger_anomaly_alert(self, process_id: str, anomaly_details: Dict[str, Any]):
        return self._simulate_api_call(process_id, "Anomaly_Alert", anomaly_details)