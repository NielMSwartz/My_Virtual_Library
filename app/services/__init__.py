"""Service layer: duplicate detection and external metadata providers."""


class MetadataError(Exception):
    """An external book-metadata provider could not fulfil a request."""
