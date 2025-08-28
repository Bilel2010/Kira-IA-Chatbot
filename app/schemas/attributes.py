from pydantic import BaseModel
from typing import List, Optional

class AttributeQuestion(BaseModel):
    field: str              # ex: "marque"
    question: str           # ex: "Quelle est la marque de la voiture ?"
    options: Optional[List[str]] = None  # ex: ["Peugeot", "Renault"] si applicable

class AttributeAnswer(BaseModel):
    field: str              # ex: "marque"
    value: str              # ex: "Peugeot"
