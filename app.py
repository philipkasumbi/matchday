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
    if not current_user.team:
        flash("Please create your team profile first.")
        return redirect(url_for("register_team"))

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
            flash("This phone number is already registered!","error")
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)

        new_user = User(
            name = name,
            phone = phone,
            password_hash = hashed_password
        )

        db.session.add(new_user)
        db.session.commit()

        flash("Registration Successful!","success")
        return redirect(url_for('login'))

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
                flash(f"Welcome back, {existing_user.name}!", "success")
                return redirect(url_for("home"))
            else:
                flash("Incorrect password. Please try again.", "error")
                return redirect(url_for("login"))
        else:
            flash("User doesn't Exist","error")
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
            flash("The team is already Registered","error")
            return redirect(url_for('register_team'))

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
        flash("You have successfully registered your team","success")
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

            flash("Post Created successfully","success")
            return redirect(url_for("team_posts"))
        flash("Register a Team First","error")
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

                   flash("Your match request has been sent successfully!","success")
                   return redirect(url_for("search_posts"))

               else:
                   flash("Your team has already requested this match.","error")
                   return redirect(url_for('search_posts'))
           else:
               flash("You cannot request your own team's post.","error")
               return redirect(url_for('search_posts'))
       else:
           flash("You need to register a team before requesting a match.","error")
           return redirect(url_for('search_posts'))
   else:
       flash("Ooops the post is not open for requesting","error")
       return redirect(url_for('search_posts'))

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
    flash("You don't have a registered team","error")
    return redirect(url_for("register_team"))


# accept Match
@app.route('/accept/<int:request_id>',methods=["POST"])
@login_required
def accept_match(request_id):
    match_req = db.session.get(MatchRequest, request_id)

    if not match_req:
       flash("Match request not found")
       return redirect(url_for("inbox"))

    if not current_user.team or match_req.post.team != current_user.team:
        flash("You are not authorized to accept this request")
        return redirect(url_for("inbox"))

    if match_req.status != "PENDING" or match_req.post.status != "OPEN":
        flash("This request is no longer available")
        return redirect(url_for("inbox"))

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

    flash("Match request accepted successfully!","success")
    return redirect(url_for("inbox"))


# display declined or accepted on the request sender inbox
@app.route("/my_requests")
@login_required
def my_requests():
    if current_user.team:
        now = datetime.now()

        # Mark past PENDING requests as EXPIRED
        expired_pending = (
            MatchRequest.query
            .join(AvailabilityPost)
            .filter(
                MatchRequest.requesting_team_id == current_user.team.id,
                MatchRequest.status == "PENDING",
                AvailabilityPost.date < now
            )
            .all()
        )
        for req in expired_pending:
            req.status = "EXPIRED"
        if expired_pending:
            db.session.commit()

        # Only fetch upcoming requests (match day hasn't passed yet)
        all_team_requests = (
            MatchRequest.query
            .join(AvailabilityPost)
            .filter(
                MatchRequest.requesting_team_id == current_user.team.id,
                AvailabilityPost.date >= now
            )
            .order_by(AvailabilityPost.date.asc())
            .all()
        )

        return render_template("my_requests.html", team_requests=all_team_requests)

    flash("You need to register a team first","error")
    return redirect(url_for("register_team"))

# history page
@app.route("/history")
@login_required
def history():
    if not current_user.team:
        flash("Register a team First")
        return redirect(url_for("register_team"))

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
        flash("Match not found.","error")
        return redirect(url_for("history"))

    if not current_user.team or current_user.team.id not in [match.home_team_id, match.away_team_id]:
        flash("You are not authorized to record this result.","error")
        return redirect(url_for("history"))

    home_score = request.form.get("home_score", type=int)
    away_score = request.form.get("away_score", type=int)

    if home_score is None or away_score is None or home_score < 0 or away_score < 0:
        flash("Please enter valid scores (0 or higher).","error")
        return redirect(url_for("history"))

    match.home_score = home_score
    match.away_score = away_score
    db.session.commit()

    flash("Match result saved!","success")
    return redirect(url_for("history"))

