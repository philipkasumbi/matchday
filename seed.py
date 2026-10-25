from app import app, db, User, Team

def seed_database():
    with app.app_context():
        # 1. Clear any old data (so we don't get 'unique' constraint errors if we run it twice)
        db.drop_all()
        db.create_all()

        print("Database Cleared and Recreated.")

        # 2. Create a Captain (User)
        captain_kasumbi = User(
            name = "Kasumbi",
            phone = "0790553620"
        )

        # Add the captain to the 'staging area'
        db.session.add(captain_kasumbi)

        # Save to database to generate the ID
        db.session.commit()
        print(f"Created {captain_kasumbi} with ID {captain_kasumbi.id}")

        # 3. Create a Team and link it to the Captain
        kutha_fc = Team(
            name = "Kutha Fc",
            home_area = "Mutonguni Ward",
            level = "Competitive",
            has_home_pitch = True,
            captain_id = captain_kasumbi.id
        )

        db.session.add(kutha_fc)
        db.session.commit()
        print(f"Created {kutha_fc} linked to Captain ID: {kutha_fc.captain_id}")

        # 4. Prove the SQLAlchemy Relationship works
        print("\n--- Testing the Relationship ---")

        # Let's ask the database for the team, and use the 'backref' to find the captain
        test_team = Team.query.filter_by(name="Kutha Fc").first()
        print(f"Query: Who is the captain of {test_team.name}?")
        print(f"Answer: {test_team.captain.name} (Phone: {test_team.captain.phone})")

        # Let's ask the database for the user, and use the relationship to find the team
        test_user = User.query.filter_by(name="Kasumbi").first()
        print(f"Query: Which team does {test_user.name} manage?")
        print(f"Answer: {test_user.team.name} (Format: {test_user.team.format})")


if __name__ == "__main__":
    seed_database()

