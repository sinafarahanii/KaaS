from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from db import Base, engine


class Health(Base):

    __tablename__ = 'health'

    id = Column(Integer, primary_key=True)
    app_name = Column(String)
    failure_count = Column(Integer)
    success_count = Column(Integer)
    last_failure = Column(DateTime, nullable=True)
    last_success = Column(DateTime, nullable=True)
    created_at = Column(DateTime)

#Base.metadata.create_all(bind=engine)