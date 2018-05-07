import os

class Config():
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'kafjhk3fdsak369844%#2kghjg342kj565kj@#$^k'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///test1.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

