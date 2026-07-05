import jwt
import time

def generate_mock_jwt(uid: str = "mock-user", email: str = "mock@aegis.gov", expires_in: int = 3600) -> str:
    """Helper function to generate a mock JWT token signed with a test key."""
    payload = {
        "uid": uid,
        "email": email,
        "exp": int(time.time()) + expires_in,
        "iss": "https://securetoken.google.com/aegis-platform",
        "aud": "aegis-platform"
    }
    # For testing, we sign using a simple test key.
    # In actual firebase, this is verified against Google's public certs.
    # The mock server accepts any token starting with 'mock-' or 'test-token-key'.
    token = jwt.encode(payload, "test-token-key", algorithm="HS256")
    return token
