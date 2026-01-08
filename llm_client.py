"""Lightweight HTTP client for OpenAI-compatible LLM APIs using httpx.
Supports streaming responses via Server-Sent Events (SSE).
"""

import json
import httpx
from typing import Iterator, Optional, List, Dict, Any


class Message:
    """Simple message object to match OpenAI API format."""
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content


class Delta:
    """Represents a delta in streaming responses."""
    def __init__(self, content: Optional[str] = None, role: Optional[str] = None):
        self.content = content
        self.role = role


class Choice:
    """Represents a choice in the completion response."""
    def __init__(self, delta: Optional[Dict] = None, message: Optional[Message] = None,
                 index: int = 0, finish_reason: Optional[str] = None):
        if delta is not None:
            self.delta = Delta(
                content=delta.get('content'),
                role=delta.get('role')
            )
        else:
            self.delta = Delta()
        self.message = message
        self.index = index
        self.finish_reason = finish_reason


class ChatCompletionChunk:
    """Represents a streaming chunk from chat completion."""
    def __init__(self, id: str, choices: List[Choice], created: int, model: str):
        self.id = id
        self.choices = choices
        self.created = created
        self.model = model


class ChatCompletion:
    """Represents a complete chat completion response."""
    def __init__(self, id: str, choices: List[Choice], created: int, model: str):
        self.id = id
        self.choices = choices
        self.created = created
        self.model = model


class Model:
    """Represents a model from the models list."""
    def __init__(self, id: str, owned_by: str = ""):
        self.id = id
        self.owned_by = owned_by


class ModelList:
    """Container for list of models."""
    def __init__(self, data: List[Model]):
        self.data = data


class ModelsAPI:
    """API for model-related operations."""
    def __init__(self, base_url: str, api_key: str, client: httpx.Client):
        self.base_url = base_url
        self.api_key = api_key
        self.client = client

    def list(self) -> ModelList:
        """List available models."""
        response = self.client.get(
            f"{self.base_url}/models",
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        response.raise_for_status()
        data = response.json()
        models = [Model(id=m.get('id', ''), owned_by=m.get('owned_by', ''))
                  for m in data.get('data', [])]
        return ModelList(data=models)


class ChatCompletionsAPI:
    """API for chat completion operations."""
    def __init__(self, base_url: str, api_key: str, client: httpx.Client):
        self.base_url = base_url
        self.api_key = api_key
        self.client = client

    def create(self, model: str, messages: List[Dict[str, str]],
               stream: bool = False, **kwargs) -> Any:
        """Create a chat completion.

        Args:
            model: Model identifier
            messages: List of message dicts with 'role' and 'content'
            stream: If True, returns an iterator of chunks; if False, returns complete response
            **kwargs: Additional parameters to pass to the API
        """
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            **kwargs
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        if stream:
            return self._create_stream(payload, headers)
        else:
            return self._create_non_stream(payload, headers)

    def _create_non_stream(self, payload: Dict, headers: Dict) -> ChatCompletion:
        """Create a non-streaming chat completion."""
        response = self.client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=60.0
        )
        response.raise_for_status()
        data = response.json()

        choices = []
        for choice_data in data.get('choices', []):
            msg = choice_data.get('message', {})
            message = Message(role=msg.get('role', ''), content=msg.get('content', ''))
            choice = Choice(
                message=message,
                index=choice_data.get('index', 0),
                finish_reason=choice_data.get('finish_reason')
            )
            choices.append(choice)

        return ChatCompletion(
            id=data.get('id', ''),
            choices=choices,
            created=data.get('created', 0),
            model=data.get('model', '')
        )

    def _create_stream(self, payload: Dict, headers: Dict) -> Iterator[ChatCompletionChunk]:
        """Create a streaming chat completion.

        Yields ChatCompletionChunk objects as they arrive via SSE.
        """
        with self.client.stream(
            'POST',
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=None  # No timeout for streaming
        ) as response:
            response.raise_for_status()

            for line in response.iter_lines():
                line = line.strip()

                # SSE format: "data: {...}" or "data: [DONE]"
                if not line or not line.startswith('data: '):
                    continue

                data_str = line[6:]  # Remove "data: " prefix

                # Check for end of stream
                if data_str == '[DONE]':
                    break

                try:
                    data = json.loads(data_str)

                    choices = []
                    for choice_data in data.get('choices', []):
                        delta = choice_data.get('delta', {})
                        choice = Choice(
                            delta=delta,
                            index=choice_data.get('index', 0),
                            finish_reason=choice_data.get('finish_reason')
                        )
                        choices.append(choice)

                    chunk = ChatCompletionChunk(
                        id=data.get('id', ''),
                        choices=choices,
                        created=data.get('created', 0),
                        model=data.get('model', '')
                    )
                    yield chunk

                except json.JSONDecodeError:
                    # Skip malformed JSON
                    continue


class ChatAPI:
    """API for chat-related operations."""
    def __init__(self, base_url: str, api_key: str, client: httpx.Client):
        self.completions = ChatCompletionsAPI(base_url, api_key, client)


class LLMClient:
    """Lightweight HTTP client for OpenAI-compatible LLM APIs.

    Drop-in replacement for OpenAI client with minimal import overhead.

    Example:
        # Basic usage
        client = LLMClient(base_url="http://localhost:8080/v1", api_key="dummy")

        # List models
        models = client.models.list()

        # Non-streaming
        response = client.chat.completions.create(
            model="mymodel",
            messages=[{"role": "user", "content": "Hello"}],
            stream=False
        )

        # Streaming
        for chunk in client.chat.completions.create(
            model="mymodel",
            messages=[{"role": "user", "content": "Hello"}],
            stream=True
        ):
            if chunk.choices and chunk.choices[0].delta.content:
                print(chunk.choices[0].delta.content, end='')

        # Clean up when done
        client.close()

        # Or use as context manager (recommended)
        with LLMClient(base_url="http://localhost:8080/v1") as client:
            response = client.chat.completions.create(...)
    """

    def __init__(self, base_url: str, api_key: str = "dummy"):
        """Initialize the client.

        Args:
            base_url: Base URL of the API (e.g., "http://localhost:8080/v1")
            api_key: API key (can be dummy for local servers)
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key

        # Create a persistent HTTP client for connection reuse
        self.http_client = httpx.Client(timeout=60.0)

        # Initialize API endpoints
        self.models = ModelsAPI(self.base_url, self.api_key, self.http_client)
        self.chat = ChatAPI(self.base_url, self.api_key, self.http_client)

    def close(self):
        """Explicitly close the HTTP client and clean up resources."""
        if hasattr(self, 'http_client') and self.http_client is not None:
            self.http_client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        """Context manager exit - ensures cleanup."""
        self.close()
        return False

    def __del__(self):
        """Clean up HTTP client on deletion (fallback)."""
        self.close()
