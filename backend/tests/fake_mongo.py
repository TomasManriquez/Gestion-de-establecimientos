"""
fake_mongo.py — MongoDB en memoria para los tests de reglas de negocio.

Implementa el subconjunto de la API de Motor que usan los services de esta feature:
insert_one/insert_many, find_one, find (sort/skip/limit/to_list), count_documents,
update_one/update_many ($set, $unset, $push, $pull, $setOnInsert, upsert),
find_one_and_update, delete_one/delete_many y create_index con `unique` y
`partialFilterExpression`. Los índices únicos lanzan el `DuplicateKeyError` real de pymongo.

Operadores de consulta: igualdad (con la semántica de arrays de Mongo), $eq, $ne, $in, $nin,
$gt, $gte, $lt, $lte, $exists, $type (string/null), $regex/$options, $not, $elemMatch, $or,
$and. No es MongoDB: lo que no está aquí lanza NotImplementedError para que un test no
pase por accidente con una consulta que no se simuló.
"""
import copy
import re
from types import SimpleNamespace

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

_MISSING = object()


def _get_path(doc, path):
    """Devuelve la lista de valores candidatos de un path con puntos (recorre arrays)."""
    values = [doc]
    for part in path.split("."):
        nxt = []
        for v in values:
            if isinstance(v, dict):
                if part in v:
                    nxt.append(v[part])
            elif isinstance(v, list):
                if part.isdigit():
                    idx = int(part)
                    if idx < len(v):
                        nxt.append(v[idx])
                else:
                    for item in v:
                        if isinstance(item, dict) and part in item:
                            nxt.append(item[part])
        values = nxt
    return values


def _flatten(values):
    out = []
    for v in values:
        if isinstance(v, list):
            out.extend(v)
            out.append(v)  # un array también iguala a otro array completo
        else:
            out.append(v)
    return out


def _type_ok(value, name):
    if name == "string":
        return isinstance(value, str)
    if name == "null":
        return value is None
    if name == "objectId":
        return isinstance(value, ObjectId)
    raise NotImplementedError(f"$type {name}")


def _cond_matches(candidates, cond, path_exists):
    flat = _flatten(candidates)
    if isinstance(cond, dict) and cond and all(k.startswith("$") for k in cond):
        for op, arg in cond.items():
            if op == "$eq":
                ok = arg in flat if flat else arg is None
            elif op == "$ne":
                ok = arg not in flat
            elif op == "$in":
                ok = any(v in arg for v in flat) or (not flat and None in arg)
            elif op == "$nin":
                ok = not any(v in arg for v in flat)
            elif op in ("$gt", "$gte", "$lt", "$lte"):
                def cmp(v):
                    try:
                        return {"$gt": v > arg, "$gte": v >= arg, "$lt": v < arg, "$lte": v <= arg}[op]
                    except TypeError:
                        return False
                ok = any(cmp(v) for v in flat)
            elif op == "$exists":
                ok = path_exists == bool(arg)
            elif op == "$type":
                ok = any(_type_ok(v, arg) for v in flat)
            elif op == "$regex":
                flags = re.IGNORECASE if "i" in cond.get("$options", "") else 0
                ok = any(isinstance(v, str) and re.search(arg, v, flags) for v in flat)
            elif op == "$options":
                continue
            elif op == "$not":
                ok = not _cond_matches(candidates, arg, path_exists)
            elif op == "$elemMatch":
                ok = any(isinstance(item, dict) and _match(item, arg)
                         for v in candidates if isinstance(v, list) for item in v)
            else:
                raise NotImplementedError(f"operador de consulta {op}")
            if not ok:
                return False
        return True
    # igualdad
    if cond is None:
        return not flat or None in flat
    return cond in flat


def _match(doc, filt):
    for key, cond in (filt or {}).items():
        if key == "$or":
            if not any(_match(doc, f) for f in cond):
                return False
        elif key == "$and":
            if not all(_match(doc, f) for f in cond):
                return False
        elif key.startswith("$"):
            raise NotImplementedError(f"operador de nivel superior {key}")
        else:
            candidates = _get_path(doc, key)
            if not _cond_matches(candidates, cond, bool(candidates)):
                return False
    return True


