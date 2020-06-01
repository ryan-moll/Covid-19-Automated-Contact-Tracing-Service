"""
___app.py___
Main driver code for the website. Handles page routing, HTTP requests, and user login through Flask.
Also manages the connection to the database for storing location data and user data.
"""
import uuid
import sys
import MySQLdb.cursors
import smtplib, ssl
import cred
from flask import Flask, request, Response, redirect, flash, render_template, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, logout_user, login_user
from flask_wtf.form import FlaskForm
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import PasswordField, BooleanField, StringField, SubmitField
from wtforms.validators import DataRequired
from datetime import *


###################################################
#                     CLASSES
###################################################

class DB:  # https://stackoverflow.com/questions/207981/how-to-enable-mysql-client-auto-re-connect-with-mysqldb
    def __init__(self):
        conn = None

    def connect(self):
        if not local:
            self.conn = MySQLdb.connect(
                        host='Group7.mysql.pythonanywhere-services.com',
                        user='Group7',
                        passwd=cred.paSQLpass,
                        database='Group7$project_2'
                        )
        else:
            self.conn = MySQLdb.connect(port=3548,
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


class User(UserMixin):  # Base login system derived from code here: https://flask-login.readthedocs.io/en/latest/
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


###################################################
#                      FLASK
###################################################

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


###################################################
#                      FORMS
###################################################

# most basic form version that is inherited by other form versions
class Form(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])


class UserForm(Form):
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')


class LoginForm(UserForm):
    submit = SubmitField('log in')


class RegistrationForm(UserForm):
    email = StringField('Email', validators=[DataRequired()])


class DisplayForm(Form):
    tab = BooleanField('Tab delimited output file')


###################################################
#                     ROUTING
###################################################

# Handles routing to the home page
@app.route("/")
@app.route("/index")
@login_required
def index():
    return render_template('location.html'), 200


# finds and returns all data entries for a particular user ID
@app.route('/display/', methods=('GET', 'POST'))
def display():
    form = DisplayForm()
    if form.validate_on_submit():  # Checks to see if a valid form is received from display.html
        username = form.username.data.lower()
        tab = form.tab.data
        # Pulls all location entries tied the submitted username from the database
        sql = "SELECT latitude, longitude, date, time, time_at_location FROM user_info WHERE name LIKE '%s';" % (username)
        results = db.get(sql)
        if results:  # If any entries are found the requested user
            # Two versions of files can be returned: tab delimited or csv formatted
            if tab:  # User requested Tab delimited output file
                txt = "User I.D.\tDate\tTime\tLatitude\tLongitude\tTime at Location\n"
                usr = get_user(username)
                # Create a string of all entries of the user that were found in the database
                for entry in results:
                    location = unsalt(entry[0], entry[1])
                    lat = location[0]
                    lng = location[1]
                    txt = txt + "%s\t%s\t%s\t%s\t%s\t%s\n" % (usr.id, entry[2], entry[3], lat+0.00175, lng+0.00175, entry[4])
                # Convert that string to a text file and return it to the user
                return Response(
                    txt,
                    mimetype="text/plain",
                    headers={"Content-disposition":
                             "attachment; filename=locations.txt"})
            else:  # User requested CSV formatted output file
                csvList = ["lat,lng,name,color,note"]
                # Create a list of strings of all entries of the user that were found in the database
                for entry in results:
                    location = unsalt(entry[0], entry[1])
                    lat = location[0]
                    lng = location[1]
                    csvList.append(",".join(map(str,[lat+0.00175, lng+0.00175, '', "ff0000", ' '.join(map(str,entry[2:]))])))
                csv = "\n".join(csvList)  # Turn that list of strings into a single string
                # Convert that string to a text file and return it to the user
                return Response(
                    csv,
                    mimetype="text/csv",
                    headers={"Content-disposition":
                             "attachment; filename=locations.csv"})
        else:  # There was no user with the given username
            emsg = "No user found. Check that you spelled the username correctly and try again."
            flash(emsg)
            return render_template('display.html', form=form)

    return render_template('display.html', form=form)


