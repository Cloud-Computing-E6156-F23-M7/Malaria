import json, os, requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import text
import pandas as pd

### Set up the database ###

class DbConfig(object):
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://admin:weareteamm7@malariastat.czmrkezas6nx.us-east-2.rds.amazonaws.com:3306/Malaria_db'
    SQLALCHEMY_BINDS = {
        'malaria_db': SQLALCHEMY_DATABASE_URI  # default bind
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False

app = Flask(__name__)
app.config.from_object(DbConfig)
app.json.sort_keys = False
db = SQLAlchemy(app)
CORS(app)

class Malaria(db.Model):
    __bind_key__ = 'malaria_db'
    id = db.Column(db.Integer, primary_key=True)
    region = db.Column(db.String(100))
    year = db.Column(db.Integer)
    cases = db.Column(db.String(100))
    deaths = db.Column(db.String(100))
    cases_median = db.Column(db.Integer)
    cases_min = db.Column(db.Integer)
    cases_max = db.Column(db.Integer)
    deaths_median = db.Column(db.Integer)
    deaths_min = db.Column(db.Integer)
    deaths_max = db.Column(db.Integer)
    fips = db.Column(db.String(2))
    iso = db.Column(db.String(3))   # assume uppercase
    iso2 = db.Column(db.String(2))
    land_area_kmsq_2012 = db.Column(db.Integer)
    languages_en_2012 = db.Column(db.String(100))
    who_region = db.Column(db.String(100))
    world_bank_income_group = db.Column(db.String(100))

    def serialize(self):
        return {
            'malaria_id': self.id,
            'region': self.region,
            'iso': self.iso,
            'year': self.year,
            'cases_median': self.cases_median,
            'deaths_median': self.deaths_median,
            'land_area_kmsq_2012': self.land_area_kmsq_2012,
            'languages_en_2012': self.languages_en_2012,
            'who_region': self.who_region,
            'world_bank_income_group': self.world_bank_income_group
        }

### Import data to the database ###

def import_malaria_csv():
    malaria_csv_path = os.path.join(
        os.getcwd(), 
        'estimated_numbers.csv'
        )
    df = pd.read_csv(malaria_csv_path)
    df.insert(0, 'id', range(len(df)))

    df_schema = {
        'id': db.Integer,
        'region': db.String(100),
        'year': db.Integer,
        'cases': db.String(100),
        'deaths': db.String(100),
        'cases_median': db.Integer,
        'cases_min': db.Integer,
        'cases_max': db.Integer,
        'deaths_median': db.Integer,
        'deaths_min': db.Integer,
        'deaths_max': db.Integer,
        'fips': db.String(2),
        'iso': db.String(3),
        'iso2': db.String(2),
        'land_area_kmsq_2012': db.Integer,
        'languages_en_2012':db.String(100),
        'who_region': db.String(100),
        'world_bank_income_group': db.String(100)
    }

    engine = db.engines['malaria_db']

    df.to_sql(
        Malaria.__tablename__, 
        engine, 
        if_exists='replace', 
        index=False,
        dtype=df_schema)

    query = "ALTER TABLE malaria ADD PRIMARY KEY (id);"
    with engine.connect() as conn:
        conn.execute(text(query))

# NOTE: This route is needed for the default EB health check route
@app.route('/')  
def home():
    return "Ok"

### Reset database ###

@app.route('/api/reset/malaria/', methods=['PUT'])
def reset_malaria_db():
    engine = db.engines['malaria_db']
    if engine:
        metadata = db.MetaData()
        metadata.reflect(bind=engine)
        metadata.drop_all(bind=engine)
        metadata.create_all(bind=engine)
        import_malaria_csv()
        return "Successfully reset the malaria database"
    else:
        return "Error resetting the malaria database", 501

### Malaria resource ###

@app.route('/api/malaria/filter')   # with pagination
def filter_malaria():
    region = request.args.get('region')  # takes region from query parameters
    year = request.args.get('year')  
    who_region = request.args.get('who_region')
    page = request.args.get('page', 1, type=int)  # takes page number from query parameters
    per_page = request.args.get('per_page', 10, type=int)
    iso = request.args.get('iso')

    query = Malaria.query
    url = '/api/malaria/filter?'

    if region:
        region_list = region.lower().split(',')
        query = query.filter(func.lower(Malaria.region).in_(region_list))
        url += '&' if url[-1] != '?' else ''
        url += f'region={region}'
    if year:
        year_list = year.split(',')
        query = query.filter(Malaria.year.in_(year_list))
        url += '&' if url[-1] != '?' else ''
        url += f'year={year}'
    if who_region:
        who_region_list = who_region.lower().split(',')
        query = query.filter(func.lower(Malaria.who_region).in_(who_region_list))
        url += '&' if url[-1] != '?' else ''
        url += f'who_region={who_region}'
    if iso:
        iso_list = iso.upper().split(',')
        query = query.filter(Malaria.iso.in_(iso_list))
        url += '&' if url[-1] != '?' else ''
        url += f'iso={iso}'

    # paginates the filtered query
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    malaria_data = [malaria.serialize() for malaria in pagination.items]

    url += '&' if url[-1] != '?' else ''
    next_url = url + f'page={pagination.next_num}&per_page={pagination.per_page}'
    prev_url = url + f'page={pagination.prev_num}&per_page={pagination.per_page}'
    current_url = url + f'page={pagination.page}&per_page={pagination.per_page}'

    return jsonify({
        'malaria_data': malaria_data,
        'previous_page': prev_url,
        'next_page': next_url,
        'current_page': current_url,
        'total_pages': pagination.pages,
        'total_items': pagination.total
    })

@app.route('/api/malaria/') # without pagination
def get_all_malaria():
    malaria_list = Malaria.query.all()
    return jsonify([malaria.serialize() for malaria in malaria_list])

@app.route('/api/malaria/<int:id>/')
def get_malaria_by_id(id):
    malaria = db.session.get(Malaria, id)

    if malaria:
        return jsonify(malaria.serialize())
    else:
        return "Malaria data not found", 404

@app.route('/api/malaria/iso/')
def get_all_malaria_iso():
    iso_list = db.session.query(Malaria.iso).distinct().order_by(Malaria.iso).all()
    return jsonify([iso[0] for iso in iso_list])

@app.route('/api/malaria/iso/<string:iso>')
def get_malaria_by_iso(iso):
    malaria = Malaria.query.filter_by(iso=iso.upper()).first()
    
    if malaria:
        return jsonify(malaria.serialize())
    else:
        return "Malaria data not found", 404

### Routes for E6156 requirements (NOT to be consumed) ###

@app.route('/api/malaria/<int:id>/', methods=['DELETE'])
def delete_malaria(id):
    malaria = db.session.get(Malaria, id)

    if malaria:
        db.session.delete(malaria)
        try:
            db.session.commit()
            return "Successfully deleted malaria data"
        except (IntegrityError, SQLAlchemyError):
            db.session.rollback()
            return "Error deleting malaria data", 501
    else:
        return "Malaria data not found", 404

@app.route('/api/malaria/<int:id>/', methods=['PUT'])
def update_malaria(id):
    malaria = db.session.get(Malaria, id)

    if malaria:
        new_malaria = request.get_json()
        malaria.region = new_malaria.get('region', malaria.region)
        malaria.year = new_malaria.get('year', malaria.year)
        malaria.cases = new_malaria.get('cases', malaria.cases)
        malaria.deaths = new_malaria.get('deaths', malaria.deaths)
        malaria.cases_median = new_malaria.get('cases_median', malaria.cases_median)
        malaria.cases_min = new_malaria.get('cases_min', malaria.cases_min)
        malaria.cases_max = new_malaria.get('cases_max', malaria.cases_max)
        malaria.deaths_median = new_malaria.get('deaths_median', malaria.deaths_median)
        malaria.deaths_min = new_malaria.get('deaths_min', malaria.deaths_min)
        malaria.deaths_max = new_malaria.get('deaths_max', malaria.deaths_max)
        malaria.fips = new_malaria.get('fips', malaria.fips)
        malaria.iso = new_malaria.get('iso', malaria.iso)
        malaria.iso2 = new_malaria.get('iso2', malaria.iso2)
        malaria.land_area_kmsq_2012 = new_malaria.get('land_area_kmsq_2012', malaria.land_area_kmsq_2012)
        malaria.languages_en_2012 = new_malaria.get('languages_en_2012', malaria.languages_en_2012)
        malaria.who_region = new_malaria.get('who_region', malaria.who_region)
        malaria.world_bank_income_group = new_malaria.get('world_bank_income_group', malaria.world_bank_income_group)

        try:
            db.session.commit()
            return "Successfully updated malaria data"
        except (IntegrityError, SQLAlchemyError):
            db.session.rollback()
            return "Error updating malaria data", 501
    else:
        return "Malaria data not found", 404

@app.route('/api/malaria/', methods=['POST'])
def add_malaria():
    new_malaria_data = request.get_json()

    new_malaria = Malaria(
        region=new_malaria_data.get('region'),
        year=new_malaria_data.get('year'),
        cases=new_malaria_data.get('cases'),
        deaths=new_malaria_data.get('deaths'),
        cases_median=new_malaria_data.get('cases_median'),
        cases_min=new_malaria_data.get('cases_min'),
        cases_max=new_malaria_data.get('cases_max'),
        deaths_min=new_malaria_data.get('deaths_min'),
        deaths_max=new_malaria_data.get('deaths_max'),
        fips=new_malaria_data.get('fips'),
        iso=new_malaria_data.get('iso'),
        iso2=new_malaria_data.get('iso2'),
        land_area_kmsq_2012=new_malaria_data.get('land_area_kmsq_2012'),
        languages_en_2012=new_malaria_data.get('languages_en_2012'),
        who_region=new_malaria_data.get('who_region'),
        world_bank_income_group=new_malaria_data.get('world_bank_income_group')
    )

    db.session.add(new_malaria)
    try:
        db.session.commit()
        return "Successfully added malaria data"
    except (IntegrityError, SQLAlchemyError):
        db.session.rollback()
        return "Error adding malaria data", 501

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        import_malaria_csv()

    app.run(debug=True, port=7071)
