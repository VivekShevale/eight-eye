import getpass

import httpx

from app.config import settings


class ChatCLI:
    """Terminal chat against the running API, for checking RAG answers before a frontend exists.

    Run from the project root: python -m scripts.chat_cli (scripts/ needs an __init__.py).
    """

    EXIT_WORDS = {"exit", "quit"}

    def __init__(self) -> None:
        self.client = httpx.Client(base_url=settings.api_base_url, timeout=120.0)

    def authenticate(self) -> None:
        """Log in (or register first) and keep the token on the client."""
        while True:
            choice = input("\n[1] Login  [2] Register: ").strip()
            if choice not in {"1", "2"}:
                continue
            credentials = {"email": input("Email: ").strip(), "password": getpass.getpass("Password: ")}
            if choice == "2":
                registered = self.client.post("/api/v1/auth/register", json=credentials)
                if registered.is_error:
                    print(f"\nError: {registered.json().get('message', registered.text)}")
                    continue
            response = self.client.post("/api/v1/auth/login", json=credentials)
            if response.is_success:
                self.client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
                return
            print(f"\nError: {response.json().get('message', response.text)}")

    @staticmethod
    def show_answer(data: dict) -> None:
        """Print the answer and its sources."""
        message = data.get("assistant_message", data)
        print(f"\nAssistant:\n{message.get('content') or message.get('answer', 'No answer received.')}")
        for source in message.get("sources", []):
            print(f"- {source['filename']} (page {source['page_number']})")
        print("-" * 60)

    def ask(self, chat_id: str, question: str) -> None:
        """Send one question and print the result or a readable error."""
        try:
            response = self.client.post(f"/api/v1/chats/{chat_id}/messages", json={"question": question})
            if response.is_error:
                print(f"\nAPI error ({response.status_code}): {response.json().get('message', response.text)}")
                return
            self.show_answer(response.json())
        except httpx.TimeoutException:
            print("\nRequest timed out. Please try again.")

    def run(self) -> None:
        """Log in, open a chat and loop until the user types exit."""
        print("Type 'exit' to quit.")
        try:
            self.authenticate()
            chat_id = self.client.post("/api/v1/chats", json={}).raise_for_status().json()["chat_id"]
            while (question := input("\nYou: ").strip()).lower() not in self.EXIT_WORDS:
                if question:
                    self.ask(chat_id, question)
        except httpx.ConnectError:
            print("\nCannot reach the API. Is the server running?")
        except KeyboardInterrupt:
            print("\nChat ended.")
        finally:
            self.client.close()


if __name__ == "__main__":
    ChatCLI().run()
