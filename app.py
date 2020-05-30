'''
___app.py___
Main driver code for the website. Handles page routing, HTTP requests, and user login through Flask.
Also manages the connection to the database for storing location data and user data.
'''
import uuid
import sys
import MySQLdb.cursors
import smtplib, ssl 
import cred
from random import randrange
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



#__________CLASSES__________
class DB: # https://stackoverflow.com/questions/207981/how-to-enable-mysql-client-auto-re-connect-with-mysqldb
    def __init__(self):
        conn = None
    def connect(self):
        if local == False:
            self.conn =  MySQLdb.connect(
                         host='Group7.mysql.pythonanywhere-services.com',
                         user='Group7',
                         passwd=cred.paSQLpass,
                         database='Group7$project_2'
                         )
        else:
            self.conn =  MySQLdb.connect(port=3548,
                         host='ix-dev.cs.uoregon.edu',
                         user='cis422-group7',
                         password=cred.ixSQLpass,
                         db='project_1',
                         charset='utf8')

    def query(self, sql):
        self.conn.ping(True)
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql)
            self.conn.commit()
        except (AttributeError, MySQLdb.OperationalError):
            self.connect()
            cursor = self.conn.cursor()
            cursor.execute(sql)
            self.conn.commit()
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


class User(UserMixin): # Base login system derived from code here: https://flask-login.readthedocs.io/en/latest/
    def __init__(self, user, status, email):
        self.username = user[0].lower()
        self.password = user[1]
        self.id = user[2]
        self.status = status
        self.email = email

    def verify_password(self, password):
        if self.password is None:
            return False
        return check_password_hash(self.password, password)

    def get_id(self):
        return self.id

    def notify(self, lat, lng, date, time): # Email code based on https://realpython.com/python-send-email/
        message = """\
        Subject: Important Covid-19 Exposure Alert

        Someone you were in close proximity to over the last 14 days has tested positive for Covid-19. The encounter happened at (%s, %s) on %s at %s. Please respond accordingly. You can learn more here: https://www.cdc.gov/coronavirus/2019-ncov/index.html""" % (lat, lng, date, time)

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login("covid.alert.422@gmail.com", cred.emailPass)
            server.sendmail("covid.alert.422@gmail.com", self.email, message)
        return



#__________FLASK__________
app = Flask(__name__)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
app.secret_key = cred.secretKey
@login_manager.user_loader
def load_user(user_id):
    if user_id not in userObjects:
        return None
    return userObjects[user_id]



