"""
GitHub OAuth implementation for seller verification
Provides OAuth flow and GitHub API client for profile fetching
"""

import secrets
from typing import Optional, Dict, Any
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
import structlog

logger = structlog.get_logger()


@dataclass
class GitHubUser:
    """GitHub user profile data"""
    id: int
    login: str  # username
    name: Optional[str]
    email: Optional[str]
    avatar_url: Optional[str]
    html_url: str  # profile URL
    bio: Optional[str]
    company: Optional[str]
    location: Optional[str]
    public_repos: int
    followers: int
    following: int
    created_at: str

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "GitHubUser":
        """Create GitHubUser from GitHub API response"""
        return cls(
            id=data["id"],
            login=data["login"],
            name=data.get("name"),
            email=data.get("email"),
            avatar_url=data.get("avatar_url"),
            html_url=data["html_url"],
            bio=data.get("bio"),
            company=data.get("company"),
            location=data.get("location"),
            public_repos=data.get("public_repos", 0),
            followers=data.get("followers", 0),
            following=data.get("following", 0),
            created_at=data["created_at"]
        )


class GitHubOAuth:
    """
    GitHub OAuth handler for seller verification
    
    OAuth Flow:
    1. Generate authorization URL with state parameter
    2. User authorizes on GitHub
    3. GitHub redirects back with code
    4. Exchange code for access token
    5. Fetch user profile with access token
    """
    
    AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    API_URL = "https://api.github.com"
    
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scopes: Optional[list] = None
    ):
        """
        Initialize GitHub OAuth client
        
        Args:
            client_id: GitHub OAuth App client ID
            client_secret: GitHub OAuth App client secret
            redirect_uri: Callback URL for OAuth redirect
            scopes: OAuth scopes to request (default: read:user)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes or ["read:user"]
        
        # Store pending OAuth states (in production, use Redis or database)
        self._pending_states: Dict[str, str] = {}  # state -> seller_address
    
    def generate_state(self, seller_address: str) -> str:
        """
        Generate a random state parameter for CSRF protection
        Associates the state with a seller address
        
        Args:
            seller_address: Ethereum address of the seller
            
        Returns:
            Random state string
        """
        state = secrets.token_urlsafe(32)
        self._pending_states[state] = seller_address.lower()
        return state
    
    def validate_state(self, state: str) -> Optional[str]:
        """
        Validate and consume a state parameter
        
        Args:
            state: State parameter from OAuth callback
            
        Returns:
            Seller address if valid, None otherwise
        """
        seller_address = self._pending_states.pop(state, None)
        return seller_address
    
    def get_authorization_url(self, seller_address: str) -> str:
        """
        Generate GitHub OAuth authorization URL
        
        Args:
            seller_address: Ethereum address of the seller
            
        Returns:
            Full authorization URL to redirect user to
        """
        state = self.generate_state(seller_address)
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "state": state,
        }
        
        url = f"{self.AUTHORIZE_URL}?{urlencode(params)}"
        
        logger.info(
            "github_oauth_url_generated",
            seller_address=seller_address,
            redirect_uri=self.redirect_uri
        )
        
        return url
    
    async def exchange_code_for_token(self, code: str) -> Optional[str]:
        """
        Exchange authorization code for access token
        
        Args:
            code: Authorization code from GitHub callback
            
        Returns:
            Access token if successful, None otherwise
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.TOKEN_URL,
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "code": code,
                        "redirect_uri": self.redirect_uri,
                    },
                    headers={
                        "Accept": "application/json"
                    }
                )
                response.raise_for_status()
                
                data = response.json()
                
                if "error" in data:
                    logger.error(
                        "github_token_exchange_failed",
                        error=data.get("error"),
                        description=data.get("error_description")
                    )
                    return None
                
                access_token = data.get("access_token")
                
                if access_token:
                    logger.info("github_token_exchange_success")
                    return access_token
                
                return None
                
            except httpx.HTTPError as e:
                logger.error("github_token_exchange_error", error=str(e))
                return None
    
    async def get_user(self, access_token: str) -> Optional[GitHubUser]:
        """
        Fetch user profile from GitHub API
        
        Args:
            access_token: GitHub access token
            
        Returns:
            GitHubUser if successful, None otherwise
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.API_URL}/user",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28"
                    }
                )
                response.raise_for_status()
                
                data = response.json()
                user = GitHubUser.from_api_response(data)
                
                logger.info(
                    "github_user_fetched",
                    github_id=user.id,
                    username=user.login
                )
                
                return user
                
            except httpx.HTTPError as e:
                logger.error("github_user_fetch_error", error=str(e))
                return None
    
    async def verify_user(self, code: str, state: str) -> Optional[tuple[str, GitHubUser]]:
        """
        Complete OAuth flow: validate state, exchange code, fetch user
        
        Args:
            code: Authorization code from callback
            state: State parameter from callback
            
        Returns:
            Tuple of (seller_address, GitHubUser) if successful, None otherwise
        """
        # Validate state and get seller address
        seller_address = self.validate_state(state)
        if not seller_address:
            logger.warning("github_oauth_invalid_state", state=state[:10])
            return None
        
        # Exchange code for token
        access_token = await self.exchange_code_for_token(code)
        if not access_token:
            logger.error("github_oauth_token_failed", seller_address=seller_address)
            return None
        
        # Fetch user profile
        user = await self.get_user(access_token)
        if not user:
            logger.error("github_oauth_user_failed", seller_address=seller_address)
            return None
        
        logger.info(
            "github_oauth_verification_complete",
            seller_address=seller_address,
            github_id=user.id,
            github_username=user.login
        )
        
        return (seller_address, user)


# Singleton instance
_github_oauth: Optional[GitHubOAuth] = None


def get_github_oauth() -> Optional[GitHubOAuth]:
    """
    Get or create GitHub OAuth singleton
    Returns None if GitHub OAuth is not configured
    """
    global _github_oauth
    
    if _github_oauth is None:
        from src.config import get_marketplace_config
        config = get_marketplace_config()
        
        if not config.github_client_id or not config.github_client_secret:
            logger.warning("github_oauth_not_configured")
            return None
        
        _github_oauth = GitHubOAuth(
            client_id=config.github_client_id,
            client_secret=config.github_client_secret,
            redirect_uri=config.github_callback_url
        )
    
    return _github_oauth

