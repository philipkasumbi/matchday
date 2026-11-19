from flask import Flask, request, render_template, url_for,flash,redirect
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import redirect
import os
from dotenv import load_dotenv
from datetime import datetime,date
from sqlalchemy import or_,select

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
    date = db.Column(db.DateTime, nullable=False)
    # time_window = db.Column(db.String(50), nullable=False)  # e.g., '2:00 PM - 4:00 PM'

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


class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("match_request.id"), unique=True, nullable=False)

    home_team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=False)
    away_team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=False)
    match_date = db.Column(db.DateTime, nullable=False)
    venue = db.Column(db.String(120), nullable=False)

    home_score = db.Column(db.Integer, nullable=True)
    away_score = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.String(255), nullable=True)

    # Relationships
    request = db.relationship("MatchRequest", backref=db.backref("match", uselist=False))
    home_team = db.relationship("Team", foreign_keys=[home_team_id])
    away_team = db.relationship("Team", foreign_keys=[away_team_id])


@app.route("/")
def home():
    today = date.today()

    accepted_matches = MatchRequest.query.join(AvailabilityPost).filter(
        MatchRequest.status == "ACCEPTED",
        or_(
            AvailabilityPost.team_id == current_user.team.id,
            MatchRequest.requesting_team_id == current_user.team.id
        )
    ).order_by(AvailabilityPost.date.asc()).all()


    upcoming_matches = []

    for match in accepted_matches:
        match_date = match.post.date.date()

        if match_date >= today:
            upcoming_matches.append(match)

    available_teams = AvailabilityPost.query.filter(
        AvailabilityPost.status == "OPEN",
        AvailabilityPost.team_id != current_user.team.id
    ).count()

    pending_requests = MatchRequest.query.join(AvailabilityPost).filter(
        AvailabilityPost.team_id == current_user.team.id,
        MatchRequest.status == "PENDING"
    ).count()

    return render_template("home.html", pending_requests=pending_requests,confirmed_match=upcoming_matches)

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
            flash("User doesn't Exist")
            return redirect(url_for("register"))


    return render_template("login.html")


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

# create a team for a logged-in captain
@app.route("/register-team",methods=["POST","GET"])
@login_required
def register_team():
    if request.method == "POST":
        team_name = request.form.get("name")
        home_area = request.form.get("home_area")
        format = request.form.get("format")
        level = request.form.get("level")
        home_pitch = request.form.get("has_home_pitch")
        has_home_pitch = home_pitch.strip().lower() == "yes"


        if current_user.team:
            return "The team is already Registered"

        team = Team(
            name = team_name,
            home_area = home_area,
            format = format,
            level = level,
            has_home_pitch = has_home_pitch,
            captain_id = current_user.id
        )

        db.session.add(team)
        db.session.commit()
        flash("You have successfully registered your team")
        return  redirect(url_for("home"))

    return render_template("register_team.html")

# create an availability post
@app.route("/posts",methods=["POST","GET"])
@login_required
def team_posts():
    if request.method == "POST":
        date_input = request.form.get("date")
        date = datetime.fromisoformat(date_input)
        pitch_status = request.form.get("pitch_status")

        if current_user.team:
            post = AvailabilityPost(
                date = date,
                pitch_status = pitch_status,
                team_id = current_user.team.id
            )

            db.session.add(post)
            db.session.commit()

            flash("Post Created successfully")
            return redirect(url_for("home"))
        flash("Register a Team First")
        return redirect(url_for("register_team"))

    return render_template("posts.html")

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
                   return redirect(url_for("search_posts"))

               else:
                   return "Your team has already requested this match."

           else:
               return "You cannot request your own team's post."
       else:
           return "You need to register a team before requesting a match."
   else:
       return "Ooops the post is not open for requesting"

# accept match requests
@app.route("/inbox")
@login_required
def inbox():
    if current_user.team:
        captains_posts = current_user.team.posts
        incoming_requests = []
        for post in captains_posts:
            match_requests = post.match_requests
            for match_request in match_requests:
                match_request_id = match_request.id
                requesting_team = match_request.requesting_team.name
                status = match_request.status
                message = match_request.message
                incoming_requests.append({
                    "match_request_id":match_request_id,
                    "requesting_team":requesting_team,
                    "status":status,
                    "message":message
                })

        pending_requests = []
        for request in incoming_requests:
            if request["status"] == "PENDING":
                pending_requests.append(request)

        accepted_requests = []
        for request in incoming_requests:
            if request["status"] == "ACCEPTED":
                accepted_requests.append(request)

        declined_requests = []
        for request in incoming_requests:
            if request["status"] == "DECLINED":
                declined_requests.append(request)

        return render_template("inbox.html",pending_requests=pending_requests,accepted_requests=accepted_requests,declined_requests=declined_requests)
    flash("You don't have a registered team")
    return redirect(url_for("register_team"))


# accept Match
@app.route('/accept/<int:request_id>',methods=["POST"])
@login_required
def accept_match(request_id):
    match_req = db.session.get(MatchRequest, request_id)

    if not match_req:
        return "Match request not found"

    if not current_user.team or match_req.post.team != current_user.team:
        return "You are not authorized to accept this request"

    if match_req.status != "PENDING" or match_req.post.status != "OPEN":
        return "This request is no longer available"

    match_req.status = "ACCEPTED"

    new_match = Match(
        request_id=match_req.id,
        home_team_id=match_req.post.team_id,
        away_team_id=match_req.requesting_team_id,
        match_date=match_req.post.date,
        venue=f"{match_req.post.team.name} Grounds"
    )
    db.session.add(new_match)


    for other_request in match_req.post.match_requests:
        if other_request.id != match_req.id and other_request.status == "PENDING":
            other_request.status = "CANCELLED_AUTO"

    match_req.post.status = "CLOSED"
    db.session.commit()

    flash("Match request accepted successfully!")
    return redirect(url_for("inbox"))


#display declined or accepted on the request sender inbox
@app.route("/my_requests")
@login_required
def my_requests():
    if current_user.team:
        all_team_requests = MatchRequest.query.filter(MatchRequest.requesting_team_id == current_user.team.id).all()

        return render_template("my_requests.html",team_requests=all_team_requests)

    return "You need to register a team first"


# history page
@app.route("/history")
@login_required
def history():
    if not current_user.team:
        return redirect(url_for("create_team"))

    today = date.today()

    stmt = (
        select(Match)
        .where(
            Match.match_date < today,
            or_(
                Match.home_team_id == current_user.team.id,
                Match.away_team_id == current_user.team.id
            )
        )
        .order_by(Match.match_date.desc())
    )
    past_matches = db.session.execute(stmt).scalars().all()

    return render_template("history.html", past_matches=past_matches)


@app.route("/match/<int:match_id>/result", methods=["POST"])
@login_required
def record_result(match_id):
    match = db.session.get(Match, match_id)

    if not match:
        flash("Match not found.")
        return redirect(url_for("history"))

    if not current_user.team or current_user.team.id not in [match.home_team_id, match.away_team_id]:
        flash("You are not authorized to record this result.")
        return redirect(url_for("history"))

    home_score = request.form.get("home_score", type=int)
    away_score = request.form.get("away_score", type=int)

    if home_score is None or away_score is None or home_score < 0 or away_score < 0:
        flash("Please enter valid scores (0 or higher).")
        return redirect(url_for("history"))

    match.home_score = home_score
    match.away_score = away_score
    db.session.commit()

    flash("Match result saved!")
    return redirect(url_for("history"))





with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)
