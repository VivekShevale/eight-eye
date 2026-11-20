from typing import TypeVar

from flask import request
from pydantic import BaseModel, ValidationError

SchemaType = TypeVar("SchemaType", bound=BaseModel)


class RequestValidationError(Exception):
    """Invalid client input, kept apart from ValidationErrors caused by server bugs."""

    def __init__(self, details: list[dict[str, str]]) -> None:
        super().__init__("Request validation failed.")
        self.details = details


class RequestUtils:
    """Validate request bodies and query strings with Pydantic (Flask doesn't do it itself)."""

    @classmethod
    def parse_body(cls, schema: type[SchemaType]) -> SchemaType:
        """Validate the JSON body against a schema."""
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise RequestValidationError([{"field": "body", "message": "Request body must be a JSON object."}])
        return cls.validate(schema, data, "body")

    @classmethod
    def parse_query(cls, schema: type[SchemaType]) -> SchemaType:
        """Validate the query string against a schema."""
        return cls.validate(schema, request.args.to_dict(), "query")

    @staticmethod
    def validate(schema: type[SchemaType], data: dict, location: str) -> SchemaType:
        """Run Pydantic validation and convert its errors to field details."""
        try:
            return schema.model_validate(data)
        except ValidationError as exc:
            details = [{"field": ".".join([location, *(str(part) for part in error["loc"])]), "message": error["msg"]} for error in exc.errors()]
            raise RequestValidationError(details) from exc
