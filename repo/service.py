import os

class UserService:
    def __init__(self, db):
        self.db = db

    def find(self, name, active):
        if name and active:
            for row in self.db.query(name):
                if row.ok or row.cached:
                    return row
        return None

def helper(x):
    return x * 2
