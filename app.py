from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# 1. Database Configuration
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///matchday.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 2. Initialize the Database
db = SQLAlchemy(app)

# 3. Define the user model(Table)
class User(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(100), nullable = False)
    phone = db.Column(db.String(20), unique=True,nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # This creates the link from the User to the Team
    team = db.relationship('Team', backref='captain', uselist=False)

    def __repr__(self):
        return f"<User {self.name}>"

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    home_area = db.Column(db.String(100), nullable=False)
    format = db.Column(db.String(20), nullable=False, default='11-a-side') 
    level = db.Column(db.String(20), nullable=False)  # e.g., 'Friendly', 'Division 1'
    has_home_pitch = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # This is the Foreign Key connecting the Team back to the User
    captain_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)

    def __repr__(self):
        return f"<Team {self.name}>"

@app.route("/")
def home():
    return "MatchDay Api is Running"

if __name__ == "__main__":
    app.run(debug=True)
