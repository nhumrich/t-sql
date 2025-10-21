"""Row object - dict with attribute access support."""


class Row(dict):
    """A dict subclass that supports attribute-style access.

    Provides a nicer API for accessing row data while maintaining
    full dict compatibility.

    Example:
        row = Row({'id': 1, 'name': 'Alice'})
        print(row.id)        # 1 (attribute access)
        print(row['name'])   # Alice (dict access)
        row.age = 30         # Set via attribute
        print(row['age'])    # 30
    """

    def __getattr__(self, key: str):
        """Allow attribute-style access to dict keys."""
        try:
            return self[key]
        except KeyError:
            raise AttributeError(f"Row has no attribute {key!r}") from None

    def __setattr__(self, key: str, value):
        """Allow attribute-style setting of dict keys."""
        self[key] = value

    def __delattr__(self, key: str):
        """Allow attribute-style deletion of dict keys."""
        try:
            del self[key]
        except KeyError:
            raise AttributeError(f"Row has no attribute {key!r}") from None

    def __repr__(self) -> str:
        """Nice repr for debugging."""
        items = ', '.join(f'{k}={v!r}' for k, v in self.items())
        return f"Row({items})"
