from datetime import datetime
import os
import requests
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from models import *


DATABASE_URL = f"postgresql://{os.getenv('POSTGRESQL_USERNAME')}:{os.getenv('POSTGRESQL_PASSWORD')}@{os.getenv('POSTGRESQL_MASTER_HOST')}:5432/{os.getenv('POSTGRESQL_DATABASE')}"
print(DATABASE_URL)
engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()
db = SessionLocal()

result = requests.get('http://kaas-api:8000/health')
if result.status_code == 200:
    result = result.json()
    app = db.query(Health).filter(Health.app_name == result['app_name']).first()
    if app is not None:
        app.success_count += 1
        app.last_success = datetime.now()
    else:
        record = Health(app_name=result['app_name'], success_count=1, last_success=datetime.now(), failure_count=0, last_failure=None, created_at=result['created_at'])
        db.add(record)
    db.commit()


else:
    result = result.json()['detail']
    app = db.query(Health).filter(Health.app_name == result['app_name']).first()
    if app is not None:
        app.failure_count += 1
        app.last_failure = datetime.now()
    else:
        record = Health(app_name=result['app_name'], success_count=0, last_success=None, failure_count=1,
                        last_failure=datetime.now(), created_at=result['created_at'])
        db.add(record)
    db.commit()

