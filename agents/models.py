# File: /multi_agent_system/agents/models.py
from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any

# --- Classifier Agent Models ---
class ClassificationResult(BaseModel):
    format: Literal["Email", "JSON", "PDF", "Unknown"] = Field(
        ..., description="Detected format of the input content."
    )
    intent: Literal["RFQ", "Complaint", "Invoice", "Regulation", "Fraud Risk", "Unknown"] = Field(
        ..., description="Detected business intent of the input content."
    )
    confidence: Optional[float] = Field(None, description="Confidence score of the classification.")

# --- Email Agent Models ---
class EmailContent(BaseModel):
    sender: str = Field(..., description="Email sender's address or name.")
    urgency: Literal["High", "Medium", "Low", "Unknown"] = Field(
        ..., description="Urgency level of the email content."
    )
    issue_request: str = Field(..., description="Summary of the main issue or request in the email.")
    tone: Literal["Escalation", "Polite", "Threatening", "Neutral", "Unknown"] = Field(
        ..., description="Identified tone of the email."
    )

# --- JSON Agent Models ---
class WebhookData(BaseModel):
    event_type: str = Field(..., description="Type of the webhook event (e.g., 'order_created', 'user_signed_up').")
    timestamp: str = Field(..., description="Timestamp of the event in ISO format.")
    data: Dict[str, Any] = Field(..., description="Payload data of the webhook event.")
    source_app: Optional[str] = Field(None, description="The application that sent the webhook.")

class JsonProcessingResult(BaseModel):
    is_valid_schema: bool = Field(..., description="True if the JSON validates against the expected schema.")
    anomalies: List[str] = Field(..., description="List of detected anomalies or schema validation errors.")
    parsed_data: Optional[Dict[str, Any]] = Field(None, description="The parsed JSON data if valid.")

# --- PDF Agent Models ---
class InvoiceLineItem(BaseModel):
    description: str
    quantity: int
    unit_price: float
    total: float

class InvoiceData(BaseModel):
    invoice_number: str
    date: str
    total_amount: float
    currency: str
    line_items: List[InvoiceLineItem]

class PolicyData(BaseModel):
    policy_title: str
    policy_id: str
    keywords_found: List[str]
    summary: str

class PdfProcessingResult(BaseModel):
    document_type: Literal["Invoice", "Policy", "Other"] = Field(
        ..., description="Type of document identified in the PDF."
    )
    invoice_data: Optional[InvoiceData] = Field(None, description="Extracted invoice details if applicable.")
    policy_data: Optional[PolicyData] = Field(None, description="Extracted policy details if applicable.")
    flags: List[str] = Field(..., description="List of flags (e.g., 'Invoice_HighValue', 'Compliance_GDPR').")