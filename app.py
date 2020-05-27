'''
___app.py___
Main driver code for the website. Handles page routing, HTTP requests, and user login through Flask.
Also manages the connection to the database for storing location data and user data.
'''
import uuid

import MySQLdb.cursors
from flask import Flask, request, Response
from flask import redirect, flash
from flask import render_template, url_for
from flask_login import LoginManager
from flask_login import UserMixin
from flask_login import current_user, login_required
from flask_login import logout_user, login_user
from flask_wtf.form import FlaskForm
from itsdangerous import (TimedJSONWebSignatureSerializer \
                              as Serializer, BadSignature, \
                          SignatureExpired)
import csv
from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash
from wtforms import PasswordField, BooleanField, StringField, SubmitField
from wtforms.validators import DataRequired
from datetime import *
from math import isclose

app = Flask(__name__)

app.secret_key = 'abc'
class DB: # https://stackoverflow.com/questions/207981/how-to-enable-mysql-client-auto-re-connect-with-mysqldb
    def __init__(self):
        conn = None

    def connect(self):
        self.conn = MySQLdb.connect(port=3548,
                     host='ix-dev.cs.uoregon.edu',
                     user='cis422-group7',
                     password='Group7',
                     db='project_1',
                     charset='utf8')

    def query(self, sql):
        self.conn.ping(True)
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql)
        except (AttributeError, MySQLdb.OperationalError):
            self.connect()
            cursor = self.conn.cursor()
            cursor.execute(sql)
        return cursor

    def get(self, sql):
        results = None
        try:
            self.conn.query(sql)
            if self.conn:
                r = self.conn.store_result()
                results = r.fetch_row(maxrows=0)
        except (AttributeError, MySQLdb.OperationalError):
            self.connect()
            self.conn.query(sql)
            if self.conn:
                r = self.conn.store_result()
                results = r.fetch_row(maxrows=0)
        return results

db = DB()
db.connect() 

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
userObjects = {}

# Handles routing to the home page
@app.route("/")
@app.route("/index")
@login_required
def index():
    return render_template('location.html'), 200

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

def create_user(usr, pas, uid=None):
    if not uid:
        uid = uuid.uuid4()
    user = User([usr, pas, uid])
    userObjects[uid] = user
    return user

def get_user(usr):
    for user in userObjects.values():
        if user.username == usr:
            return user
    return None


class User(UserMixin): # Base login system derived from code here: https://flask-login.readthedocs.io/en/latest/
    def __init__(self, user):
        self.username = user[0]
        self.password = user[1]
        self.id = user[2]

    def verify_password(self, password):
        if self.password is None:
            return False
        return check_password_hash(self.password, password)

    def get_id(self):
        return self.id


@login_manager.user_loader
def load_user(user_id):
    if user_id not in userObjects:
        return None
    return userObjects[user_id]

results = db.get("SELECT * FROM user_id")
for user in results:
    create_user(user[1], user[2], user[0])

