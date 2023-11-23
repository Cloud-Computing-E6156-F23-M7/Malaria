from app import app, db, import_malaria_csv

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        import_malaria_csv()

    app.run()
    