def _set_path(doc, path, value):
    parts = path.split(".")
    cur = doc
    for p in parts[:-1]:
        if isinstance(cur, list):
            cur = cur[int(p)]
        else:
            cur = cur.setdefault(p, {})
    if isinstance(cur, list):
        cur[int(parts[-1])] = value
    else:
        cur[parts[-1]] = value


def _unset_path(doc, path):
    parts = path.split(".")
    cur = doc
    for p in parts[:-1]:
        cur = cur.get(p) if isinstance(cur, dict) else None
        if cur is None:
            return
    if isinstance(cur, dict):
        cur.pop(parts[-1], None)


def _apply_update(doc, update, inserting=False):
    before = copy.deepcopy(doc)
    for op, fields in update.items():
        if op == "$set":
            for k, v in fields.items():
                _set_path(doc, k, copy.deepcopy(v))
        elif op == "$unset":
            for k in fields:
                _unset_path(doc, k)
        elif op == "$setOnInsert":
            if inserting:
                for k, v in fields.items():
                    _set_path(doc, k, copy.deepcopy(v))
        elif op == "$push":
            for k, v in fields.items():
                cur = _get_path(doc, k)
                if cur and isinstance(cur[0], list):
                    cur[0].append(copy.deepcopy(v))
                else:
                    _set_path(doc, k, [copy.deepcopy(v)])
        elif op == "$pull":
            for k, v in fields.items():
                cur = _get_path(doc, k)
                if cur and isinstance(cur[0], list):
                    cur[0][:] = [x for x in cur[0] if not (_match(x, v) if isinstance(x, dict) and isinstance(v, dict) else x == v)]
        else:
            raise NotImplementedError(f"operador de actualización {op}")
    return doc != before


def _project(doc, projection):
    if not projection:
        return copy.deepcopy(doc)
    include = {k for k, v in projection.items() if v and k != "_id"}
    exclude = {k for k, v in projection.items() if not v and k != "_id"}
    if include:
        out = {}
        for k in include:
            vals = _get_path(doc, k)
            if vals:
                _set_path(out, k, copy.deepcopy(vals[0]))
        if projection.get("_id", 1):
            out["_id"] = doc["_id"]
        return out
    out = copy.deepcopy(doc)
    for k in exclude:
        _unset_path(out, k)
    if "_id" in projection and not projection["_id"]:
        out.pop("_id", None)
    return out


class _Cursor:
    def __init__(self, docs, projection=None):
        self._docs = docs
        self._projection = projection
        self._skip = 0
        self._limit = None
        self._it = None

    def sort(self, key_or_list, direction=1):
        keys = key_or_list if isinstance(key_or_list, list) else [(key_or_list, direction)]
        for key, d in reversed(keys):
            def k(doc, key=key):
                v = _get_path(doc, key)
                v = v[0] if v else None
                return (v is not None, v if v is not None else 0)
            self._docs = sorted(self._docs, key=k, reverse=(d == -1))
        return self

    def skip(self, n):
        self._skip = n
        return self

    def limit(self, n):
        self._limit = n or None
        return self

    def _final(self):
        docs = self._docs[self._skip:]
        if self._limit is not None:
            docs = docs[: self._limit]
        return [_project(d, self._projection) for d in docs]

    def __aiter__(self):
        self._it = iter(self._final())
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration

    async def to_list(self, length=None):
        docs = self._final()
        return docs if length is None else docs[:length]


