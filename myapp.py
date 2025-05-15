from recon.app import Recon, Model, ModelMeta, Request, Response

app = Recon(db_path='app.db')

# Define a model
class User(Model):
    id = ('INTEGER PRIMARY KEY AUTOINCREMENT',)
    name = ('TEXT',)
    email = ('TEXT',)

User.create_table()

@app.route('/')
def index(req):
    users = User.all()
    items = ''.join(f"<li>{u.name} ({u.email})</li>" for u in users)
    return f"<h1>User List</h1><ul>{items}</ul>"

@app.route('/add/<name>/<email>')
def add(req, name, email):
    u = User(name=name, email=email)
    u.save()
    return '<p>User added!</p><a href="/">Back</a>'

@app.route("/users", methods=["POST"])
def create_user(req):
    data = dict(kv.split("=") for kv in req.query.split("&") if kv)
    u = User(**data)
    u.save()
    return Response(f"Created user {u.id}", status="201 Created")
