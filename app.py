import datetime

from dateutil import relativedelta

from collections import namedtuple
from calendar import Calendar
import calendar
from functools import partial

from flask import Flask, render_template, url_for, request, make_response, redirect

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy_utils import ChoiceType
from sqlalchemy import func

from flask_wtf.csrf import CSRFProtect

from flask_security import Security, SQLAlchemyUserDatastore, \
    UserMixin, RoleMixin, login_required
from flask_login import LoginManager, current_user
from flask_principal import identity_loaded, Permission, RoleNeed, UserNeed

from config import Config
from forms import AddChildForm
from forms import AddNapForm
from forms import AddNightNapForm


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


children_users = db.Table('children_users',
                          db.Column('user_id', db.Integer(), db.ForeignKey('user.id'), primary_key=True),
                          db.Column('child_id', db.Integer(), db.ForeignKey('child.id'), primary_key=True))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(100))
    active = db.Column(db.Boolean)
    roles = db.relationship('Role', secondary=roles_users,
                            backref=db.backref('users', lazy='dynamic'))
    children = db.relationship('Child', secondary=children_users,
                               backref=db.backref('users', lazy='dynamic'))


class Child(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80))
    date_of_birth = db.Column(db.Date)
    naps = db.relationship('Nap', backref='child', lazy=True)
    night_naps = db.relationship('NightNap', backref='child', lazy=True)

    def __repr__(self):
        return f'<Child {self.first_name} {self.last_name}>'


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
    notes = db.Column(db.UnicodeText, nullable=True, default=None, info={'label': 'Notatki'})
    child_id = db.Column(db.Integer, db.ForeignKey('child.id'), nullable=False)

    def __repr__(self):
        return f'<Nap {self.id}>'


class NightNap(db.Model):
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    date = db.Column(db.Date, default=datetime.date.today(), nullable=False, unique=True, info={'label': 'Data'})
    wake_up = db.Column(db.Time, info={'label': 'Godzina rannego obudzenia'})
    fall_asleep = db.Column(db.Time, info={'label': 'Godzina uśnięica na noc'})
    child_id = db.Column(db.Integer, db.ForeignKey('child.id'), nullable=False)


user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore)


@app.route('/')
@login_required
def start():
    if request.cookies.get('child'):
        return redirect(url_for('daytime_naps'))
    return redirect(url_for('children'))


@app.route('/children')
@login_required
def children():
    children = User.query.filter(User.id == current_user.id).first().children
    return render_template('children.html', children=children)


@app.route('/set_child/<child_id>', methods=['GET', 'POST'])
def set_child(child_id):
    resp = make_response(redirect(url_for('daytime_naps')))
    resp.set_cookie('child', child_id)
    return resp


@app.route('/daytime_naps', methods=['GET'])
@login_required
def daytime_naps():
    if request.cookies.get('child') not in [str(child.id) for child in current_user.children]:
        return redirect(url_for('children'))
    today = datetime.date.today()
    naps = Nap.query.filter(Nap.cdate.like(f'%{today}%')).filter(Nap.child_id == request.cookies.get('child')).order_by(Nap.stime).all()
    return render_template('daytime_naps.html', today=today, naps=naps)


@app.route('/add_child', methods=['GET', 'POST'])
def add_child():
    form = AddChildForm()
    if form.validate_on_submit():
        child = Child(first_name=form.first_name.data, last_name=form.last_name.data, date_of_birth=form.date_of_birth.data)
        current_user.children.append(child)
        db.session.add(child)
        db.session.commit()
        return redirect(url_for('children'))
    return render_template('add_child.html', form=form)


@app.route('/add_nap', methods=['GET', 'POST'])
@login_required
def add_nap():
    form = AddNapForm()
    if form.validate_on_submit():
        nap = Nap(cdate=form.cdate.data, stime=form.stime.data, etime=form.etime.data, problems=form.problems.data, place=form.place.data, notes=form.notes.data, child_id=request.cookies.get('child'))
        db.session.add(nap)
        db.session.commit()
        return redirect(url_for('daytime_naps'))
    return render_template('add_nap.html', form=form)


@app.route('/add_nap_detailed', methods=['GET', 'POST'])
def add_nap_detailed():
    form = AddNapForm()
    if form.validate_on_submit():
        nap = Nap(cdate=form.cdate.data, stime=form.stime.data, etime=form.etime.data, problems=form.problems.data, place=form.place.data, notes=form.notes.data, child_id=request.cookies.get('child'))
        db.session.add(nap)
        db.session.commit()
        return redirect(url_for('daytime_naps'))
    return render_template('add_nap_detailed.html', form=form)


@app.route('/add_nightnap', methods=['GET', 'POST'])
@login_required
def add_nightnap():
    form = AddNightNapForm()
    if form.validate_on_submit():
        nap = NightNap(date=datetime.date.today(), wake_up=form.wake_up.data, fall_asleep=form.fall_asleep.data, child_id=request.cookies.get('child'))
        db.session.add(nap)
        db.session.commit()
        return redirect(url_for('daytime_naps'))
    return render_template('add_night_nap.html', form=form)


@app.route('/add_nightnap_detailed', methods=['GET', 'POST'])
@login_required
def add_nightnap_detailed():
    form = AddNightNapForm()
    if form.validate_on_submit():
        nap = NightNap(date=form.date.data, wake_up=form.wake_up.data, fall_asleep=form.fall_asleep.data, notes=form.notes.data, child_id=request.cookies.get('child'))
        db.session.add(nap)
        db.session.commit()
        return redirect(url_for('daytime_naps'))
    return render_template('add_night_nap_detailed.html', form=form)


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
        naps = Nap.query.filter(Nap.child_id == request.cookies.get('child')).filter(Nap.cdate == date).order_by(Nap.stime).all()
        night_sleep = NightNap.query.filter(NightNap.child_id==request.cookies.get('child')).filter(NightNap.date==date).first()
        try:
            wake_up = night_sleep.wake_up
            fall_asleep = night_sleep.fall_asleep
        except AttributeError:
            wake_up = None
            fall_asleep = None
        naps_amount = Nap.query.filter(Nap.child_id==request.cookies.get('child')).filter(Nap.cdate == date).count()
        naps_duration = datetime.timedelta(0)
        for i in range(len(naps)):
            duration = datetime.datetime.combine(datetime.date.min, naps[i].etime) \
                - datetime.datetime.combine(datetime.date.min, naps[i].stime)
            naps_duration += duration
            duration_string = ':'.join(str(duration).split(':')[:2])
            data['naps'].append({
                'date': naps[i].cdate,
                'stime': naps[i].stime,
                'etime': naps[i].etime,
                'problems': naps[i].problems.value,
                'place': naps[i].place.value,
                'notes': naps[i].notes,
                'duration': duration_string
            })
        summary = {
            'wake_up': wake_up,
            'fall_asleep': fall_asleep,
            'naps_amount': naps_amount,
            'naps_duration': ':'.join(str(naps_duration).split(':')[:2])
        }
        return render_template('day_modal.html', data=data, summary=summary)
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
        naps = Nap.query.filter(Nap.child_id == request.cookies.get('child')).filter(func.extract('month', Nap.cdate) == date.month).order_by(Nap.stime).all()
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
        nap_in_day = Nap.query.filter(Nap.child_id==request.cookies.get('child')).filter(func.extract('day', Nap.cdate) == day).all()
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