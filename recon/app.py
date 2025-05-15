import re, sqlite3, threading, argparse, sys, importlib.util
from wsgiref.simple_server import make_server

# ======= ORM Component =======
class Database:
    """Thread-safe SQLite connection manager."""
    _instance_lock = threading.Lock()

    def __init__(self, db_path=':memory:'):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()

    def execute(self, query, params=None):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(query, params or [])
            self.conn.commit()
            return cur

_db = None

def init_db(path=':memory:'):
    global _db
    if _db is None:
        _db = Database(path)
    return _db

class ModelMeta(type):
    def __new__(cls, name, bases, attrs):
        if name == 'Model':
            return super().__new__(cls, name, bases, attrs)
        # collect fields defined as tuple or str
        fields = {k: v for k, v in attrs.items() if isinstance(v, (tuple, str))}
        attrs['_fields'] = fields
        attrs['__tablename__'] = name.lower()
        return super().__new__(cls, name, bases, attrs)

class Model(metaclass=ModelMeta):
    def __init__(self, **kwargs):
        for f in self._fields:
            setattr(self, f, kwargs.get(f))

    @classmethod
    def create_table(cls):
        cols = []
        for name, type_def in cls._fields.items():
            if isinstance(type_def, tuple):
                # join tuple elements: type and constraints
                col_def = f"{name} {' '.join(type_def)}"
            else:
                col_def = f"{name} {type_def}"
            cols.append(col_def)
        sql = f"CREATE TABLE IF NOT EXISTS {cls.__tablename__} ({', '.join(cols)});"
        init_db().execute(sql)

    def save(self):
        fields = list(self._fields)
        placeholders = ','.join(['?'] * len(fields))
        sql = f"INSERT INTO {self.__tablename__} ({', '.join(fields)}) VALUES ({placeholders});"
        vals = [getattr(self, f) for f in fields]
        init_db().execute(sql, vals)

    @classmethod
    def all(cls):
        cur = init_db().execute(f"SELECT * FROM {cls.__tablename__};")
        return [cls(**dict(row)) for row in cur.fetchall()]

# ======= HTTP Components =======
class Request:
    def __init__(self, env):
        self.method = env['REQUEST_METHOD']
        self.path = env['PATH_INFO']
        self.query = env['QUERY_STRING']
        self.environ = env

class Response:
    def __init__(self, body='', status='200 OK', headers=None):
        self.body = body
        self.status = status
        self.headers = headers or [('Content-Type', 'text/html')]

    def __iter__(self):
        yield self.body.encode()

# ======= Framework =======
class Recon:
    def __init__(self, db_path=':memory:'):
        self.routes = []
        init_db(db_path)

    def route(self, path, methods=['GET']):
        pat = re.sub(r"<(?P<n>[^>]+)>", r"(?P<\g<n>>[^/]+)", path)
        regex = re.compile(f"^{pat}$")
        def dec(fn):
            self.routes.append((regex, methods, fn))
            return fn
        return dec

    def __call__(self, env, start):
        req = Request(env)
        for regex, methods, fn in self.routes:
            m = regex.match(req.path)
            if m and req.method in methods:
                result = fn(req, **m.groupdict())
                if isinstance(result, Response):
                    start(result.status, result.headers)
                    return result
                start('200 OK', [('Content-Type','text/html')])
                return [result.encode()]
        start('404 Not Found', [('Content-Type','text/plain')])
        return [b'Not Found']

    def run(self, host='127.0.0.1', port=5000):
        srv = make_server(host, port, self)
        print(f"Recon running at http://{host}:{port}")
        srv.serve_forever()

# ======= CLI Entrypoint =======
def main():
    p = argparse.ArgumentParser(prog='recon')
    p.add_argument('app', help='Path to your app .py file')
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=5000)
    args = p.parse_args()

    spec = importlib.util.spec_from_file_location('mod', args.app)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    app = getattr(mod, 'app', None)
    if not app:
        print(f"Error: 'app' instance not found in {args.app}")
        sys.exit(1)

    app.run(host=args.host, port=args.port)

if __name__ == '__main__':
    main()