#__________FORMS__________
#TODO: Make a superclass for all of these forms to inherit from to reduce redundancy
class LoginForm(FlaskForm):
    username = StringField('user', validators=[DataRequired()])
    password = PasswordField('password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('log in')


class RegistrationForm(FlaskForm):
    username = StringField('user', validators=[DataRequired()])
    password = PasswordField('password', validators=[DataRequired()])
    email = StringField('email', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')


class DisplayForm(FlaskForm):
    username = StringField('user', validators=[DataRequired()])
    tab = BooleanField('Tab delimited output file')


class ReportForm(FlaskForm):
    username = StringField('user', validators=[DataRequired()])



#__________ROUTING__________
# Handles routing to the home page
@app.route("/")
@app.route("/index")
@login_required
def index():
    return render_template('location.html'), 200


@app.route('/display/', methods=('GET', 'POST'))
def display():
    # finds all data entries for a particular user ID
    form = DisplayForm()
    if form.validate_on_submit():
        username = form.username.data.lower()
        tab = form.tab.data
        print("Getting location data for: ", username)
        sql = "SELECT latitude, longitude, date, time, time_at_location FROM user_info WHERE name LIKE '%s';" % (username)
        results = db.get(sql)
        if results:
            if tab:
                txt = "User I.D.\tDate\tTime\tLatitude\tLongitude\tTime at Location\n"
                usr = get_user(username)
                for entry in results:
                    location = unsalt(entry[0], entry[1])
                    lat = location[0]
                    lng = location[1]
                    txt = txt + "%s\t%s\t%s\t%s\t%s\t%s\n" % (usr.id, entry[2], entry[3], lat+0.00175, lng+0.00175, entry[4])
                return Response(
                    txt,
                    mimetype="text/plain",
                    headers={"Content-disposition":
                             "attachment; filename=locations.txt"})
            else:
                csvList = ["lat,lng,name,color,note"]
                for entry in results:
                    location = unsalt(entry[0], entry[1])
                    lat = location[0]
                    lng = location[1]
                    csvList.append(",".join(map(str,[lat+0.00175, lng+0.00175, '', "ff0000", ' '.join(map(str,entry[2:]))])))
                csv = "\n".join(csvList)
                return Response(
                    csv,
                    mimetype="text/csv",
                    headers={"Content-disposition":
                             "attachment; filename=locations.csv"})
        else:
            emsg = "No user found. Check that you spelled the username correctly and try again."
            return render_template('display.html', form=form, msg=emsg)

    return render_template('display.html', form=form)


@app.route('/login/', methods=('GET', 'POST'))
def login():
    if current_user.is_authenticated: # If the user is already logged in, send them to the main page
        return render_template('location.html'), 200
    form = LoginForm()
    emsg = None
    if form.validate_on_submit():
        # assigns information received from website to variables
        username = form.username.data.lower()
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


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/register', methods=('GET', 'POST'))
def register():
    # store id with random index number
    form = RegistrationForm()
    if form.validate_on_submit():
        # Login and validate the user.
        # User should be an instance of your 'User' class
        username = form.username.data.lower()
        password = form.password.data
        email = form.email.data

        if get_user(username):
            emsg = "That username is taken. Try another one."
            return render_template('register.html', form=form, msg=emsg), 400
        else:
            newUser = create_user(username, generate_password_hash(password), email)
            sql = "INSERT INTO user_id VALUES ('%s', '%s', '%s', '%s', '%s')" % (newUser.id, username, newUser.password, 0, email) # 0 indicates that the user is not infected. They can change this if they are.
            db.query(sql)
            emsg = "You have successfully registered! You may now log in."
            return render_template('login.html', form=form, msg=emsg), 200 # Shouldn't this pass in the login form not the Register form?
    else:
        return render_template('register.html', form=form)


# Handles location send requests
@app.route('/send_location', methods=['POST'])
@login_required
def send():
    data = request.form.to_dict(flat=False) # Request form from website containing user information and create a dictionary using it
    date, time = data.get('date')[0], data.get('time')[0]
    sql = "SELECT latitude, longitude, date, time, time_at_location FROM user_info WHERE name LIKE '%s';" % (current_user.username)
    results = db.get(sql) # Query the database for entries from a particular user

    pastLat = pastLng = 0
    if results is (): # If no entries are found in the database (for new users)
        past = (0, 0, datetime.today().date(), timedelta(0, 86400), 0) # Create dummy location
    else:
        past = results[-1] # Select most recent entry
        loc = unsalt(past[0], past[1])
        pastLat, pastLng = loc[0], loc[1]

    if 'null' in data.get('lat')[0] or 'null' in data.get('lng')[0]: # Check to make sure that the latitude nad longitude received from the user are not null
        lati, longi = past[0], past[1]
    else:
        lati, longi = data.get('lat')[0], data.get('lng')[0]

    '''
    If the newly received location and the newest entry in the database are within a meter, calculate the time difference 
    between the newly received entry and the most recent entry in the database from that particular user. Since the time 
    sent from the website is a string and the time in the database is a timedelta, the time from the website is converted to 
    a datetime and the two are subtracted and then added to the time at loc. Otherwise location is different so time_at is 0 
    '''
    if abs(float(pastLat) - float(lati)) <= .00001 and abs(float(pastLng) - float(longi)) <= .00001:
        inter_time = time[0:2]+time[3:5] + time[6:8] # How to parse colon datetimes https://stackoverflow.com/questions/30999230/how-to-parse-timezone-with-colon
        data_dt = datetime.strptime(inter_time, '%H%M%S').time()
        past_time = (datetime.min + past[3]).time()
    
        difference = datetime.combine(datetime.today(), data_dt) - datetime.combine(datetime.today(), past_time) # Concept for difference based on https://stackoverflow.com/questions/9578906/easiest-way-to-combine-date-and-time-strings-to-single-datetime-object-using-pyt
        print(difference.total_seconds() % 3600)

        # Timedelta to minutes from https://stackoverflow.com/questions/14190045/how-do-i-convert-datetime-timedelta-to-minutes-hours-in-python/43965102
        time_at = int(past[4]) + (difference.total_seconds() % 3600)/60 # Make it a difference between date's time and past's time
        sql = "UPDATE user_info SET time_at_location = '%s' WHERE name LIKE '%s' ORDER BY date DESC, time DESC LIMIT 1;" % (time_at, current_user.username)
        db.query(sql) # Update time_at_location for the previous entry
    else: # The user moved more than a meter
        time_at = 0
        location = salt(lati, longi) # Salt location data before storing it in the DB
        saltLati, saltLongi = location[0], location[1]
        sql = "INSERT INTO user_info VALUES ('%s', '%s',  '%s',  '%s', '%s', '%s')" % (current_user.username, date, time, saltLati, saltLongi, time_at)
        db.query(sql) # Send new entry with all updated variables to the DB

    contactTrace(current_user.username, date, time, lati, longi) # Check if this entry is overlaps with any other users last entries

    return render_template('location.html'), 200


# Allows users to report that they've tested positive
@app.route('/report', methods=['GET', 'POST'])
@login_required
def report():
    form = ReportForm()
    if form.validate_on_submit():
        username = form.username.data.lower()
        infected = get_user(username)
        if not infected:
            emsg = "No user found. Check that you spelled the username correctly and try again."
            return render_template('report.html', form, msg=emsg)
        
        print("Updating user infected status for: ", username)
        infected.status = 1
        sql = "SELECT * FROM contacts WHERE personA LIKE '%s' OR personB LIKE '%s';" % (username, username)
        results = db.get(sql)

        if results:
            sql = "UPDATE user_id SET user_status = 1 WHERE name LIKE '%s';" % (username)
            db.query(sql)
            for contact in results:
                if contact[0] == username:
                    other = get_user(contact[1])
                else:
                    other = get_user(contact[0])
                other.notify(contact[4], contact[5], contact[2], contact[3])
                other.status = 2
                sql = "UPDATE user_id SET user_status = 2 WHERE name LIKE '%s';" % (other.username)
                db.query(sql)
            emsg = "Your status has been updated. Thank you."
            return render_template('report.html', form=form, msg=emsg)
        else:
            print("No users in contact with the infected user.")
            emsg = "Your status has been updated. Thank you."
            return render_template('report.html', form=form, msg=emsg)

    return render_template('report.html', form=form)



#__________ERROR PAGES__________
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



#__________HELPER FUNCTIONS__________
# Given a latitude and longitude it adds random numbers to specified positions to obscure the actual data
def salt(lat, lng):
    la, lo = floatTrunc(lat, 7), floatTrunc(lng, 7)
    laSum, loSum = int(la[-1]), int(lo[-1])
    laList, loList = list(la), list(lo)

    for i in range(len(laList)-1):
        if laList[i].isdigit():
            laList[i] = str((int(laList[i])+laSum)%10)

    for i in range(len(loList)-1):
        if loList[i].isdigit():
            loList[i] = str((int(loList[i])+loSum)%10)

    return ["".join(laList), "".join(loList)]


# Given a salted latitude and longitude, return the actual data
def unsalt(lat, lng):
    la, lo = str(lat), str(lng)
    laList, loList = list(la), list(lo)
    laSub, loSub = int(la[-1]), int(lo[-1])

    for i in range(len(laList)-1):
        if laList[i].isdigit():
            laList[i] = str((int(laList[i])+10-laSub)%10)
    
    for i in range(len(loList)-1):
        if loList[i].isdigit():
            loList[i] = str((int(loList[i])+10-loSub)%10)
    
    return [float("".join(laList)), float("".join(loList))]


def create_user(usr, pas, email, uid=None, status=0):
    if not uid:
        uid = uuid.uuid4()
    user = User([usr.lower(), pas, uid], status, email)
    userObjects[uid] = user
    return user


# Given a username, it returns a User object
def get_user(usr):
    usr = usr.lower()
    for user in userObjects.values():
        if user.username == usr:
            return user
    return None

# Takes a float or string float and truncates it to have 'deg' decimals
def floatTrunc(num, deg):
    if isinstance(num, float):
        num = str(num)
    numSplit = num.split('.')
    numSplit[1] = numSplit[1][:deg]
    num = ".".join(numSplit)
    return num


def contactTrace(name, date, time, lat, lng):
    lat1, lng1 = float(floatTrunc(lat, 5)), float(floatTrunc(lng, 5))
    sql = "SELECT name, latitude, longitude FROM user_info WHERE time_to_sec(timediff('%s', time)) < 500 AND datediff('%s', date) LIKE 0 AND name NOT LIKE '%s'" % (time, date, name)
    results = db.get(sql)
    contacts = []
    for entry in results:
        loc = unsalt(entry[1], entry[2])
        lat2, lng2 = float(floatTrunc(loc[0], 5)), float(floatTrunc(loc[1], 5))
        if abs(lat1-lat2) <= 0.00002 and abs(lng1-lng2) <= 0.00002: # Difference of 0.00002 in lat/long is 7.28346457 feet apart
            contacts.append(entry[0])
    saltLoc = salt(lat, lng)
    for contact in contacts:
        sql = "INSERT INTO contacts VALUES ('%s', '%s', '%s', '%s', '%s', '%s')" % (name, contact, date, time, saltLoc[0], saltLoc[1])
        db.query(sql)
    return 



#__________STARTUP__________
# TODO: How much of this can be moved to main?
local = False
if len(sys.argv) > 1:
    if sys.argv[1] == "local":
        print("Running on local...")
        local = True

db = DB()
db.connect()

userObjects = {}

results = db.get("SELECT * FROM user_id")
for user in results:
    create_user(user[1], user[2], user[4], user[0], user[3])



#__________MAIN__________
if __name__ == "__main__":
    if local == False:
        app.run(debug=False)
    else:
        app.run(debug=True,host='localhost')