class LoginForm(FlaskForm):
    username = StringField('user', validators=[DataRequired()])
    password = PasswordField('password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('log in')


class RegistrationForm(FlaskForm):
    username = StringField('user', validators=[DataRequired()])
    password = PasswordField('password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')


class DisplayForm(FlaskForm):
    username = StringField('user', validators=[DataRequired()])
    tab = BooleanField('Tab delimited output file')


@app.route('/display/', methods=('GET', 'POST'))
def display():
    # finds all data entries for a particular user ID
    form = DisplayForm()
    if form.validate_on_submit():
        username = form.username.data

        tab = form.tab.data
        
        print("Getting location data for: ", username)

        sql = "SELECT latitude, longitude, date, time, time_at_location FROM user_info WHERE user_id LIKE '%s';" % (username)
        results = db.get(sql)
        if results:
            if tab:
                txt = "User I.D.\tDate\tTime\tLatitude\tLongitude\tTime at Location\n"
                usr = get_user(username)
                for entry in results:
                    txt = txt + "%s\t%s\t%s\t%s\t%s\t%s\n" % (usr.id, entry[2], entry[3], entry[0]+0.00175, entry[1]+0.00175, entry[4])
                return Response(
                    txt,
                    mimetype="text/plain",
                    headers={"Content-disposition":
                             "attachment; filename=locations.txt"})
            else:
                csvList = ["lat,lng,name,color,note"]
                for entry in results:
                    csvList.append(",".join(map(str,[entry[0]+0.00175, entry[1]+0.00175, '', "ff0000", ' '.join(map(str,entry[2:]))])))
                csv = "\n".join(csvList)
                return Response(
                    csv,
                    mimetype="text/csv",
                    headers={"Content-disposition":
                             "attachment; filename=locations.csv"})
        else:
            emsg = "No user found. please regiser"
            return render_template('login.html', msg=emsg)

    return render_template('display.html', form=form)


@app.route('/login/', methods=('GET', 'POST'))
def login():
    form = LoginForm()
    emsg = None
    if form.validate_on_submit():
        # assigns information received from website to variables
        username = form.username.data
        password = form.password.data
        remember = form.remember_me.data
        user = get_user(username)

        if user:
            if user.verify_password(password):
                if remember:
                    login_user(user, remember=True)
                else:
                    login_user(user)
                return render_template('location.html', form=form, username=username)
            else:
                emsg = "Error: Password incorrect."
                flash(emsg)
                return render_template('login.html', form=form, msg=emsg)
        else:
            emsg = "No user found. Please regiser if you have not."
            return render_template('login.html', form=form, msg=emsg)
    else:
        return render_template('login.html', form=form)


@app.route('/register', methods=('GET', 'POST'))
def register():
    # store id with random index number
    form = RegistrationForm()
    if form.validate_on_submit():
        # Login and validate the user.
        # User should be an instance of your 'User' class
        username = form.username.data
        password = form.password.data

        if get_user(username):
            emsg = "That username is taken. Try another one."
            return render_template('register.html', form=form, msg=emsg), 400
        else:
            newUser = create_user(username, generate_password_hash(password))
            sql = "INSERT INTO user_id VALUES ('%s', '%s', '%s')" % (newUser.id, username, newUser.password)
            db.query(sql)
            emsg = "You have successfully registered! You may now log in."
            return render_template('login.html', form=form, msg=emsg), 200
    else:
        return render_template('register.html', form=form)


# Handles location send requests
@app.route('/send_location', methods=['POST'])
@login_required
def send():
    # request form from website containing user information and create a dictionary using it
    data = request.form.to_dict(flat=False)
    # query the database for entries from a particular user
    sql = "SELECT latitude, longitude, date, time, time_at_location FROM user_info WHERE user_id LIKE '%s';" % (current_user.username)
    # select most recent entry
    results = db.get(sql)

    # create a dummy location if no entries are found in the database (for new users)
    if results is ():
        # create dummy location
        past = (0, 0, datetime.today().date(), timedelta(0, 86400), 0)
    else:
        past = results[-1]

    # checks to make sure that the latitude nad longitude information received from the user is not null
    if 'null' in data.get('lat')[0] or 'null' in data.get('lng')[0]:
        lati = past[0]
        longi = past[1]
    else:
        lati = data.get('lat')[0]
        longi = data.get('lng')[0]
    u_id = current_user.username
    date = data.get('date')[0]
    time = data.get('time')[0]

    # if the newly received location and the newest entry in the database are within a meter
    # Calculates the time difference between the newly received entry
    # and the most recent entry in the database from that particular user
    # since the time sent from the website is a string and the time in the database is a timedelta,
    # the time from the website is converted to a datetime and the two are subtracted and then added to the time at loc
    # otherwise sets time_at to 0 as location is different
    if abs(float(past[0]) - float(lati)) <= .00001 and abs(float(past[1]) - float(longi)) <= .00001:
        # src on how to parse colon datetimes https://stackoverflow.com/questions/30999230/how-to-parse-timezone-with-colon
        inter_time = time[0:2]+time[3:5] + time[6:8]
        data_dt = datetime.strptime(inter_time, '%H%M%S').time()
        past_time = (datetime.min + past[3]).time()
        # concept for difference based on https://stackoverflow.com/questions/9578906/easiest-way-to-combine-date-and-time-strings-to-single-datetime-object-using-pyt
        difference = datetime.combine(datetime.today(), data_dt) - datetime.combine(datetime.today(), past_time)
        print(difference.total_seconds() % 3600)

        #timedelta to minutes src https://stackoverflow.com/questions/14190045/how-do-i-convert-datetime-timedelta-to-minutes-hours-in-python/43965102
        time_at = int(past[4]) + (difference.total_seconds() % 3600)/60 # make it a difference between date's time and past's time
        TSI = 5
    else:
        time_at = 0
        TSI = 5
    # send new entry with all updated variables to the
    sql = "INSERT INTO user_info VALUES ('%s', '%s',  '%s',  '%s', '%s', '%s', '%s')" % (u_id, date, time, lati, longi, time_at, TSI)
    db.query(sql)

    return render_template('location.html'), 200


# Error handling routing
@app.errorhandler(404)
def error_404(error):
    return render_template('404.html'), 404


@app.errorhandler(403)
def error_403(error):
    return render_template('403.html'), 403


@app.errorhandler(401)
def error_401(error):
    return render_template('401.html'), 401


@app.errorhandler(400)
def error_400(error):
    return render_template('400.html'), 400


if __name__ == "__main__":
    app.run(debug=True)  