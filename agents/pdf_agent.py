# File: /multi_agent_system/agents/pdf_agent.py
import io
import json
import PyPDF2
from typing import List, Union, Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import ValidationError
# REMOVED: from core.memory import memory
# REMOVED: from core.action_router import action_router
from agents.models import PdfProcessingResult, InvoiceData, PolicyData, InvoiceLineItem
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file
import os
google_api_key = os.getenv("GOOGLE_API_KEY")

class PdfAgent:
    def __init__(self, memory_instance, action_router_instance, model_name: str = "gemini-2.0-flash"): # ADDED memory_instance
        self.memory = memory_instance # Store the memory instance
        self.action_router = action_router_instance # Store the action router instance
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.0,google_api_key =os.getenv(GOOGLE_API_KEY))
        self.invoice_parser = PydanticOutputParser(pydantic_object=InvoiceData)
        self.policy_parser = PydanticOutputParser(pydantic_object=PolicyData)

        self.invoice_examples = [
            {"text": "Invoice # INV-2023-001\nDate: 2023-10-26\nTotal Due: $1250.00\nItem: Consulting, Qty: 1, Price: 1000.00\nItem: Training, Qty: 1, Price: 250.00",
             "output": InvoiceData(invoice_number="INV-2023-001", date="2023-10-26", total_amount=1250.0, currency="$",
                                   line_items=[InvoiceLineItem(description="Consulting", quantity=1, unit_price=1000.0, total=1000.0),
                                               InvoiceLineItem(description="Training", quantity=1, unit_price=250.0, total=250.0)]).model_dump()},
            {"text": "Bill No. 000123\nDate: 2023/11/01\nGrand Total: 85.50 EUR\nService Fee: 1 * 85.50 = 85.50",
             "output": InvoiceData(invoice_number="000123", date="2023/11/01", total_amount=85.50, currency="EUR",
                                   line_items=[InvoiceLineItem(description="Service Fee", quantity=1, unit_price=85.50, total=85.50)]).model_dump()},
        ]

        self.policy_examples = [
            {"text": "Privacy Policy (Version 2.0)\nPolicy ID: PRIV-2023-001\nEffective: Jan 1, 2023\nThis policy outlines our commitment to GDPR compliance and data protection.",
             "output": PolicyData(policy_title="Privacy Policy (Version 2.0)", policy_id="PRIV-2023-001", keywords_found=["GDPR"], summary="This policy outlines the company's commitment to GDPR compliance and data protection.").model_dump()},
            {"text": "Drug Approval Guidelines (FDA)\nDocument Ref: FDA-DRUG-005\nThis document details the procedures for FDA approval of new pharmaceutical products.",
             "output": PolicyData(policy_title="Drug Approval Guidelines (FDA)", policy_id="FDA-DRUG-005", keywords_found=["FDA"], summary="This document details the procedures for FDA approval of new pharmaceutical products.").model_dump()},
        ]

        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", "You are a document processing agent. Extract structured data from the provided text content. Focus on either Invoice data or Policy data. If the text looks like an invoice, extract invoice details. If it looks like a policy document, extract policy details and relevant keywords like 'GDPR', 'FDA', 'HIPAA', 'CCPA', 'PCI DSS'. Respond only with the JSON that matches the format instructions.\n\n{format_instructions}\n"),
            ("human", "Here are some examples:\n{examples}\n\nNow process the following PDF content:\n{pdf_content}"),
        ])

    def _prepare_invoice_examples(self):
        example_str = ""
        for ex in self.invoice_examples:
            example_str += f"Content:\n{ex['text']}\nOutput: {json.dumps(ex['output'])}\n\n"
        return example_str

    def _prepare_policy_examples(self):
        example_str = ""
        for ex in self.policy_examples:
            example_str += f"Content:\n{ex['text']}\nOutput: {json.dumps(ex['output'])}\n\n"
        return example_str

    def _extract_text_from_pdf(self, pdf_bytes: bytes) -> str:
        text = ""
        try:
            reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
            for page in reader.pages:
                text += page.extract_text() or ""
            return text
        except PyPDF2.errors.PdfReadError as e:
            print(f"PDF Agent: Could not read PDF: {e}")
            return ""
        except Exception as e:
            print(f"PDF Agent: An unexpected error occurred during PDF text extraction: {e}")
            return ""

    def process(self, process_id: str, pdf_bytes: bytes) -> PdfProcessingResult:
        self.memory.add_entry(process_id, "pdf_agent_input", {"content_size": len(pdf_bytes)}) # Changed: Use self.memory
        
        extracted_text = self._extract_text_from_pdf(pdf_bytes)
        if not extracted_text:
            result = PdfProcessingResult(document_type="Other", flags=["PDF_Extraction_Failed"], invoice_data=None, policy_data=None)
            self.memory.add_entry(process_id, "pdf_agent_output", result.model_dump()) # Changed: Use self.memory
            self.action_router.trigger_anomaly_alert(process_id, {"reason": "PDF_Extraction_Failed"})
            return result

        llm_text = extracted_text[:8000]

        document_type = "Other"
        invoice_data = None
        policy_data = None
        flags = []

        try:
            invoice_chain = self.prompt_template | self.llm | self.invoice_parser
            parsed_invoice = invoice_chain.invoke({
                "pdf_content": llm_text,
                "examples": self._prepare_invoice_examples(),
                "format_instructions": self.invoice_parser.get_format_instructions()
            })
            invoice_data = parsed_invoice
            document_type = "Invoice"
            print(f"PDF Agent: Identified as Invoice, Total: {invoice_data.total_amount}")
            if invoice_data.total_amount > 10000:
                flags.append("Invoice_Total_High")
                self.action_router.trigger_risk_alert(process_id, {"reason": "HighValueInvoice", "total": invoice_data.total_amount, "invoice_num": invoice_data.invoice_number})

        except ValidationError as e:
            print(f"PDF Agent: Not an Invoice or validation failed for invoice: {e}")
        except Exception as e:
            print(f"PDF Agent: Error processing as invoice: {e}")

        if document_type == "Other":
            try:
                policy_chain = self.prompt_template | self.llm | self.policy_parser
                parsed_policy = policy_chain.invoke({
                    "pdf_content": llm_text,
                    "examples": self._prepare_policy_examples(),
                    "format_instructions": self.policy_parser.get_format_instructions()
                })
                policy_data = parsed_policy
                document_type = "Policy"
                print(f"PDF Agent: Identified as Policy, Keywords: {policy_data.keywords_found}")
                if any(kw.lower() in [s.lower() for s in policy_data.keywords_found] for kw in ["gdpr", "fda", "hipaa", "ccpa", "pci dss"]):
                    flags.append("Compliance_Relevant_Keywords")
                    self.action_router.trigger_compliance_flag(process_id, {"reason": "ComplianceKeywordsFound", "keywords": policy_data.keywords_found, "policy_title": policy_data.policy_title})
            except ValidationError as e:
                print(f"PDF Agent: Not a Policy or validation failed for policy: {e}")
            except Exception as e:
                print(f"PDF Agent: Error processing as policy: {e}")
        
        result = PdfProcessingResult(
            document_type=document_type,
            invoice_data=invoice_data,
            policy_data=policy_data,
            flags=flags
        )
        self.memory.add_entry(process_id, "pdf_agent_output", result.model_dump()) # Changed: Use self.memory
        
        if not flags:
             self.action_router.trigger_logging_and_close(process_id, {"message": f"PDF processed as {document_type}", "summary": result.model_dump()})

        return result
