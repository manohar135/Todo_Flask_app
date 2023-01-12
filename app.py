from flask import Flask, render_template, request, redirect, flash, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_required, login_user, current_user, logout_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, validators
from wtforms.validators import InputRequired, Length, ValidationError, EqualTo
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from winotify import Notification, audio
import atexit
import math

db = SQLAlchemy()
app = Flask(__name__)
bcrypt = Bcrypt(app)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///Todo_DB.db"
app.config['SECRET_KEY'] = 'todosecretkey'
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique = True)
    password = db.Column(db.String(80), nullable=False)

# Todo Database with there attribute
class TodoModel(db.Model):
    sno = db.Column(db.Integer, primary_key = True)
    title = db.Column(db.String(200), nullable = False)
    desc = db.Column(db.String(500), nullable = False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date_time = db.Column(db.String(30))


class RegisterForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Username"})
    password = PasswordField('Password', [validators.Regexp(r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$', message='Password should contain at least one uppercase letter, one number, and is at least 8 characters long')], render_kw={"placeholder": "Password"})
    confirm_password = PasswordField('Confirm Password', validators=[InputRequired(), EqualTo('password')], render_kw={"placeholder": "Confirm Password"})
    submit = SubmitField("Register")

    def validate_username(self, username):
        exist_username = User.query.filter_by(username = username.data).first()
        
        if exist_username:
            raise ValidationError("Username allready exist")


class LoginForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Username"})
    password = PasswordField(validators=[InputRequired(), Length(min=8, max=20)], render_kw={"placeholder": "Password"})
    submit = SubmitField("Login")


with app.app_context():
    db.create_all()

#Register page
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        encrypted_pass = bcrypt.generate_password_hash(form.password.data)
        new_user = User(username=form.username.data, password = encrypted_pass)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("login"))

    return render_template('register.html', form = form)

#Login page
@app.route('/', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            if bcrypt.check_password_hash(user.password, form.password.data):
                login_user(user)
                return redirect(url_for('dashboard'))
            else:
                form.username.errors.append("Invalid username or password")
        else:
            form.username.errors.append("Invalid username or password")

    return render_template('login.html', form = form)

#Logout
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# Home page
@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    user_id = current_user.id
    if request.method == 'POST':
        title = request.form['title']
        desc = request.form['desc']
        time = request.form['time']
        date = request.form['date']
        if '' not in [title, desc, date, time]:
            date_time = convert(date, time)
            todo = TodoModel(title=title, desc=desc, user_id = user_id, date_time = date_time)
            db.session.add(todo)
            db.session.commit()

    alltodo = TodoModel.query.filter_by(user_id=user_id).all()                            # alltodo -----> has the record of all todos
    schedule(alltodo)
    resetDB(alltodo)
    return render_template('index.html', alltodo = alltodo)

# Deleting the records in DataBase
@app.route('/delete/<int:sno>')
@login_required
def delete(sno):
    del_todo = TodoModel.query.filter_by(sno = sno).first()
    db.session.delete(del_todo)
    db.session.commit()
    return redirect(url_for('dashboard'))

# Creating View page 
@app.route('/view/<int:sno>')
@login_required
def view(sno):
    todo = TodoModel.query.filter_by(sno = sno).first()
    rem_time = remaing_time(todo)
    user_id = current_user.id
    alltodo = TodoModel.query.filter_by(user_id=user_id).all()
    allsno = [x.sno for x in alltodo]
    return render_template('view.html', todo = todo, rem_time = rem_time, allsno = allsno)            #passing title and description

# Making any changes in the List
@app.route('/update/<int:sno>',methods=['GET', 'POST'])
@login_required
def update(sno):
    if request.method == 'POST':
        title = request.form['title']
        desc = request.form['desc']
        time = request.form['time']
        date = request.form['date']
        if '' not in [title, desc, date, time]:
            date_time = convert(date, time)
            up_todo = TodoModel.query.filter_by(sno = sno).first()
            up_todo.title = title
            up_todo.desc = desc
            up_todo.date_time = date_time
            db.session.add(up_todo)
            db.session.commit()
            return redirect('/view/'+str(sno))

    todo = TodoModel.query.filter_by(sno = sno).first()
    return render_template('update.html', todo = todo)          

# Converting date and time to show in the DB table
def convert(date, time):
    with app.app_context():
        if int(time[0:2]) > 12:
            date_time = date +' [@'+str(int(time[0:2])-12)+time[2:]+' PM]' 
        else:
            date_time = date +' [@'+time+' AM]'

        return date_time

# Sending the notification to the user and deleting the todo from the Database
def notify_and_delet(todo):
    with app.app_context():
        win_notify(todo)
        delete(todo.sno)

# Scheduling the time to send the notification
scheduler = BackgroundScheduler(timezone = "Asia/Calcutta")
scheduler.start()
def schedule(alltodo):
    with app.app_context():
        scheduler.remove_all_jobs()
        for todo in alltodo:
            todo_date = datetime.strptime(todo.date_time, "%Y-%m-%d [@%I:%M %p]")
            scheduler.add_job(notify_and_delet, 'cron', day = todo_date.day, hour = todo_date.hour, minute = todo_date.minute, args=[todo])

# Window Notification
def win_notify(todo):
    with app.app_context():
        toast = Notification(app_id="Todo no "+str(todo.sno), title="Title:  "+todo.title, msg="\nDescription:\n"+todo.desc, duration="long")
        toast.set_audio(audio.Mail, loop=False)
        toast.show()

# Calculating the remaing time to send message
def remaing_time(todo):
    with app.app_context():
        todo_dt = datetime.strptime(todo.date_time, "%Y-%m-%d [@%I:%M %p]")
        today = datetime.today()
        delta = todo_dt - today
        if delta.days > 0:
            return str(delta.days) + " Days Remaining"
        elif delta.days < 0:
            delete(todo.sno)
        elif (delta.seconds/3600) > 1:
            return str(math.ceil(delta.seconds/3600)) + " hours Remaining"
        elif (delta.seconds/60) > 0:
            return str(math.ceil(delta.seconds/60)) + " Minutes Remaining"

# Deleating past date todos that are incomplete
def resetDB(alltodo):
    with app.app_context():
        for todo in alltodo:
            todo_dt = datetime.strptime(todo.date_time, "%Y-%m-%d [@%I:%M %p]")
            if todo_dt + timedelta(minutes=2) < datetime.today():
                delete(todo.sno)

if __name__ == '__main__':
    app.run(debug=True)
    atexit.register(lambda: scheduler.shutdown())




