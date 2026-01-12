from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

# This tells APScheduler to store its 'to-do list' in a local SQLite file
jobstores = {
    'default': SQLAlchemyJobStore(url='sqlite:///adjnt_jobs.sqlite')
}

scheduler = BackgroundScheduler(jobstores=jobstores)
scheduler.start()