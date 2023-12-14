import unittest
from flask import json
from backend.app import app, db, Malaria, import_malaria_csv


class TestMainFile(unittest.TestCase):
    def setUp(self):
        # Set up a test Flask app and configure it for testing
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_malaria.db'
        app.config['SQLALCHEMY_BINDS'] = {
            'malaria_db': app.config['SQLALCHEMY_DATABASE_URI']
        }

        # Create a test client
        self.client = app.test_client()

        # Create the test database tables
        with app.app_context():
            db.create_all()
            import_malaria_csv()

    def tearDown(self):
        # Drop the test database tables
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_home_route(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b'Ok')

    def test_reset_malaria_db_route(self):
        response = self.client.put('/api/reset/malaria/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Successfully reset the malaria database', response.data)

    def test_filter_malaria_route(self):
        response = self.client.get('/api/malaria/filter?region=Africa')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('malaria_data', data)
        self.assertIsInstance(data['malaria_data'], list)

    def test_get_all_malaria_route(self):
        response = self.client.get('/api/malaria/')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIsInstance(data, list)

    # Add more test methods for other routes and functions as needed


if __name__ == '__main__':
    unittest.main()
