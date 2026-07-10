from asgiref.wsgi import WsgiToAsgi
from dotenv import load_dotenv

from app import create_app


load_dotenv()

flask_app = create_app()
app = WsgiToAsgi(flask_app)
