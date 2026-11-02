"""Versioned identities and graph contract. Paths and retrieval time never enter IDs."""
from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json

SCHEMA_VERSION = '1'
PARSER_VERSION = 'conservative-2'

class NodeKind(StrEnum):
    ARTIFACT = 'Artifact'
    WITNESS = 'Witness'
    COMPOSITION = 'Composition'
    PASSAGE = 'Passage'
    SEQUENCE = 'SequenceVersion'
    LINE = 'Line'
    OCCURRENCE = 'SignOccurrence'
    WORD = 'WordToken'
    LEMMA = 'Lemma'
    SENSE = 'Sense'
    TRANSLATION = 'TranslationSegment'
    SOURCE = 'SourceRecord'
    SIGN = 'SignType'
    CLAIM = 'Claim'

@dataclass(frozen=True)
class SourceLocator:
    """JSON pointer plus UTF-8 offsets in its decoded string, not JSON-file offsets."""
    pointer: str
    start_byte: int | None = None
    end_byte: int | None = None


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity(kind: str, *parts: object) -> str:
    return kind + ':' + digest(canonical(parts).encode())[:32]


EDGE_TYPES = {
    'HAS_SEQUENCE': ('Witness', 'SequenceVersion'),
    'HAS_LINE': ('SequenceVersion', 'Line'),
    'HAS_OCCURRENCE': ('Line', 'SignOccurrence'),
    'NEXT': ('SignOccurrence', 'SignOccurrence'),
    'NEXT_LINE': ('Line', 'Line'),
    'ON_ARTIFACT': ('Witness', 'Artifact'),
    'MAPS_TO_SIGN': ('SignOccurrence', 'SignType'),
    'HAS_WORD': ('SequenceVersion', 'WordToken'),
    'HAS_SIGN': ('WordToken', 'SignOccurrence'),
    'LEMMATIZED_AS': ('WordToken', 'Lemma'),
    'HAS_SENSE': ('Lemma', 'Sense'),
    'TRANSLATES': ('TranslationSegment', 'Passage'),
}
