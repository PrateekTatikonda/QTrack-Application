from pydantic import BaseModel

class JoinQueueRequest(BaseModel):
    name: str
    phone: str
    branch_id: str
