from abc import ABC, abstractmethod
from typing import Any


class TypeProcessor(ABC):
    """Base class for custom column type transformations.

    Type processors enable automatic value transformation when reading from
    and writing to the database, similar to SQLAlchemy's TypeDecorator.

    Processors can be stateful and accept configuration in __init__:

        class EncryptedString(TypeProcessor):
            def __init__(self, key):
                self.key = key

            def process_bind_param(self, value):
                return encrypt(value, self.key) if value is not None else None

            def process_result_value(self, value):
                return decrypt(value, self.key) if value is not None else None

    Example usage with Table:

        class User(Table, metadata=metadata):
            id = SAColumn(Integer, primary_key=True)
            ssn = SAColumn(String(255), type_processor=EncryptedString(key=MY_KEY))

        # Automatic encryption on insert
        User.insert(ssn="123-45-6789")

        # Manual decryption on select
        query = User.select().where(User.id == 1)
        rows = await conn.fetch(*query.render())
        users = query.map_results(rows)  # ssn automatically decrypted
    """

    @abstractmethod
    def process_bind_param(self, value: Any) -> Any:
        """Transform Python value to database value.

        Called when inserting, updating, or comparing values in WHERE clauses.
        NULL values (None) are passed through - the processor decides how to handle them.

        Args:
            value: The Python value to transform

        Returns:
            The transformed value to send to the database
        """
        pass

    @abstractmethod
    def process_result_value(self, value: Any) -> Any:
        """Transform database value to Python value.

        Called when reading values from query results via map_results().
        NULL values (None) are passed through - the processor decides how to handle them.

        Args:
            value: The database value to transform

        Returns:
            The transformed Python value
        """
        pass


__all__ = ['TypeProcessor']
