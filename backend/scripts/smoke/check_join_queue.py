"""Manual smoke check: POST /join-queue against a running server.

Usage (from backend/):  python -m scripts.smoke.check_join_queue [BASE_URL]
"""

import asyncio
import sys

import aiohttp


async def check_join_queue(base_url: str = "http://localhost:8000"):
    payload = {
        "name": "Jathin Test",
        "phone": "12312312353",
        "branch_id": "main",
        "service_type": "ent"
    }

    print(f"Testing API call with payload: {payload}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{base_url}/join-queue", json=payload) as response:
                print(f"Response status: {response.status}")
                if response.status == 200:
                    print(f"Success! Response: {await response.json()}")
                else:
                    print(f"Error! Status: {response.status}, Text: {await response.text()}")
    except Exception as e:
        print(f"Exception occurred: {str(e)}")


if __name__ == "__main__":
    asyncio.run(check_join_queue(*sys.argv[1:2]))
