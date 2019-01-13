# -*- coding: utf-8 -*-

from sqlalchemy import Column, Integer, String, DateTime, SmallInteger, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base

engine = create_engine('sqlite:///sqlite3.db', encoding='utf-8')

Base = declarative_base()


class Upload(Base):
    __tablename__ = 'uploads'

    id = Column(Integer, primary_key=True)
    datetime = Column(DateTime)
    username = Column(String)
    width = Column(Integer)
    filename = Column(String)
    status = Column(SmallInteger)
    log = Column(Boolean)

    def __repr__(self):
        return "{} to {}px ({})".format(self.filename, self.width, self.username)


if __name__ == '__main__':
    Base.metadata.create_all(engine)
