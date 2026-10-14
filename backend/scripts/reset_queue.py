"""Clear a queue and its patients from Redis.

Usage (from backend/):  python -m scripts.reset_queue [QUEUE_NAME]
"""

import asyncio
import sys

from app.services.redis_client import redis_client as r

async def reset_queue(branch_id="ENT"):
    queue_key = f"queue:{branch_id}"

    # Get existing user IDs in the queue (if any)
    existing_users = await r.lrange(queue_key, 0, -1)

    # Delete queue key
    await r.delete(queue_key)

    # Delete associated user hashes
    for uid in existing_users:
        await r.delete(f"user:{uid}")

    print(f"Cleared queue and user data for branch: {branch_id}")

if __name__ == "__main__":
    asyncio.run(reset_queue(*sys.argv[1:2]))
