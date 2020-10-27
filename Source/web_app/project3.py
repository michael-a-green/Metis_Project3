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

#Stuff for the ML model
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import ticker
import re
import time
import pickle


import seaborn as sns

from sklearn.linear_model import LinearRegression
from sklearn.linear_model import LogisticRegression


from sklearn.model_selection import train_test_split
from sklearn.model_selection import cross_validate
from sklearn.model_selection import KFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
from sklearn.model_selection import cross_validate
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.metrics import plot_confusion_matrix, plot_roc_curve, classification_report, confusion_matrix
from sklearn.metrics import precision_recall_curve
from sklearn.metrics import roc_auc_score, roc_curve

from xgboost import XGBClassifier

from imblearn.over_sampling import RandomOverSampler
from imblearn.over_sampling import SMOTE
from imblearn.over_sampling import ADASYN

import pymysql.cursors
import sys

#to speed up pandas operands
from pandarallel import pandarallel

#GPU

import cupy as cnp
import cudf
import numpy as np
import pandas as pd

import gc
from sklearn.preprocessing import LabelEncoder
from cuml import train_test_split as gputrain_test_split
from cuml import LinearRegression as gpuLinearRegression
from cuml import KMeans as gpuKmeans
from cuml import LogisticRegression as gpuLogisticRegression
from cuml.ensemble import RandomForestClassifier as gpuRandomForestClassifier
from cuml.experimental.preprocessing import scale


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

##Get the normalizer and XGBoost objects
XGB_MODEL_PICKLE_FILE = open("../../Data/xgb_model.pkl","rb")
NORMALIZER_PICKLE_FILE = open("../../Data/normalizer.pkl","rb")

xgb_model = pickle.load(XGB_MODEL_PICKLE_FILE)
normalizer = pickle.load(NORMALIZER_PICKLE_FILE)

if xgb_model == None:
    print("Error - failed to read in ML model")
if normalizer == None:
    print("Error - failed to read in normalizer")


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
    
    # if prediction_performed != 1:
    #     prediction_performed = 0
    #     Y = 0
    #     Y_pred = 0
        
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

            
            
            send_email(app.config["PROJ3_ADMIN"]," New Transaction!!!","mail/new_transaction",transaction=transaction)
        else:
            #print("Found this in the database already")
            #print("here it is-->\n",transaction)
            session['known'] = True
            
        X = [form.step.data,
         form.amount.data,
         form.oldbalanceOrg.data,
         form.newbalanceOrig.data,
         form.oldbalanceDest.data,
         form.newbalanceDest.data,
         0, #suspect code
         0, #CASH_IN
         0, #CASH_OUT
         0, #DEBIT
         0, #PAYMENT
         0  #TRANSFER
        ]
        
        Y = form.isFraud.data
        print("type(Y) ",type(Y))
        session["Y"] = Y
        
        if ((form.oldbalanceOrg.data == form.amount.data) or (form.newbalanceDest.data == form.amount.data)) and (form.newbalanceOrig.data == 0):
            X[6] = 1.0
        elif ((form.oldbalanceOrg.data == form.amount.data) or (form.newbalanceDest.data == form.amount.data)) and (form.newbalanceOrig.data < form.oldbalanceOrg.data):
            X[6] = 0.6
        elif (form.amount.data <= 10000000) and (form.transtype.data == "TRANSFER" or form.transtype.data == "CASH_OUT"):
            X[6] = 0.1
        else:
            X[6] = 0.0
            
        #encode transtype string into a 1-hot value
        if (form.transtype.data == "TRANSFER"):
            X[11] = 1
        elif (form.transtype.data == "PAYMENT"):
            X[10] = 1
        elif (form.transtype.data == "DEBIT"):
            X[9] = 1
        elif (form.transtype.data == "CASH_OUT"):
            X[8] = 1
        elif (form.transtype.data == "CASH_IN"):
            X[7] = 1
        else:
            pass
        
        ## Normalize ML model input data
        print("X before numpy conversion \n",X,"\n")
        #X = np.array(X)
        #X = X.reshape(1,-1)
        #X = pd.DataFrame(X)
        cols_used_by_model = xgb_model.get_booster().feature_names
        #feature_names = xgb_model.feature_names
        print("cols_used_by_model = ",cols_used_by_model)
        print("type(cols_used_by_model[0]) is ",type(cols_used_by_model[0]))
        #print("feature_names = ",feature_names,"\n")        
        #X =  X[feature_names]
        print("X after numpy conversion \n",X,"\n")
        

        # ['f0', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11']

        
        print("X after preprocessing\n",X,"\n")

        #X = X.values
        print("type(X) is {}".format(type(X)))
        print("X just before normalization \n",X,"\n")
        X = np.array(X).reshape(1,-1)
        print("X just before normalization after converting to a np array\n",X,"\n")

        X_normal = normalizer.transform(X)
        print("type(X_normal) ",type(X_normal))
        print("X after normalization \n",X_normal,"\n")

        #X_normal = X_normal.reshape(1,-1)

        Xdict = {
            '0':  [ X_normal[0][0]  ],
            '1':  [ X_normal[0][1]  ],
            '2':  [ X_normal[0][2]  ],
            '3':  [ X_normal[0][3]  ],
            '4':  [ X_normal[0][4]  ],
            '5':  [ X_normal[0][5]  ],
            '6':  [ X_normal[0][6]  ],
            '7':  [ X_normal[0][7]  ],
            '8':  [ X_normal[0][8]  ],
            '9':  [ X_normal[0][9]  ],
            '10': [ X_normal[0][10] ],
            '11': [ X_normal[0][11] ]
        }
        vector = pd.DataFrame(Xdict)
        X_normal = vector[cols_used_by_model].iloc[[-1]]

        print("type(X_normal) before prediction \n",type(X_normal))
        print("X_normal before prediction \n",X_normal)
        
        Y_pred = xgb_model.predict(X_normal)
        Y_pred = Y_pred[0]
        Y_pred = int(Y_pred)
        print("type(Y_pred) ",type(Y_pred))        
        session["Y_pred"] = Y_pred
        session["prediction_performed"] = 1

        #go back to the index URL
        print("prediction_performed = {} Y_pred = {} Y = {}".format(session.get("prediction_performed",0),session.get("Y_pred",0),session.get("Y",0)))
        print("redirect URL performed")
        return redirect(url_for('index'))

    print("prediction_performed = {} Y_pred = {} Y = {}".format(session.get("prediction_performed",0),session.get("Y_pred",0),session.get("Y",0)))
    print("render_template in index performed")
    return render_template('index.html', current_time=datetime.utcnow(), form=form, known=session.get('known',False), Y_pred=session.get("Y_pred",0),Y=session.get("Y",0),prediction_performed=session.get("prediction_performed",0))

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
