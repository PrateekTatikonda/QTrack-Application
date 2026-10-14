from pydantic import BaseModel

class JoinQueueRequest(BaseModel):
    name: str
    phone: str
    branch_id: str
    service_type: str = "general"  # Default to general if not specified
