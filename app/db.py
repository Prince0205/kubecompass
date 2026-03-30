from pymongo import MongoClient
from app.config import MONGO_URI, DB_NAME

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

users = db.users
clusters = db.clusters
namespace_requests = db.namespace_requests
audit_logs = db["audit_logs"]
resource_history = db["resource_history"]
