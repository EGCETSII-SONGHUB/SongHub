from flask import Flask
from flask_mail import Mail

mail = Mail()


def init_feature(app: Flask) -> None:
    mail.init_app(app)