# Handles the user login page and logs in users
@app.route('/login/', methods=('GET', 'POST'))
def login():
    if current_user.is_authenticated:  # If the user is already logged in, send them to the main page
        return render_template('location.html'), 200
    form = LoginForm()
    if form.validate_on_submit():  # Otherwise check to see if login.html sent a form to app.py
        # Assign information received from login.html to variables
        username = form.username.data.lower()
        password = form.password.data
        remember = form.remember_me.data
        user = get_user(username)

        if user:  # There is an existing user with the provided username
            if user.verify_password(password):  # The provided password is correct
                if remember:  # The user checked 'remember me'
                    login_user(user, remember=True)
                else:  # The user did not check 'remember me'
                    login_user(user)
                return render_template('location.html', username=username)
            else:  # The provided password is incorrect
                emsg = "Error: Password incorrect."
                flash(emsg)
                return render_template('login.html', form=form)
        else:  # There is no existing user with the provided username
            emsg = "No user found with that username. Please regiser if you have not."
            flash(emsg)
            return render_template('login.html', form=form)
    else:
        return render_template('login.html', form=form)


# Handles user log out
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))  # Once the user is logged out, redirect them to the log in screen


# Handles user registration
@app.route('/register', methods=('GET', 'POST'))
def register():
    form = RegistrationForm()
    if form.validate_on_submit():  # Checks to see if a valid form is received from register.html
        username = form.username.data.lower()
        password = form.password.data
        email = form.email.data

        if get_user(username):  # There is an existing user with the provided username
            emsg = "That username is taken. Try another one."
            flash(emsg)
            return render_template('register.html', form=form), 400
        else:  # The username is available
            newUser = create_user(username, generate_password_hash(password), email)  # Create a new user object with the given info
            sql = "INSERT INTO user_id VALUES ('%s', '%s', '%s', '%s', '%s')" % (newUser.id, username, newUser.password, 0, email) # 0 indicates that the user is not infected. They can change this if they are.
            db.query(sql)  # Add the new user to the database
            emsg = "You have successfully registered! You may now log in."
            flash(emsg)
            form = LoginForm()
            return render_template('login.html', form=form), 200  # Direct the user to the login page
    else:
        return render_template('register.html', form=form)


# Handles location send requests
@app.route('/send_location', methods=['POST'])
@login_required
def send():
    data = request.form.to_dict(flat=False) # Request form from website containing user information and create a dictionary using it
    date, time = data.get('date')[0], data.get('time')[0]
    sql = "SELECT latitude, longitude, date, time, time_at_location FROM user_info WHERE name LIKE '%s';" % (current_user.username)
    results = db.get(sql)  # Query the database for entries from the specified user

    pastLat = pastLng = 0
    if results is ():  # If no entries are found in the database (for new users)
        past = (0, 0, datetime.today().date(), timedelta(0, 86400), 0) # Create dummy location
    else:
        past = results[-1]  # Select most recent entry
        loc = unsalt(past[0], past[1])
        pastLat, pastLng = loc[0], loc[1]

    if 'null' in data.get('lat')[0] or 'null' in data.get('lng')[0]:  # Check to make sure that the latitude and longitude received from the user are not null
        lati, longi = past[0], past[1]  # If they are just reuse the location values from the last entry
    else:
        lati, longi = data.get('lat')[0], data.get('lng')[0]

    """
    If the newly received location and the newest entry in the database are within a meter, calculate the time difference 
    between the newly received entry and the most recent entry in the database from that particular user. Since the time 
    sent from the website is a string and the time in the database is a timedelta, the time from the website is converted to 
    a datetime and the two are subtracted and then added to the time at loc. Otherwise location is different so time_at is 0 
    """
    if abs(float(pastLat) - float(lati)) <= .00001 and abs(float(pastLng) - float(longi)) <= .00001:
        inter_time = time[0:2]+time[3:5] + time[6:8]  # How to parse colon datetimes https://stackoverflow.com/questions/30999230/how-to-parse-timezone-with-colon
        data_dt = datetime.strptime(inter_time, '%H%M%S').time()
        past_time = (datetime.min + past[3]).time()

        difference = datetime.combine(datetime.today(), data_dt) - datetime.combine(datetime.today(), past_time)  # Concept for difference based on https://stackoverflow.com/questions/9578906/easiest-way-to-combine-date-and-time-strings-to-single-datetime-object-using-pyt
        print(difference.total_seconds() % 3600)

        # Timedelta to minutes from https://stackoverflow.com/questions/14190045/how-do-i-convert-datetime-timedelta-to-minutes-hours-in-python/43965102
        time_at = (difference.seconds % 3600)/60  # Make it a difference between date's time and past's time
        sql = "UPDATE user_info SET time_at_location = '%s' WHERE name LIKE '%s' ORDER BY date DESC, time DESC LIMIT 1;" % (time_at, current_user.username)
        db.query(sql)  # Update time_at_location for the previous entry
    else:  # The user moved more than a meter
        time_at = 0
        location = salt(lati, longi)  # Salt location data before storing it in the DB
        saltLati, saltLongi = location[0], location[1]
        sql = "INSERT INTO user_info VALUES ('%s', '%s',  '%s',  '%s', '%s', '%s')" % (current_user.username, date, time, saltLati, saltLongi, time_at)
        db.query(sql)  # Send new entry with all updated variables to the DB

    contactTrace(current_user.username, date, time, lati, longi)  # Check if this entry is overlaps with any other users last entries

    return render_template('location.html'), 200


