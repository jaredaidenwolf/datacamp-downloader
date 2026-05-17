from colorama import init

from .env import load_env
from .session import Session

load_env()

# use Colorama to make Termcolor work on Windows too
init()

active_session = Session()
datacamp = active_session.datacamp
