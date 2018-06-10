from flask_wtf import FlaskForm
from wtforms import StringField, DateField


class AddChildForm(FlaskForm):
    first_name = StringField('Imię:')
    last_name = StringField('Nazwisko:')
    date_of_birth = DateField('Data urodzenia:')