import os
from datetime import datetime
import inspect
from flask import Flask
from flask import render_template
from flask import session
from flask import redirect
from flask import url_for
from flask import flash
from flask_bootstrap import Bootstrap
from flask_moment import Moment
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, IntegerField, FloatField
from wtforms.validators import DataRequired, Length,NumberRange, AnyOf, InputRequired
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail
from flask_mail import Message
from threading import Thread


class TransactionForm(FlaskForm):
    step = IntegerField("On what time step will this transaction occur. Will only accept numbers <= 744", validators=[DataRequired(),NumberRange(min=1,max=744,message="must enter value within acceptable range")])
    transtype = StringField("What type of transaction? (Accepts only PAYMENT, TRANSFER,CASH_OUT,DEBIT,CASH_IN)",validators=[DataRequired(),AnyOf(values=["PAYMENT","TRANSFER","CASH_OUT","DEBIT","CASH_IN"],message="Must enter one of the supported values ONLY!")])
    amount = FloatField("What is the amount of the transaction?", validators=[InputRequired()])
    nameOrig = StringField("Name of the Originator of the transaction", validators=[DataRequired(),Length(min=1, max=255)])
    oldbalanceOrg = FloatField("Original originator balance", validators=[InputRequired()])
    newbalanceOrig = FloatField("new originator balance", validators=[InputRequired()])
    nameDest = StringField("Name of the Receiver of the transaction", validators=[DataRequired(), Length(min=1, max=255)])
    oldbalanceDest = FloatField("Original Receiver balance", validators=[ InputRequired(), NumberRange(min=0,message="must enter value of at least 0")])
    newbalanceDest = FloatField("New Receiver balance", validators=[InputRequired(),NumberRange(min=0,message="must enter value of at least 0")])
    isFraud = IntegerField("Is this a fraudulent transaction? Enter 1 for yes 0 for no only", validators=[InputRequired(),NumberRange(min=0,max=1)])
    isFlaggedFraud = IntegerField("Was this transaction flagged by the payment system as fraudulent? Enter 1 for yes 0 for no only", validators=[InputRequired(),NumberRange(min=0,max=1)])

    #The submit button
    submit = SubmitField("Submit")
        
    # step = IntegerField("On what time step will this transaction occur. Will only accept numbers <= 744", validators=[DataRequired(),NumberRange(min=1,max=744,message="must enter value with supported range")])
    # transtype = StringField("What type of transaction? (Accepts only PAYMENT, TRANSFER,CASH_OUT,DEBIT,CASH_IN)",validators=[DataRequired(),AnyOf(values=["PAYMENT","TRANSFER","CASH_OUT","DEBIT","CASH_IN"],message="Must enter one of the supported values ONLY!")])
    # amount = FloatField("What is the amount of the transaction?", validators=[DataRequired()])
    # nameOrig = StringField("Name of the Originator of the transaction", [validators.Required(),validators.Length(min=8, max=255)])
    # oldbalanceOrg = FloatField("Original originator balance", validators=[DataRequired(),NumberRange(min=0,message="must enter value of at least 0")])
    # newbalanceOrig = FloatField("new originator balance", validators=[DataRequired(),NumberRange(min=0,message="must enter value of at least 0")]
    # nameDest = StringField("Name of the Receiver of the transaction", validators=[DataRequired(), Length(min=8, max=255)])
    # oldbalanceDest = FloatField("Original Receiver balance", validators=[ DataRequired(), NumberRange(min=0,message="must enter value of at least 0")])
    # newbalanceDest = FloatField("New Receiver balance", validators=[DataRequired(),NumberRange(min=0,message="must enter value of at least 0")])
    # isFraud = IntegerField("Is this a fraudulent transaction? Enter 1 for yes 0 for no only", validators=[DataRequired()])
    # isFlaggedFraud = IntegerField("Was this transaction flagged by the payment system as fraudulent? Enter 1 for yes 0 for no only", validators=[DataRequired()])

#constructing the app
app = Flask(__name__)

#used to prevent CSR attacks
app.config['SECRET_KEY'] = os.environ['PROJECT3_FLASK_APP_SECRET_KEY']


##########################################################################################
#
# setting email notification. Make sure you source setup.sh before running the application
#
#########################################################################################
app.config['MAIL_SERVER'] = os.environ['MAIL_SERVER']
app.config['MAIL_PORT'] = os.environ['MAIL_PORT']
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME']  = os.environ['MAIL_USERNAME']
app.config['MAIL_PASSWORD']  = os.environ['MAIL_PASSWORD']
app.config['PROJ3_ADMIN'] = os.environ['PROJ3_ADMIN']
app.config['PROJ3_MAIL_SUBJECT_PREFIX'] = "[Metis Project 3]"
app.config['PROJ3_EMAIL_SENDER'] = os.environ["PROJ3_EMAIL_SENDER"]


#print("debug info\nmail_server = {}\nmail_port = {}\nmail_use_tls = {}\nmail_username = {}\nmail_password = {}\nproj3_admin = {}\nproj3_mail_subject_prefix = {}\nproj_email_sender = {}\n".format(
#      os.environ['MAIL_SERVER'], os.environ['MAIL_PORT'], True, os.environ['MAIL_USERNAME'], os.environ['MAIL_PASSWORD'], os.environ['PROJ3_ADMIN'], "[Metis Project 3]", os.environ["PROJ3_EMAIL_SENDER"]))

