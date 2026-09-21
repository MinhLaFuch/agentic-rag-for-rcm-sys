from package.utils.path._paths import PathConfig


DATA_ROOT = PathConfig(__file__)

RAW_DIR = DATA_ROOT.raw()
PROCESSED_DIR = DATA_ROOT.processed()

AMAZON_RAW_DIR = RAW_DIR / "amazon"
AMAZON_PROCESSED_DIR = PROCESSED_DIR / "amazon"