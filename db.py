from sqlalchemy import Column, Integer, String, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base

engine = create_engine('sqlite:///sqlite3.db', echo=True)

Base = declarative_base()


class Upload(Base):
    __tablename__ = 'uploads'

    id = Column(Integer, primary_key=True)
    datetime = Column(DateTime)
    username = Column(String)
    width = Column(Integer)
    filename = Column(String)

    def __repr__(self):
        return "{} to {}px ({})".format(self.filename, self.width, self.username)


if __name__ == '__main__':
    Base.metadata.create_all(engine)