# Allows users to report that they've tested positive
@app.route('/report', methods=['GET', 'POST'])
@login_required
def report():
    form = Form()
    if form.validate_on_submit():  # Checks to see if a valid form is received from report.html
        username = form.username.data.lower()
        infected = get_user(username)  # Get the User() object for the given username
        if not infected:  # There is no existing user with the given username
            emsg = "No user found. Check that you spelled the username correctly and try again."
            flash(emsg)
            return render_template('report.html', form=form)

        sql = "UPDATE user_id SET user_status = 1 WHERE name LIKE '%s';" % (username)
        db.query(sql)  # Update the user status in the database to '1' to indicate thate they're infected
        infected.status = 1  # Update the user status in their User() object too
        sql = "SELECT * FROM contacts WHERE personA LIKE '%s' OR personB LIKE '%s';" % (username, username)
        results = db.get(sql)  # Get a list of every time the infected user has come in contact with another user

        if results:  # The user has come in contact with other users
            contacted = [username]  # List to keep track of who has already been emailed
            for contact in results:
                if contact[0] == username:  # Get the user who was contacted
                    other = get_user(contact[1])
                else:
                    other = get_user(contact[0])
                if other.username in contacted:  # This user was in contact with the infected person multiple times
                    continue  # Skip the rest so they aren't emailed numerous times
                contacted.append(other.username)
                other.notify(contact[4], contact[5], contact[2], contact[3])  # Email the contacted person
                sql = "UPDATE user_id SET user_status = 2 WHERE name LIKE '%s';" % (other.username)
                db.query(sql)  # Update the user status in the database to '2' to indicate thate they were in contact with the infected
                other.status = 2  # Update the user status in their User() object too
            emsg = "Your status has been updated and users you were in contact with have been notified. Thank you."
            flash(emsg)
            return render_template('report.html', form=form)
        else:
            print("No users in contact with the infected user.")
            emsg = "Your status has been updated and users you were in contact with have been notified. Thank you."
            flash(emsg)
            return render_template('report.html', form=form)

    return render_template('report.html', form=form)


###################################################
#                  ERROR ROUTING
###################################################

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


###################################################
#                HELPER FUNCTIONS
###################################################

# Given a latitude and longitude it modifies their digits to obscure the actual data
def salt(lat, lng):
    la, lo = floatTrunc(lat, 7), floatTrunc(lng, 7)  # Reformat the lat and long to have 7 decimal places
    laSum, loSum = int(la[-1]), int(lo[-1])  # Get the last digit from the lat and long
    laList, loList = list(la), list(lo)  # Convert the lat and long strings to lists of characters

    for i in range(len(laList)-1):  # Loop through each character in the latitude
        if laList[i].isdigit():  # If the character is not a '-' or '.'
            laList[i] = str((int(laList[i])+laSum)%10)  # Add the last digit of lat to that digit

    for i in range(len(loList)-1):  # Loop through each character in the longitude
        if loList[i].isdigit():  # If the character is not a '-' or '.'
            loList[i] = str((int(loList[i])+loSum)%10)  # Add the last digit of lng to that digit

    return ["".join(laList), "".join(loList)]  # Return the lat and long in a list as strings


