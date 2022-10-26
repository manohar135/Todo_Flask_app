from flask import Flask, render_template, request, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from winotify import Notification, audio
import atexit
import math

db = SQLAlchemy()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///Todo_DB.db"
db.init_app(app)

#Todo Database with there attribute
class TodoModel(db.Model):
    sno = db.Column(db.Integer, primary_key = True)
    title = db.Column(db.String(200), nullable = False)
    desc = db.Column(db.String(500), nullable = False)
    date_time = db.Column(db.String(30))

with app.app_context():
    db.create_all()
        
#Home page
@app.route('/', methods=['GET', 'POST'])
def Home():
    if request.method == 'POST':
        title = request.form['title']
        desc = request.form['desc']
        time = request.form['time']
        date = request.form['date']
        if '' not in [title, desc, date, time]:
            date_time = convert(date, time)
            todo = TodoModel(title=title, desc=desc, date_time = date_time)
            db.session.add(todo)
            db.session.commit()

    alltodo = TodoModel.query.all()                                                   # alltodo -----> has the record of all todos
    schedule(alltodo)
    resetDB(alltodo)
    return render_template('index.html', alltodo = alltodo)

# Deleting the records in DataBase
@app.route('/delete/<int:sno>')
def delete(sno):
    del_todo = TodoModel.query.filter_by(sno = sno).first()
    db.session.delete(del_todo)
    db.session.commit()
    return redirect('/')

# Creating View page 
@app.route('/view/<int:sno>')
def view(sno):
    todo = TodoModel.query.filter_by(sno = sno).first()
    rem_time = remaing_time(todo)
    alltodo = TodoModel.query.all()
    allsno = [x.sno for x in alltodo]
    print(type(allsno[allsno.index(4)]))
    return render_template('view.html', todo = todo, rem_time = rem_time, allsno = allsno)            #passing title and description

# Creating View page 
@app.route('/update/<int:sno>',methods=['GET', 'POST'])
def update(sno):
    if request.method == 'POST':
        title = request.form['title']
        desc = request.form['desc']
        time = request.form['time']
        date = request.form['date']
        ph_num = request.form['phno']
        if '' not in [title, desc, date, time, ph_num]:
            date_time = convert(date, time)
            up_todo = TodoModel.query.filter_by(sno = sno).first()
            up_todo.title = title
            up_todo.desc = desc
            up_todo.ph_num = ph_num
            up_todo.date_time = date_time
            db.session.add(up_todo)
            db.session.commit()
            return redirect('/view/'+str(sno))

    todo = TodoModel.query.filter_by(sno = sno).first()
    return render_template('update.html', todo = todo)          

# converting date and time to show in the DB table
def convert(date, time):
    with app.app_context():
        if int(time[0:2]) > 12:
            date_time = date +' [@'+str(int(time[0:2])-12)+time[2:]+' PM]' 
        else:
            date_time = date +' [@'+time+' AM]'

        return date_time

#Sending the notification to the user and deleting the todo from the Database
def notify_and_delet(todo):
    with app.app_context():
        win_notify(todo)
        delete(todo.sno)

#scheduling the time to send the notification
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

#Calculating the remaing time to send message
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

#Deleating past date todos that are incomplete
def resetDB(alltodo):
    with app.app_context():
        for todo in alltodo:
            todo_dt = datetime.strptime(todo.date_time, "%Y-%m-%d [@%I:%M %p]")
            if todo_dt + timedelta(minutes=2) < datetime.today():
                delete(todo.sno)

if __name__ == '__main__':
    app.run(debug=True)
    atexit.register(lambda: scheduler.shutdown())




