import json
from sqlalchemy.types import TypeDecorator, TEXT
from sqlalchemy.dialects.postgresql import ARRAY # Keep for non-SQLite

class JsonEncodedList(TypeDecorator):
    """Represents an immutable structure as a json-encoded string.

    Usage::

        JsonEncodedList(255)

    """

    impl = TEXT
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value

    def copy(self, **kw):
        return JsonEncodedList(self.impl.length)

# For other dialects (like PostgreSQL), ARRAY is fine.
# We'll choose which type to use in the model based on the dialect. 