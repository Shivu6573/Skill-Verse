from app import create_app, mongo

app = create_app(seed_data_flag=False)
with app.app_context():
    result = mongo.db.users.delete_many({
        "email": {"$regex": r"^testuser_.*@example\.com$"},
        "name": {"$regex": r"^Smoke Tester"}
    })
    print('deleted', result.deleted_count, 'test users')
