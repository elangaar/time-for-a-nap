import datetime
import json

from dateutil import relativedelta

from collections import namedtuple
from calendar import Calendar
import calendar
from functools import partial

from flask import Flask, render_template, redirect, url_for, request, jsonify

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy_utils import ChoiceType
from sqlalchemy import func

from flask_wtf.csrf import CSRFProtect
from flask_wtf import Form
from wtforms_alchemy import ModelForm

from flask_security import Security, SQLAlchemyUserDatastore, \
    UserMixin, RoleMixin, login_required
from flask_login import LoginManager, current_user
from flask_principal import identity_loaded, Permission, RoleNeed, UserNeed

from config import Config

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)
csrf = CSRFProtect(app)
csrf.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(id):
    return User.query.get(id)


NapMainlNeed = namedtuple('nap_main', ['method', 'value'])
ShowNapMainNeed = partial(NapMainlNeed, 'show')

class ShowNapMainPermission(Permission):
    def __init__(self, nap_id):
        need = NapMainlNeed(str(nap_id))
        super(ShowNapMainPermission, self).__init__(need)

@identity_loaded.connect_via(app)
def on_identity_loaded(sender, identity):
    identity.user = current_user
    if hasattr(current_user, 'id'):
        identity.provides.add(UserNeed(current_user.id))
    if hasattr(current_user, 'roles'):
        for role in current_user.roles:
            identity.provides.add(RoleNeed(role.name))
    if hasattr(current_user, 'naps'):
        for nap in current_user.naps:
            identity.provides.add(ShowNapMainNeed(str(nap.id)))


roles_users = db.Table('roles_users',
                        db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
                        db.Column('role_id', db.Integer(), db.ForeignKey('role.id')))


class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)


class User(db.Model, UserMixin):
    id = db.Column(db.Integer(), primary_key=True)
    email = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(100))
    active = db.Column(db.Boolean())
    roles = db.relationship('Role', secondary=roles_users,
                            backref=db.backref('users', lazy='dynamic'))
    naps = db.relationship('Nap', backref='user', lazy=True)


class Nap(db.Model):
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
    __tablename__= 'nap'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    cdate = db.Column(db.Date, default=datetime.datetime.today())
    stime = db.Column(
        db.Time,
        nullable=False,
        info={'label': 'Początek drzemki'}
    )
    etime = db.Column(
        db.Time,
        nullable=False,
        info={'label': 'Koniec drzemki'}
    )
    problems = db.Column(ChoiceType(CHOICES_PROBLEMS), info={'label': 'Problemy'})
    place = db.Column(ChoiceType(CHOICES_PLACES), info={'label': 'Miejsce'})
    notes = db.Column(db.UnicodeText, nullable=True, info={'label': 'Notatki'})
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<Nap {self.id}>'


user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore)

class NapForm(ModelForm, Form):
    class Meta:
        model = Nap


@app.route('/', methods = ['GET'])
@login_required
def daytime_naps():
    today = datetime.date.today()
    naps = Nap.query.filter(Nap.cdate.like(f'%{today}%')).filter_by(user_id=current_user.id).order_by(Nap.stime).all()
    return render_template('daytime_naps.html', today=today, naps=naps)


@app.route('/add_nap', methods=['GET', 'POST'])
@login_required
def add_nap():
    form = NapForm()
    if form.validate_on_submit():
        nap = Nap(stime=form.stime.data, etime=form.etime.data, problems=form.problems.data, place=form.place.data, notes=form.notes.data, user_id=current_user.id)
        db.session.add(nap)
        db.session.commit()
        return redirect(url_for('daytime_naps'))
    return render_template('add_nap.html', form=form)

def get_day_month_year(date):
    day = date.day
    month = calendar.month_name[date.month]
    year = date.year
    data = {
        'day': day,
        'month': month,
        'year': year
    }
    return data


@app.route('/calendar')
@login_required
def month_calendar():
    if request.args.get('day') and request.args.get('month_year'):
        day = request.args.get('day')
        month_year = request.args.get('month_year')
        date = datetime.datetime.strptime(str(day) + ' ' + month_year, '%d %B %Y').date()
        date_month_full = date.strftime('%d %B %Y')
        data = {
            'date': date_month_full,
            'naps': []
        }
        naps = Nap.query.filter_by(user_id=current_user.id).filter(Nap.cdate == date).order_by(Nap.stime).all()
        for i in range(len(naps)):
            duration = datetime.datetime.combine(datetime.date.min, naps[i].etime) \
                - datetime.datetime.combine(datetime.date.min, naps[i].stime)
            duration_string = ':'.join(str(duration).split(':')[:2])
            data['naps'].append({
                'date': naps[i].cdate.strftime('%d-%m-%Y'),
                'stime': naps[i].stime.strftime('%H:%M'),
                'etime': naps[i].etime.strftime('%H:%M'),
                'problems': naps[i].problems.value,
                'place': naps[i].place.value,
                'notes': naps[i].notes,
                'duration': duration_string
            });
        return render_template('day_modal.html', data=data)
    else:
        today = datetime.date.today()
        if request.args.get('date') is not None:
            date = datetime.datetime.strptime(request.args.get('date'), '%B %Y')
            if request.args.get('skip') == 'prev':
                date = date - relativedelta.relativedelta(months=1)
            elif request.args.get('skip') == 'next':
                date = date + relativedelta.relativedelta(months=1)
        else:
            date = datetime.date.today()
        cal = Calendar()
        month_year = get_day_month_year(date)
        mdays = cal.monthdayscalendar(date.year, date.month)
        naps = Nap.query.filter_by(user_id=current_user.id).filter(func.extract('month', Nap.cdate) == date.month).order_by(Nap.stime).all()
        weeks = []
        for week in mdays:
            days = []
            for d in week:
                day = []
                if d != 0:
                    date_day = datetime.date(date.year, date.month, d)
                    day.append(date_day)
                    ns = []
                    for nap in naps:
                        if nap.cdate.day == date_day.day:
                            ns.append(nap.problems.code)
                    day.append(ns)
                else:
                    day.append(d)
                days.append(day)
            weeks.append(days)
        if request.is_xhr:
            data = {
                'naps_data': weeks,
                'month_year': month_year,
                'date': date,
                'today': today
            }
            return render_template('month.html', naps_data=weeks, month_year=month_year, date=date, today=today)
        return render_template('calendar.html', naps_data=weeks, month_year=month_year, date=date, today=today)


@app.route('/statistics')
@login_required
def statistics():
    today = datetime.date.today()
    cal = Calendar()
    mweeks = cal.monthdayscalendar(today.year, today.month)
    mdays = []
    for week in mweeks:
        for d in week:
            if d > datetime.date.today().day:
                break
            mdays.append(d)
    naps_number = []
    naps_total_time = []
    for day in mdays:
        nap_in_day = [x for x in Nap.query.filter_by(user_id=current_user.id).all() if x.cdate.day == day]
        naps_number.append((day, len(nap_in_day)))
        naps_total_time.append(
                (day, sum([
                    (datetime.datetime.combine(datetime.date.today(), x.etime) -
                    datetime.datetime.combine(datetime.date.today(), x.stime)).total_seconds()/60
                    for x in nap_in_day])
                 )
        )
    return render_template('statistics.html', naps_number=naps_number, naps_total_time=naps_total_time)


if __name__ == "__main__":
    app.run(debug=True)