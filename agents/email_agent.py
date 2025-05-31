# File: /multi_agent_system/agents/email_agent.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import ValidationError
# REMOVED: from core.memory import memory
# REMOVED: from core.action_router import action_router
from agents.models import EmailContent
from dotenv import load_dotenv 
load_dotenv()  # Load environment variables from .env file
import os

google_api_key = os.getenv("GOOGLE_API_KEY")
class EmailAgent:
    def __init__(self, memory_instance, action_router_instance, model_name: str = "gemini-2.0-flash"): # ADDED memory_instance
        self.memory = memory_instance # Store the memory instance
        self.action_router = action_router_instance # Store the action router instance
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.0,google_api_key =os.getenv(GOOGLE_API_KEY))
        self.parser = PydanticOutputParser(pydantic_object=EmailContent)
        self.format_instruction = self.parser.get_format_instructions()

        self.few_shot_examples = [
            {"email": "From: customer@example.com\nSubject: Urgent - Service Down!\nDear Support, our service has been down for 2 hours, this is unacceptable! Fix it now!\nSincerely, An Upset Customer",
             "sender": "customer@example.com", "urgency": "High", "issue_request": "Service outage, urgent fix required", "tone": "Escalation"},
            {"email": "From: info@company.com\nSubject: Quick Question\nHi Team, just wondering about the latest update on project X. No rush, just curious.\nThanks, John",
             "sender": "info@company.com", "urgency": "Low", "issue_request": "Inquiry about project X update", "tone": "Polite"},
            {"email": "From: fraudster@evil.net\nSubject: You owe us money\nPay us 5000 USD by tomorrow or face consequences. We know where you live.",
             "sender": "fraudster@evil.net", "urgency": "High", "issue_request": "Demand for money, threat of harm", "tone": "Threatening"},
            {"email": "From: hr@corp.com\nSubject: Meeting Reminder\nReminder for the all-hands meeting at 2 PM. Please be on time.",
             "sender": "hr@corp.com", "urgency": "Medium", "issue_request": "Meeting reminder", "tone": "Neutral"},
        ]

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an email processing agent. Extract the sender, urgency, main issue/request, and tone from the given email content. Be precise and concise for the issue/request field. The tone should be one of 'Escalation', 'Polite', 'Threatening', 'Neutral', 'Unknown'.\n{format_instructions}"),
            ("human", "Here are some examples:\n{examples}\nNow process the following email:\n{email_content}"),
        ])

        self.chain = self.prompt | self.llm | self.parser

    def _prepare_examples(self):
        example_str = ""
        for ex in self.few_shot_examples:
            example_str += (f"Email:\n{ex['email']}\n"
                            f"Output: sender='{ex['sender']}', urgency='{ex['urgency']}', "
                            f"issue_request='{ex['issue_request']}', tone='{ex['tone']}'\n\n")
        return example_str

    def process(self, process_id: str, email_content: str) -> EmailContent:
        self.memory.add_entry(process_id, "email_agent_input", {"content": email_content[:200] + "..." if len(email_content) > 200 else email_content}) # Changed: Use self.memory
        
        try:
            parsed_email = self.chain.invoke({
                "email_content": email_content,
                "examples": self._prepare_examples(),
                "format_instructions": self.format_instruction
            })
            
            self.memory.add_entry(process_id, "email_agent_output", parsed_email.model_dump()) # Changed: Use self.memory
            print(f"Email Agent: Sender={parsed_email.sender}, Urgency={parsed_email.urgency}, Tone={parsed_email.tone}")

            if parsed_email.tone == "Escalation" and parsed_email.urgency == "High":
                self.action_router.trigger_crm_escalation(process_id, parsed_email.model_dump())
            elif parsed_email.tone == "Threatening":
                self.action_router.trigger_risk_alert(process_id, parsed_email.model_dump())
            else:
                self.action_router.trigger_logging_and_close(process_id, parsed_email.model_dump())

            return parsed_email
        except ValidationError as e:
            print(f"Email Agent: Pydantic validation error: {e}")
            self.memory.add_entry(process_id, "email_agent_error", {"error": str(e), "content": email_content[:100]}) # Changed: Use self.memory
            self.action_router.trigger_logging_and_close(process_id, {"error": "Email parsing failed", "details": str(e)})
            return EmailContent(sender="Unknown", urgency="Unknown", issue_request="Parsing failed", tone="Unknown")
        except Exception as e:
            print(f"Email Agent: An error occurred: {e}")
            self.memory.add_entry(process_id, "email_agent_error", {"error": str(e), "content": email_content[:100]}) # Changed: Use self.memory
            self.action_router.trigger_logging_and_close(process_id, {"error": "Email processing failed", "details": str(e)})
            return EmailContent(sender="Unknown", urgency="Unknown", issue_request="Processing failed", tone="Unknown")
