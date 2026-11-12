import logging
import aiohttp
from typing import Optional

logger = logging.getLogger(__name__)


class PeerdomClient:
    """
    Client for interacting with the Peerdom API.
    Fetches roles and role details for peers identified by email.
    """

    BASE_URL = "https://api.peerdom.app/v1"

    def __init__(self, api_key: str):
        """
        Initialize the Peerdom client.
        
        Args:
            api_key: The Peerdom API key (typically from PEERDOM_API_KEY env var)
        """
        self.api_key = api_key
        self.headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json"
        }

    async def get_peer_by_email(self, email: str) -> Optional[dict]:
        """
        Fetch peer information by email address.
        
        Args:
            email: The peer's email address
            
        Returns:
            Peer object with id, firstName, lastName, email, and roles, or None if not found
        """
        try:
            async with aiohttp.ClientSession() as session:
                # First, get all peers and filter by email (Peerdom API doesn't have direct email lookup)
                url = f"{self.BASE_URL}/peers"
                async with session.get(url, headers=self.headers) as resp:
                    if resp.status != 200:
                        error_body = await resp.text()
                        logger.warning(f"Peerdom API error ({resp.status}): {error_body[:200]}")
                        return None

                    peers = await resp.json()
                    # Find peer with matching email
                    for peer in peers:
                        if peer.get("email") == email:
                            return peer
                    
                    logger.warning(f"No peer found in Peerdom for email: {email}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error fetching peer from Peerdom: {e}")
            return None


    async def get_roles_by_peer_id(self, peer_id: str) -> Optional[list]:
        """
        Fetch all roles for a specific peer by peer ID.
        
        Args:
            peer_id: The peer ID from Peerdom
            
        Returns:
            List of role objects with name, purpose, accountabilities, domain, etc., or None if error
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/roles"
                params = {"peer": peer_id}
                async with session.get(url, headers=self.headers, params=params) as resp:
                    if resp.status != 200:
                        error_body = await resp.text()
                        logger.warning(f"Peerdom API error ({resp.status}): {error_body[:200]}")
                        return None

                    roles = await resp.json()
                    return roles if roles else []
                    
        except Exception as e:
            logger.error(f"Error fetching roles for peer {peer_id} from Peerdom: {e}")
            return None

    async def get_peer_roles_summary(self, email: str) -> Optional[str]:
        """
        Fetch all roles for a peer and create a concise summary for context.
        
        This is the main integration point - fetches roles and creates a formatted
        summary that can be stored in session state for the model to understand
        the user's organizational role context.
        
        Args:
            email: The peer's email address
            
        Returns:
            A formatted string summarizing the peer's roles (title, purpose, accountabilities),
            or None if the peer is not found or has no roles
        """
        try:
            # Get peer by email
            peer = await self.get_peer_by_email(email)
            if not peer:
                logger.info(f"Peer not found in Peerdom for email: {email}")
                return None

            peer_id = peer.get("id")
            if not peer_id:
                logger.info(f"Peer found but has no ID: {email}")
                return None

            # Fetch all roles for this peer
            roles = await self.get_roles_by_peer_id(peer_id)
            if not roles:
                logger.warning(f"No roles found for peer: {email}")
                return None

            # Build role summaries
            role_summaries = []
            for role in roles:
                summary_parts = [f"**{role.get('name', 'Unknown')}**"]
                
                if purpose := role.get("purpose"):
                    summary_parts.append(f"Purpose: {purpose}")
                
                if accountabilities := role.get("accountabilities"):
                    # accountabilities is an array, join with newline
                    accountabilities_text = "\n".join(accountabilities)
                    summary_parts.append(f"Accountabilities:\n{accountabilities_text}")

                role_summaries.append("\n".join(summary_parts))

            if not role_summaries:
                return None

            # Create a formatted summary
            full_summary = f"User Organizational Context:\n\n" + "\n\n".join(role_summaries)
            logger.info(f"Generated roles summary for {email}: {len(role_summaries)} roles")
            
            return full_summary
            
        except Exception as e:
            logger.error(f"Error generating peer roles summary: {e}")
            return None