@app.route("/cancel_match/<int:request_id>", methods=["POST"])
@login_required
def cancel_match(request_id):
    match_request = db.session.get(MatchRequest, request_id)
    if not match_request:
        flash("Match request not found.","error")
        return redirect(url_for("home"))

    post = match_request.post
    user_team_id = current_user.team.id

    if post.team_id != user_team_id and match_request.requesting_team_id != user_team_id:
        flash("You are not authorized to cancel this match.","error")
        return redirect(url_for("home"))

    match_record = Match.query.filter_by(request_id=match_request.id).first()
    if match_record and match_record.home_score is None:
        db.session.delete(match_record)

    match_request.status = "CANCELLED"

    post.status = "OPEN" if post.date > datetime.now() else "CANCELLED"

    db.session.commit()
    flash("Confirmed match has been cancelled.","error")
    return redirect(url_for("home"))

@app.context_processor
def inject_pending_count():
    if current_user.is_authenticated and current_user.team:
        count = (
            MatchRequest.query
            .join(AvailabilityPost)
            .filter(
                AvailabilityPost.team_id == current_user.team.id,
                MatchRequest.status == "PENDING",
                AvailabilityPost.date >= datetime.now()
            )
            .count()
        )
        return dict(pending_count=count)
    return dict(pending_count=0)

# profile
@app.route("/profile")
@login_required
def profile():
    team = current_user.team
    open_posts_count = 0
    played_matches_count = 0

    if team:
        open_posts_count = AvailabilityPost.query.filter_by(
            team_id=team.id,
            status="OPEN"
        ).count()

        played_matches_count = (
            Match.query
            .join(MatchRequest, Match.request_id == MatchRequest.id)
            .join(AvailabilityPost, MatchRequest.post_id == AvailabilityPost.id)
            .filter(
                db.or_(
                    MatchRequest.requesting_team_id == team.id,
                    AvailabilityPost.team_id == team.id
                ),
                AvailabilityPost.date < datetime.now()
            )
            .count()
        )

    return render_template(
        "profile.html",
        team=team,
        open_posts_count=open_posts_count,
        played_matches_count=played_matches_count
    )

# edit
@app.route("/profile/edit", methods=["POST"])
@login_required
def edit_profile():
    name = request.form.get("name", "").strip()

    if not name:
        flash("Name cannot be empty.","error")
        return redirect(url_for("profile"))

    current_user.name = name

    if current_user.team:
        team_name = request.form.get("team_name", "").strip()
        home_area = request.form.get("home_area", "").strip()
        match_format = request.form.get("format", "").strip()

        if not team_name or not home_area or not match_format:
            flash("All team fields are required.","error")
            return redirect(url_for("profile"))

        current_user.team.name = team_name
        current_user.team.home_area = home_area
        current_user.team.format = match_format

    db.session.commit()
    flash("Profile updated successfully.","success")
    return redirect(url_for("profile"))

# delete account
@app.route("/delete_account", methods=["POST"])
@login_required
def delete_account():
    user = current_user
    team = user.team

    if team:
        team_post_ids = [p.id for p in AvailabilityPost.query.filter_by(team_id=team.id).all()]
        related_requests = MatchRequest.query.filter(
            db.or_(
                MatchRequest.requesting_team_id == team.id,
                MatchRequest.post_id.in_(team_post_ids)
            )
        ).all()

        related_request_ids = [r.id for r in related_requests]

        if related_request_ids:
            Match.query.filter(Match.request_id.in_(related_request_ids)).delete(synchronize_session=False)
            MatchRequest.query.filter(MatchRequest.id.in_(related_request_ids)).delete(synchronize_session=False)

        AvailabilityPost.query.filter_by(team_id=team.id).delete(synchronize_session=False)
        db.session.delete(team)

    # 4. Log out and delete the user
    logout_user()
    db.session.delete(user)
    db.session.commit()

    flash("Your account and team data have been permanently deleted.","success")
    return redirect(url_for("register"))


# logout
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.","success")
    return redirect(url_for("login"))

with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)
