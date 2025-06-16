import asyncio
from app.services.redis_client import r

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
    asyncio.run(reset_queue())
