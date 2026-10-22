"""Run an administration command with the same dotenv config as the services."""
import os
import sys
from dotenv import load_dotenv
load_dotenv('/root/robomark/shared/backend.env', override=True)
os.execvpe(sys.argv[1], sys.argv[1:], os.environ)
