from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import date

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

    posts = db.relationship('AvailabilityPost', backref='team', lazy=True)

    def __repr__(self):
        return f"<Team {self.name}>"


class AvailabilityPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    time_window = db.Column(db.String(50), nullable=False)  # e.g., '2:00 PM - 4:00 PM'

    # The crucial pitch filter: 'HAVE_PITCH', 'NEED_PITCH', 'NEUTRAL'
    pitch_status = db.Column(db.String(20), nullable=False)

    # State machine: 'OPEN', 'CONFIRMED', 'EXPIRED'
    status = db.Column(db.String(20), nullable=False, default='OPEN')
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # The Foreign Key linking back to the Team
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)

    def __repr__(self):
        return f"<Post {self.date} ({self.status}) by Team ID {self.team_id}>"


class MatchRequest(db.Model):
    id = db.Column(db.Integer, primary_key= True)
    status = db.Column(db.String(20), nullable = False, default = "PENDING")
    message = db.Column(db.String(200),nullable=True)
    post_id = db.Column(db.Integer,db.ForeignKey("availability_post.id"),nullable = False)
    requesting_team_id = db.Column(db.Integer,db.ForeignKey("team.id"),nullable = False)
    created_at = db.Column(db.DateTime, server_default = db.func.now())
    # relationships
    post = db.relationship("AvailabilityPost",backref="match_requests")
    requesting_team = db.relationship("Team", foreign_keys=[requesting_team_id])


@app.route("/")
def home():
    return "MatchDay Api is Running"

@app.route('/accept/<int:request_id>')
def accept_match(request_id):
    match_req = MatchRequest.query.get(request_id)
    match_req.status = "ACCEPTED"
    related_post = match_req.post
    related_post.status = "CONFIRMED"
    for request in related_post.match_requests:
        if request.id != match_req.id:
            request.status = "CANCELLED_AUTO"

    db.session.commit()

    return f"Match {request_id} Accepted successfully!"

if __name__ == "__main__":
    app.run(debug=True)
