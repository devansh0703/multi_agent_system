# File: /multi_agent_system/agents/classifier_agent.py
import json
from typing import Union, Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import ValidationError
# REMOVED: from core.memory import memory
from agents.models import ClassificationResult
from dotenv import load_dotenv 
import os
load_dotenv()  # Load environment variables from .env file

google_api_key = os.getenv("GOOGLE_API_KEY")
class ClassifierAgent:
    def __init__(self, memory_instance, model_name: str = "gemini-2.0-flash"): # ADDED memory_instance
        self.memory = memory_instance # Store the memory instance
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.0,google_api_key = "AIzaSyAsBIw0b-EyKGJQNyt-ob6Tq_vSlwhsuJA")
        self.parser = PydanticOutputParser(pydantic_object=ClassificationResult)
        self.format_instruction = self.parser.get_format_instructions()

        self.few_shot_examples = [
            {"input": "Subject: Urgent - Complaint about service", "format": "Email", "intent": "Complaint"},
            {"input": "{'event': 'order_created', 'data': {'id': '123'}}", "format": "JSON", "intent": "Unknown"},
            {"input": "Invoice #XYZ - Total $1500", "format": "Email", "intent": "Invoice"},
            {"input": "This document outlines our privacy policy and GDPR compliance.", "format": "PDF", "intent": "Regulation"},
            {"input": "Subject: Quote Request for Hardware", "format": "Email", "intent": "RFQ"},
            {"input": "Possible fraudulent activity detected on account 123", "format": "Email", "intent": "Fraud Risk"},
            {"input": "{'webhook_event': 'new_user', 'user_id': 'abc'}", "format": "JSON", "intent": "Unknown"},
            {"input": "This agreement details financial terms. Invoice No. 2023-001. Total: 5000 USD", "format": "PDF", "intent": "Invoice"},
        ]

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a highly accurate document classifier. Your task is to identify the format (Email, JSON, PDF) and the business intent (RFQ, Complaint, Invoice, Regulation, Fraud Risk, Unknown) of the provided text/content snippet. Use schema matching for JSON. If the content is very short or ambiguous, classify as 'Unknown'.\n{format_instructions}"),
            ("human", "Here are some examples:\n{examples}\nNow classify the following:\nContent: {input_content}"),
        ])

        self.chain = self.prompt | self.llm | self.parser

    def _prepare_examples(self):
        example_str = ""
        for ex in self.few_shot_examples:
            example_str += f"Input: {ex['input']}\nOutput: format={ex['format']}, intent={ex['intent']}\n\n"
        return example_str

    def classify_format_heuristic(self, content: Union[str, bytes]) -> str:
        if isinstance(content, bytes):
            if content.startswith(b"%PDF"):
                return "PDF"
            try:
                decoded_content = content.decode('utf-8')
            except UnicodeDecodeError:
                return "Unknown"
        else:
            decoded_content = content

        if "From:" in decoded_content and "Subject:" in decoded_content and "@" in decoded_content:
            return "Email"
        
        if decoded_content.strip().startswith("{") and decoded_content.strip().endswith("}"):
            try:
                json.loads(decoded_content)
                return "JSON"
            except json.JSONDecodeError:
                pass
        
        if "PDF" in decoded_content[:100]:
            return "PDF"

        return "Unknown"

    def process(self, process_id: str, content: Union[str, bytes]) -> ClassificationResult:
        self.memory.add_entry(process_id, "classifier_agent_input", {"content_length": len(content), "content_type": type(content).__name__}) # Changed: Use self.memory
        
        heuristic_format = self.classify_format_heuristic(content)

        if isinstance(content, bytes):
            if heuristic_format == "PDF":
                preview_content = content[:2048].decode('latin-1', errors='ignore')
            else:
                try:
                    preview_content = content.decode('utf-8', errors='ignore')
                except:
                    preview_content = str(content)
        else:
            preview_content = content

        try:
            result = self.chain.invoke({
                "input_content": preview_content,
                "examples": self._prepare_examples(),
                "format_instructions": self.format_instruction
            })
            
            if heuristic_format != "Unknown":
                result.format = heuristic_format
            
            self.memory.add_entry(process_id, "classifier_agent_output", result.model_dump()) # Changed: Use self.memory
            print(f"Classifier Agent: Format={result.format}, Intent={result.intent}")
            return result
        except ValidationError as e:
            print(f"Classifier Agent: Pydantic validation error: {e}")
            result = ClassificationResult(format=heuristic_format, intent="Unknown", confidence=0.0)
            self.memory.add_entry(process_id, "classifier_agent_output", result.model_dump()) # Changed: Use self.memory
            return result
        except Exception as e:
            print(f"Classifier Agent: An error occurred during classification: {e}")
            result = ClassificationResult(format=heuristic_format, intent="Unknown", confidence=0.0)
            self.memory.add_entry(process_id, "classifier_agent_output", result.model_dump()) # Changed: Use self.memory
            return result