mail = Mail(app)

DB_USERNAME=os.environ['DB_USERNAME']
DB_PASSWORD=os.environ['DB_PASSWORD']
DB_HOST=os.environ['DB_HOST']
DATABASE_NAME=os.environ['DATABASE_NAME']
DB_URI = 'mysql+pymysql://%s:%s@%s:3306/%s' % (DB_USERNAME, DB_PASSWORD, DB_HOST, DATABASE_NAME)
    
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
    
#now its a bootstrap based app
bootstrap = Bootstrap(app)

#creating moment obj from flask application
moment = Moment(app)

#creating a database facility object registering it with the app
db = SQLAlchemy(app)

#creating migrate obj to enable database migrations: moving data to a db with an old schema to a db with a new schema w/o lossing data
migrate = Migrate(app, db)

    
#############
#
# Classes, and funcions, and bears (oh my!)
#
############

#run send_email() in a different thread and thereby make it asynchronous to the thread
#in which the app runs (making the call to send_email() non-blocking and making the app not lag out)
def send_async_email(app,msg):
    with app.app_context():
        mail.send(msg)

#Sends emails using the mail object created for this app
def send_email(to, subject, template, **kwargs):

    msg = Message(app.config['PROJ3_MAIL_SUBJECT_PREFIX'] + subject,
                  sender=app.config['PROJ3_EMAIL_SENDER'],
                  recipients=[to])

    msg.body = render_template(template+'.txt', **kwargs)
    msg.html = render_template(template+'.html', **kwargs)

    #run send_email is a new thread
    thr = Thread(target=send_async_email, args=[app, msg])
    thr.start()
    #mail.send(msg)


#table of transactions submitted through this website
class TransactionTable(db.Model):
    __tablename__ = "paysim_data3"
    id = db.Column(db.Integer, primary_key=True)
    step = db.Column(db.Integer)
    transtype = db.Column(db.String(255))
    amount = db.Column(db.Float)
    nameOrig = db.Column(db.String(255))
    oldbalanceOrg = db.Column(db.Float)
    newbalanceOrig = db.Column(db.Float)
    nameDest = db.Column(db.String(255))
    oldbalanceDest = db.Column(db.Float)
    newbalanceDest = db.Column(db.Float)
    isFraud = db.Column(db.Integer)
    isFlaggedFraud = db.Column(db.Integer)

    def __repr__(self):
        return "<step=%0d transtype=%r nameOrig=%r oldbalanceOrg=%.2f newbalanceOrig=%.2f> nameDest=%r oldbalanceDest=%.2f newbalanceDest=%.2f isFraud=%0d isFlaggedFraud=%0d"%(step, transtype, nameOrig, oldbalanceOrg, newbalanceOrig, nameDest, oldbalanceDest, newbalanceDest, isFraud, isFlaggedFraud)

@app.route('/', methods = ['GET','POST'])
def index():
    form =  TransactionForm()

    if form.validate_on_submit():
        #print("you did it!")
        #just querying according to transtype,originator name, dest name, and amount, and step
        transaction = TransactionTable.query.filter_by(step = form.step.data,
                                                       transtype = form.transtype.data,
                                                       nameOrig = form.nameOrig.data,
                                                       nameDest = form.nameDest.data,
                                                       amount = form.amount.data,
                                                       oldbalanceOrg = form.oldbalanceOrg.data,
                                                       newbalanceOrig = form.newbalanceOrig.data,
                                                       newbalanceDest = form.newbalanceDest.data,
                                                       oldbalanceDest = form.oldbalanceDest.data,
                                                       isFraud = form.isFraud.data,
                                                       isFlaggedFraud = form.isFlaggedFraud.data).first()

        

        #if the transaction entered into the form is not found in the database
        if transaction is None:
            #create transaction obj from form data
            transaction = TransactionTable(step = form.step.data,
                                      transtype = form.transtype.data,
                                      nameOrig = form.nameOrig.data,
                                      nameDest = form.nameDest.data,
                                      amount = form.amount.data,
                                      oldbalanceOrg = form.oldbalanceOrg.data,
                                      newbalanceOrig = form.newbalanceOrig.data,
                                      newbalanceDest = form.newbalanceDest.data,
                                      oldbalanceDest = form.oldbalanceDest.data,
                                      isFraud = form.isFraud.data,
                                      isFlaggedFraud = form.isFlaggedFraud.data)
            
            #print("did not find this in the database already")                        
            #write transaction object into the database
            db.session.add(transaction)
            db.session.commit()
            session['known'] = False
            send_email(app.config["PROJ3_ADMIN"],"New Transaction!!!","mail/new_transaction",transaction=transaction)
        else:
            #print("Found this in the database already")
            #print("here it is-->\n",transaction)
            session['known'] = True

        #go back to the index URL
        return redirect(url_for('index'))

    return render_template('index.html', current_time=datetime.utcnow(), form=form, known=session.get('known',False))

#error handling routes
#for 404 error
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

#for 500 error
@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

#to automatically setup the db when the app is called
@app.shell_context_processor
def make_shell_context():
    return dict(db=db, TransactionTable=TransactionTable)
