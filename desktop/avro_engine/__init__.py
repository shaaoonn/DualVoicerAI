# avro_engine package
"""Vendored OmicronLab Avro Phonetic engine.

Loads the official Avro Phonetic rules (avrophonetic.json) and applies
them with the same algorithm as the original Avro Keyboard. Produces
output identical to typing in real Avro on Windows.

Rules file: avrophonetic.json — sourced from OpenBangla-Keyboard's
data/ directory, which preserves Mehdi Hasan Khan / OmicronLab's
original phonetic rules verbatim.

License: The phonetic rules are Mehdi Hasan Khan / OmicronLab's work,
released under MPL-1.1 (file-level copyleft). See LICENSE-MPL-1.1.txt
in this folder. The engine code below is our own implementation,
written from scratch against the JSON schema — no GPL-licensed
OpenBangla code is reused.
"""
from .engine import AvroEngine, parse  # noqa: F401
