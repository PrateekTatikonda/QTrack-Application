"""Outbound WhatsApp Business API messaging."""

import logging

import aiohttp

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_whatsapp_response(to_number: str, message: str):
    """Send a text message via the WhatsApp Business API."""
    try:
        whatsapp_token = settings.whatsapp_access_token
        phone_number_id = settings.whatsapp_phone_number_id

        if not whatsapp_token or not phone_number_id:
            logger.error("WhatsApp credentials not configured")
            return

        url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"

        headers = {
            "Authorization": f"Bearer {whatsapp_token}",
            "Content-Type": "application/json"
        }

        data = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {"body": message}
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    logger.info(f"WhatsApp message sent to {to_number}")
                else:
                    logger.error(f"Failed to send WhatsApp message: {response.status}")

    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {str(e)}")
