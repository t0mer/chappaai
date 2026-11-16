from whatsapp import InboundMessage, InboundReaction

from .base_handler import BaseHandler


class MessageHandler(BaseHandler):
    """Listen-only handler: stores inbound messages and reactions, never replies."""

    async def __call__(self, event: InboundMessage | InboundReaction):
        if isinstance(event, InboundReaction):
            await self.store_reaction(event)
        else:
            await self.store_message(event)
        await self.session.commit()