# Given a salted latitude and longitude, return the actual data
def unsalt(lat, lng):
    la, lo = str(lat), str(lng)  # Convert the lat and long inputs from floats to strings
    laList, loList = list(la), list(lo)  # Convert the lat and long strings to lists of characters
    laSub, loSub = int(la[-1]), int(lo[-1])  # Get the last digit from the lat and long

    for i in range(len(laList)-1):  # Loop through each character in the latitude
        if laList[i].isdigit():  # If the character is not a '-' or '.'
            laList[i] = str((int(laList[i])+10-laSub)%10)  # Subtract the last digit of lat from that digit

    for i in range(len(loList)-1):  # Loop through each character in the longitude
        if loList[i].isdigit():  # If the character is not a '-' or '.'
            loList[i] = str((int(loList[i])+10-loSub)%10)  # Subtract the last digit of lng from that digit

    return [float("".join(laList)), float("".join(loList))]  # Return the lat and long in a list as floats

# Creates a User class object from inputted variables and returns it
def create_user(usr, pas, email, uid=None, status=0):
    if not uid:  # If there was no unicode user id provided
        uid = uuid.uuid4()  # Generate one
    user = User([usr.lower(), pas, uid], status, email)  # Create an object of the User() class
    userObjects[uid] = user  # Add that object to the running list of user objects
    return user  # Return that object


# Given a username, it returns a User object
def get_user(usr):
    usr = usr.lower()  # Lowercase the inputted username in case it isn't already
    for user in userObjects.values():  # Loop through every item in the list of all User() objects
        if user.username == usr:  # If the User() object name matches the provided username
            return user  # Return that User() object
    return None  # No User() object was found with the given username


# Takes a float or string float and truncates it to have 'deg' decimals
def floatTrunc(num, deg):
    if isinstance(num, float):  # If the provided number is a float
        num = str(num)  # Convert it to a string
    numSplit = num.split('.')  # Split the number into decimals and integers
    numSplit[1] = numSplit[1][:deg]  # Truncate the decimals to length 'deg'
    num = ".".join(numSplit)  # Rejoin the integers and decimals
    return num


# Given a location entry, check if it overlaps with any other location entries from the last 5 minutes
def contactTrace(name, date, time, lat, lng):
    lat1, lng1 = float(floatTrunc(lat, 5)), float(floatTrunc(lng, 5))  # Truncate the latitude and longitude to 5 decimals and convert them to float
    sql = "SELECT name, latitude, longitude FROM user_info WHERE time_to_sec(timediff('%s', time)) < 500 AND datediff('%s', date) LIKE 0 AND name NOT LIKE '%s'" % (time, date, name)
    results = db.get(sql)  # Get every entry from the last 5 minutes
    contacts = []
    for entry in results:  # For every location entry added in the last 5 minutes
        loc = unsalt(entry[1], entry[2])  # Unsalt the location data
        lat2, lng2 = float(floatTrunc(loc[0], 5)), float(floatTrunc(loc[1], 5))  # Truncate the latitude and longitude to 5 decimals and convert them to float
        if abs(lat1-lat2) <= 0.00002 and abs(lng1-lng2) <= 0.00002: # Difference of 0.00002 in lat/long is 7.28346457 feet apart
            contacts.append(entry[0])  # If the users were within 7.283 feet, count that as a contact
    saltLoc = salt(lat, lng)  # Salt the submitted user location
    for contact in contacts:  # For every contact from the last 5 minutes
        sql = "INSERT INTO contacts VALUES ('%s', '%s', '%s', '%s', '%s', '%s')" % (name, contact, date, time, saltLoc[0], saltLoc[1])
        db.query(sql)  # Add it to the 'contacts' table in the database
    return


###################################################
#                    STARTUP
###################################################

# TODO: How much of this can be moved to main?
local = False  # Global keyword to track if app.py is being run in production or local
if len(sys.argv) > 1:  # If there were command line arguments provided when running app.py
    if sys.argv[1] == "local":  # Check if "local" was provided as an arg
        print("Running on local...")
        local = True

db = DB()  # Create in instance of the DB() class for managing the database connection
db.connect()  # Connect to the database

userObjects = {}  # Dict to keep track of User() class objects

results = db.get("SELECT * FROM user_id")  # Load all existing users from the database
for user in results:  # For every existing user
    create_user(user[1], user[2], user[4], user[0], user[3])  # Create a User() object


###################################################
#                      MAIN
###################################################

if __name__ == "__main__":
    if not local:
        app.run(debug=False)
    else:
        app.run(debug=True,host='localhost')
