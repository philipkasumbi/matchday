from flask import Flask, request, render_template, url_for,flash,redirect
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import redirect
import os
from dotenv import load_dotenv

app = Flask(__name__)

load_dotenv()

# 1. Database Configuration
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///matchday.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

# 2. Initialize the Database
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)

login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# 3. Define the user model(Table)
class User(UserMixin,db.Model):
    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(100), nullable = False)
    phone = db.Column(db.String(20), unique=True,nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    password_hash = db.Column(db.String(255), nullable=False)

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
    status = db.Column(db.String(20), nullable = False, default ="PENDING")
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

# register route
@app.route("/register",methods=["GET","POST"])
def register():
    if request.method == "POST":
        name = request.form.get("captain_name")
        phone = request.form.get("phone")
        password = request.form.get("password")

        # check if number exists
        existing_user = User.query.filter_by(phone=phone).first()
        if existing_user:
            return "This phone number is already registered!"

        hashed_password = generate_password_hash(password)

        new_user = User(
            name = name,
            phone = phone,
            password_hash = hashed_password
        )

        db.session.add(new_user)
        db.session.commit()

        return "Registration Successful!"

    return render_template("register.html")

# login route
@app.route("/login",methods =["GET","POST"])
def login():
    if request.method == "POST":
        phone_number = request.form.get("phone_number")
        password = request.form.get("password")

        existing_user = User.query.filter_by(phone=phone_number).first()
        if existing_user:
            password_match = check_password_hash(existing_user.password_hash, password)
            if password_match:
                login_user(existing_user)
                return redirect(url_for("home"))
            else:
                return "Incorrect Password"
        else:
            return "User doesn't Exist"


    return render_template("login.html")


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

@app.route('/search')
def search_posts():
    open_posts = AvailabilityPost.query.filter_by(status="OPEN").all()
    location = request.args.get("area", "").strip()
    pitch_availability = request.args.get("pitch", "").strip()

    matching_posts = []

    #multi-parameter search filtering
    for post in open_posts:
        location_matches = not location or location.lower() in post.team.home_area.lower()
        pitch_matches = not pitch_availability or  pitch_availability.lower() == post.pitch_status.lower()

        if location_matches and pitch_matches:
            matching_posts.append(post)


    return render_template("search.html", posts=matching_posts)

# request match handler
@app.route("/request-match/<int:post_id>")
@login_required
def request_match(post_id):
   post = db.session.get(AvailabilityPost, post_id)
   if post and post.status=="OPEN":
       if current_user.team:
           if post.team != current_user.team:
               existing_request = MatchRequest.query.filter(
                   MatchRequest.post_id == post_id,
                   MatchRequest.requesting_team_id == current_user.team.id
               ).first()
               if not existing_request:
                   request = MatchRequest(
                       message = "Hey we are available!",
                       post_id= post.id,
                       requesting_team_id=current_user.team.id
                   )
                   db.session.add(request)
                   db.session.commit()

                   flash("Your match request has been sent successfully!")
                   return redirect(url_for("search"))

               else:
                   return "Your team has already requested this match."

           else:
               return "You cannot request your own team's post."
       else:
           return "You need to register a team before requesting a match."
   else:
       return "Ooops the post is not open for requesting"


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)
