import re
import logging
from app.core.ai_client import AIClient

logger = logging.getLogger("swarmwarm.ai_service")

class AIService:
    """
    Prompt engineering service responsible for formatting system instructions,
    tuning local inference hyper-parameters, and sanitizing LLM text outputs.
    """
    def __init__(self):
        self.client = AIClient()
        # Default model tag used inside the Swarm network
        self.model_name = "gemma"
        
    def sanitize_output(self, text: str) -> str:
        """
        Strips away common robotic conversational prefaces, markdown artifacts,
        and template placeholders to ensure the output looks like organic human text.
        """
        if not text:
             return ""
             
        # 1. Remove markdown code fences and plaintext tag blocks
        text = re.sub(r"```[a-zA-Z]*", "", text)
        text = text.replace("```", "")
        
        # 2. Strip standard LLM prefaces (case-insensitive)
        prefaces = [
            r"^here is your email:?",
            r"^here is the email:?",
            r"^sure, here is the email:?",
            r"^sure, here's a draft:?",
            r"^subject:.*",
            r"^dear [a-zA-Z\s]+,?",
            r"^hi [a-zA-Z\s]+,?",
            r"^hello [a-zA-Z\s]+,?"
        ]
        for pattern in prefaces:
             text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)
             
        # 3. Strip trailing signatures / standard templates
        signatures = [
            r"best regards,?",
            r"sincerely,?",
            r"warmly,?",
            r"thanks,?",
            r"thank you,?"
        ]
        for pattern in signatures:
             text = re.sub(pattern + r".*$", "", text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
             
        # 4. Eliminate brackets placeholder segments
        text = re.sub(r"\[[a-zA-Z\s\-_]+\]", "", text)
        
        # 5. Collapse duplicate newlines and leading/trailing whitespace
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        return text.strip()

    async def generate_thread_starter(self) -> dict:
        """
        Generates a unique B2B business introductory outreach email body.
        Applies temp=0.85 to bypass footprint verification filters.
        """
        system_prompt = (
            "You are an Elite B2B Project Coordinator.\n"
            "Objective: Write a short, professional, single-paragraph business email update.\n"
            "Constraints:\n"
            "- Do NOT include any placeholder brackets or text like [Your Name], [Company], or [Date].\n"
            "- Do NOT write a Subject line.\n"
            "- Do NOT include conversational filler before or after the email text (e.g., do not say 'Here is your email:').\n"
            "- Must be between 2 and 4 sentences max.\n"
            "- Randomly select one business topic: database scaling, migration scheduling, system architecture reviews, or budget audits."
        )
        
        prompt = "Compose a fresh, unique introductory business outreach message."
        
        raw_response = await self.client.generate(
            model=self.model_name,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.85
        )
        
        sanitized = self.sanitize_output(raw_response)
        logger.info(f"AI Service: Starter generated. Sanitized length: {len(sanitized)}")
        return {"body": sanitized}

    async def generate_thread_reply(self, incoming_email_body: str) -> str:
        """
        Generates a context-aware response reply to an incoming email thread.
        Applies temp=0.50 to keep the response focused and realistic.
        """
        system_prompt = (
            "You are a professional corporate worker replying to a colleague's email.\n"
            "Objective: Read the incoming email history and generate a natural, single-sentence response.\n"
            "Constraints:\n"
            "- Rely strictly on the context of the incoming text.\n"
            "- Do NOT add greeting fillers, signatures, or placeholders.\n"
            "- Must look like a quick, human reply sent from a mobile device (e.g., 'I will look into that and get back to you shortly.')."
        )
        
        # Clean incoming mail context
        cleaned_history = re.sub(r"^>+", "", incoming_email_body, flags=re.MULTILINE).strip()
        prompt = f"[INCOMING EMAIL HISTORY]\n{cleaned_history}\n\n[TASK]\nGenerate response string."
        
        raw_response = await self.client.generate(
            model=self.model_name,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.50
        )
        
        sanitized = self.sanitize_output(raw_response)
        logger.info(f"AI Service: Contextual reply generated. Sanitized length: {len(sanitized)}")
        return sanitized
