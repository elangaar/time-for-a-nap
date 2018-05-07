import datetime
from calendar import Calendar

from flask import Flask, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy_utils import ChoiceType

from flask_wtf.csrf import CSRFProtect
from flask_wtf import Form
from wtforms_alchemy import ModelForm

from config import Config

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)
csrf = CSRFProtect(app)
csrf.init_app(app)


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

    def __repr__(self):
        return f'<Nap {self.id}>'



class NapForm(ModelForm, Form):
    class Meta:
        model = Nap


@app.route('/', methods = ['GET'])
def main():
    today = datetime.date.today()
    naps = Nap.query.filter(Nap.cdate.like(f'%{today}%')).order_by(Nap.stime).all()
    return render_template('daytime_naps.html', today=today, naps=naps)


@app.route('/add_nap', methods=['GET', 'POST'])
def add_nap():
    form = NapForm()
    if form.validate_on_submit():
        nap = Nap(stime=form.stime.data, etime=form.etime.data, problems=form.problems.data, place=form.place.data)
        db.session.add(nap)
        db.session.commit()
        return redirect(url_for('main'))
    return render_template('add_nap.html', form=form)


@app.route('/calendar')
def calendar():
    today = datetime.date.today()
    cal = Calendar()
    mdays = cal.monthdayscalendar(today.year, today.month)
    naps = Nap.query.filter_by().order_by(Nap.stime).all()
    weeks = []
    for week in mdays:
        days = []
        for d in week:
            day = []
            if d != 0:
                day.append(d)
                ns = []
                for nap in naps:
                    if nap.cdate.day == d:
                        ns.append(nap)
                day.append(ns)
            else:
                day.append(d)
            days.append(day)
        weeks.append(days)
    return render_template('calendar.html', mdays=mdays, naps_data=weeks)


@app.route('/statistics')
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
        nap_in_day = [x for x in Nap.query.all() if x.cdate.day == day]
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