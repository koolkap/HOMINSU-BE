from asgiref.wsgi import WsgiToAsgi
from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402


flask_app = create_app()
app = WsgiToAsgi(flask_app)
