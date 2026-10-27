from os import name

from app import app, db, User, Team, AvailabilityPost, MatchRequest
from datetime import date


def seed_database():
    with app.app_context():
        # Clear and recreate tables
        db.drop_all()
        db.create_all()

        print("Database cleared and recreated.")

        # --- HOST TEAM (Kutha Fc) ---
        captain_kasumbi = User(name="Kasumbi", phone="0790553620")
        db.session.add(captain_kasumbi)
        db.session.commit()

        kutha_fc = Team(name="Kutha Fc", home_area="Kitui Town", level="Competitive", has_home_pitch=True,
                        captain_id=captain_kasumbi.id)
        db.session.add(kutha_fc)
        db.session.commit()

        sunday_post = AvailabilityPost(date=date(2026, 11, 1), time_window="3:00 PM - 5:00 PM",
                                       pitch_status="HAVE_PITCH", team_id=kutha_fc.id)
        db.session.add(sunday_post)
        db.session.commit()
        print("Created Kutha Fc and their Sunday availability post.")

        # create another host team
        another_host = User(
            name = "tabby",
            phone = "0702300281"
        )
        db.session.add(another_host)
        db.session.commit()

        nyuani_fc = Team(name= "Nyuani Fc",home_area="Kitui Town", level="Competitive", has_home_pitch=True,
                        captain_id=another_host.id)
        db.session.add(nyuani_fc)
        db.session.commit()

        nyuani_sunday_post = AvailabilityPost(date=date(2026, 11, 1), time_window="3:00 PM - 5:00 PM",
                                       pitch_status="HAVE_PITCH", team_id=kutha_fc.id)
        db.session.add(nyuani_sunday_post)
        db.session.commit()

        # --- CHALLENGER TEAM 1 (Kitui United) ---
        captain_john = User(name="John", phone="0711223344")
        db.session.add(captain_john)
        db.session.commit()

        kitui_united = Team(name="Kitui United", home_area="Kitui Central", level="Competitive", has_home_pitch=False,
                            captain_id=captain_john.id)
        db.session.add(kitui_united)
        db.session.commit()

        # Kitui United sends a request to Kutha Fc's post
        request_1 = MatchRequest(post_id=sunday_post.id, requesting_team_id=kitui_united.id,
                                 message="We can travel to you!")
        db.session.add(request_1)
        db.session.commit()

        # --- CHALLENGER TEAM 2 (Mwingi Rovers) ---
        captain_peter = User(name="Peter", phone="0799887766")
        db.session.add(captain_peter)
        db.session.commit()

        mwingi_rovers = Team(name="Mwingi Rovers", home_area="Mwingi", level="Friendly", has_home_pitch=False,
                             captain_id=captain_peter.id)
        db.session.add(mwingi_rovers)
        db.session.commit()

        # Mwingi Rovers also sends a request
        request_2 = MatchRequest(post_id=sunday_post.id, requesting_team_id=mwingi_rovers.id, message="We are free!")
        db.session.add(request_2)
        db.session.commit()

        print("\n--- Current Database State ---")
        print(f"Available Posts: {len(AvailabilityPost.query.filter_by(status="OPEN").all())}")
        print(f"Post Status: {sunday_post.status}")
        print(f"Request 1 (Kitui United) ID: {request_1.id} | Status: {request_1.status}")
        print(f"Request 2 (Mwingi Rovers) ID: {request_2.id} | Status: {request_2.status}")
        print("\nReady for testing!")


if __name__ == "__main__":
    seed_database()