class FakeCollection:
    def __init__(self, name):
        self.name = name
        self.docs = []
        self._unique = []  # (keys, partialFilterExpression)
        self.calls = []    # nombres de operaciones de escritura, para asertar en tests

    # ── índices ──
    async def create_index(self, keys, unique=False, partialFilterExpression=None, **kwargs):
        if isinstance(keys, str):
            keys = [(keys, 1)]
        if unique:
            spec = ([k for k, _ in keys], partialFilterExpression)
            if spec not in self._unique:
                self._unique.append(spec)
        return "ix_" + "_".join(k for k, _ in keys)

    def _check_unique(self, candidate, ignore_id=None):
        for keys, partial in self._unique:
            if partial is not None and not _match(candidate, partial):
                continue
            key_vals = [tuple(map(repr, _get_path(candidate, k) or [None])) for k in keys]
            for other in self.docs:
                if other["_id"] == ignore_id or other is candidate:
                    continue
                if partial is not None and not _match(other, partial):
                    continue
                if [tuple(map(repr, _get_path(other, k) or [None])) for k in keys] == key_vals:
                    raise DuplicateKeyError(f"E11000 duplicate key error collection: {self.name} index: {keys}")

    def seed(self, *docs):
        """Carga documentos de forma síncrona (preparación de un test, sin pasar por índices)."""
        for d in docs:
            d = copy.deepcopy(d)
            d.setdefault("_id", ObjectId())
            self.docs.append(d)
        return self

    # ── escritura ──
    async def insert_one(self, doc):
        self.calls.append("insert_one")
        doc = copy.deepcopy(doc)
        doc.setdefault("_id", ObjectId())
        self._check_unique(doc)
        self.docs.append(doc)
        return SimpleNamespace(inserted_id=doc["_id"])

    async def insert_many(self, docs, ordered=True):
        self.calls.append("insert_many")
        ids = []
        for d in docs:
            r = await self.insert_one(d)
            ids.append(r.inserted_id)
        return SimpleNamespace(inserted_ids=ids)

    async def update_one(self, filt, update, upsert=False):
        self.calls.append("update_one")
        for doc in self.docs:
            if _match(doc, filt):
                candidate = copy.deepcopy(doc)
                changed = _apply_update(candidate, update)
                self._check_unique(candidate, ignore_id=doc["_id"])
                doc.clear()
                doc.update(candidate)
                return SimpleNamespace(matched_count=1, modified_count=1 if changed else 0, upserted_id=None)
        if upsert:
            new = {k: v for k, v in filt.items() if not k.startswith("$") and not isinstance(v, dict)}
            _apply_update(new, update, inserting=True)
            new.setdefault("_id", ObjectId())
            self._check_unique(new)
            self.docs.append(new)
            return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=new["_id"])
        return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=None)

    async def update_many(self, filt, update):
        self.calls.append("update_many")
        matched = modified = 0
        for doc in self.docs:
            if _match(doc, filt):
                matched += 1
                candidate = copy.deepcopy(doc)
                if _apply_update(candidate, update):
                    modified += 1
                self._check_unique(candidate, ignore_id=doc["_id"])
                doc.clear()
                doc.update(candidate)
        return SimpleNamespace(matched_count=matched, modified_count=modified)

    async def find_one_and_update(self, filt, update, return_document=False, **kwargs):
        self.calls.append("find_one_and_update")
        for doc in self.docs:
            if _match(doc, filt):
                before = copy.deepcopy(doc)
                candidate = copy.deepcopy(doc)
                _apply_update(candidate, update)
                self._check_unique(candidate, ignore_id=doc["_id"])
                doc.clear()
                doc.update(candidate)
                return copy.deepcopy(doc) if return_document else before
        return None

    async def delete_one(self, filt):
        self.calls.append("delete_one")
        for i, doc in enumerate(self.docs):
            if _match(doc, filt):
                del self.docs[i]
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)

    async def delete_many(self, filt):
        self.calls.append("delete_many")
        keep = [d for d in self.docs if not _match(d, filt)]
        n = len(self.docs) - len(keep)
        self.docs[:] = keep
        return SimpleNamespace(deleted_count=n)

    # ── lectura ──
    async def find_one(self, filt=None, projection=None, sort=None):
        docs = [d for d in self.docs if _match(d, filt or {})]
        if sort:
            docs = (await _Cursor(docs).sort(sort).to_list())  # ya proyectado: sin proyección
        return _project(docs[0], projection) if docs else None

    def find(self, filt=None, projection=None):
        return _Cursor([d for d in self.docs if _match(d, filt or {})], projection)

    async def count_documents(self, filt=None):
        return sum(1 for d in self.docs if _match(d, filt or {}))

    async def distinct(self, key, filt=None):
        seen = []
        for d in self.docs:
            if _match(d, filt or {}):
                for v in _get_path(d, key):
                    for x in (v if isinstance(v, list) else [v]):
                        if x not in seen:
                            seen.append(x)
        return seen


class FakeDatabase:
    def __init__(self):
        self._cols = {}

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return self._cols.setdefault(name, FakeCollection(name))

    def __getitem__(self, name):
        return getattr(self, name)
