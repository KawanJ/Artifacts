"""API Client for Artifacts MMO."""
import logging
import time
from typing import Dict, Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Custom exception for API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        """Initialize API error."""
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class APIClient:
    """HTTP API client for Artifacts MMO.
    
    Handles authentication, retries, error handling, and response parsing.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.artifactsmmo.com",
        max_retries: int = 3,
        timeout: int = 30,
    ):
        """Initialize the API client.
        
        Args:
            api_key: API key for authentication.
            base_url: Base URL for the API.
            max_retries: Maximum number of retry attempts.
            timeout: Request timeout in seconds.
        """
        self.api_key = api_key
        self.base_url = base_url
        self.max_retries = max_retries
        self.timeout = timeout
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry strategy.
        
        Returns:
            Configured requests.Session object.
        """
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT", "DELETE"],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set authorization header
        session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })
        
        return session

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an HTTP request to the API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            endpoint: API endpoint (without base URL).
            data: Request body data.
            params: Query parameters.
        
        Returns:
            Parsed JSON response.
        
        Raises:
            APIError: If the request fails.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            logger.debug(f"{method} {url}")
            
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                timeout=self.timeout,
            )
            
            response.raise_for_status()
            
            return response.json() if response.text else {}
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            logger.error(error_msg)
            raise APIError(error_msg, status_code=e.response.status_code)
        except requests.exceptions.RequestException as e:
            error_msg = f"Request failed: {str(e)}"
            logger.error(error_msg)
            raise APIError(error_msg)

    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a GET request.
        
        Args:
            endpoint: API endpoint.
            params: Query parameters.
        
        Returns:
            Parsed JSON response.
        """
        return self._make_request("GET", endpoint, params=params)

    def post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a POST request.
        
        Args:
            endpoint: API endpoint.
            data: Request body data.
            params: Query parameters.
        
        Returns:
            Parsed JSON response.
        """
        return self._make_request("POST", endpoint, data=data, params=params)

    def put(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a PUT request.
        
        Args:
            endpoint: API endpoint.
            data: Request body data.
        
        Returns:
            Parsed JSON response.
        """
        return self._make_request("PUT", endpoint, data=data)

    def delete(self, endpoint: str) -> Dict[str, Any]:
        """Make a DELETE request.
        
        Args:
            endpoint: API endpoint.
        
        Returns:
            Parsed JSON response.
        """
        return self._make_request("DELETE", endpoint)

    def close(self) -> None:
        """Close the session."""
        self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
