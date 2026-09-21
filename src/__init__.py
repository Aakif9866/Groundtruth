"""Groundtruth: retrieval evaluation and regression harness."""
try:  # pick up a local .env (never committed); real environment variables take precedence
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv is a declared dependency; tolerate its absence
    pass
