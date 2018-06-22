from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField
from wtforms.fields.html5 import DateField
from wtforms_components import TimeField, SelectField


class AddChildForm(FlaskForm):
    first_name = StringField('Imię:')
    last_name = StringField('Nazwisko:')
    date_of_birth = DateField('Data urodzenia:')


class AddNapForm(FlaskForm):
    CHOICES_PROBLEMS = [
        ('OK', 'Wszystko OK'),
        ('--', 'Płacz'),
        ('/', 'Krzyk'),
    ]
    CHOICES_PLACES = [
        ('lozeczko', 'Łóżeczko'),
        ('spacer', 'Spacer'),
        ('rece', 'Ręce')
    ]
    cdate = DateField('Data:')
    stime = TimeField('Początek drzemki:')
    etime = TimeField('Koniec drzemki:')
    problems = SelectField('Problemy:', choices=CHOICES_PROBLEMS)
    place = SelectField('Miejsce uśnięcia:', choices=CHOICES_PLACES)
    notes = TextAreaField('Notatki:')


class AddNightNapForm(FlaskForm):
    date = DateField('Data:')
    wake_up = TimeField('Godzina rannego obudzenia:')
    fall_asleep = TimeField('Godzina uśnięcia na noc:')
    notes = TextAreaField('Notatki:')

