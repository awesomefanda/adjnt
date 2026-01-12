from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

class AdjntIntent(BaseModel):
    intent: str = Field(description="TASK, PRIVACY, CLEAR_DATA, or CHAT")
    data: dict = Field(description="Extracted details. If CHAT, include 'answer' key with your response.")

class AdjntBrain:
    def __init__(self, model="llama3.2"):
        # We use temperature 0 for strictness
        self.llm = ChatOllama(model=model, format="json", temperature=0)
        self.parser = JsonOutputParser(pydantic_object=AdjntIntent)
        
        # Explicit instructions for JSON output
        self.prompt = ChatPromptTemplate.from_template(
            "SYSTEM: You are Adjnt, a local AI assistant. You MUST respond ONLY in valid JSON.\n"
            "RULES:\n"
            "1. If user asks about privacy: intent='PRIVACY', data={{'answer': '...'}}\n"
            "2. If user mentions a task/grocery: intent='TASK', data={{'item': '...', 'time': '...'}}\n"
            "3. For general chat: intent='CHAT', data={{'answer': '...'}}\n\n"
            "{format_instructions}\n"
            "USER MESSAGE: {message}"
        )
        self.chain = self.prompt | self.llm | self.parser

    async def decide(self, text: str):
        try:
            return await self.chain.ainvoke({"message": text, "format_instructions": self.parser.get_format_instructions()})
        except Exception as e:
            # Fallback if JSON parsing fails
            return {"intent": "CHAT", "data": {"answer": f"I had a parsing error, but you said: {text}"}}