"""
test_FM01_fake_mongo_semantics.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Verifica el doble en memoria (tests/fake_mongo.py) contra la semántica de MongoDB que los
tests de la feature de usuarios dan por cierta. Si el doble miente, esos tests mienten.
"""
import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from tests.fake_mongo import FakeDatabase


@pytest.mark.asyncio
async def test_FM01_unique_index_raises_real_duplicate_key_error():
    col = FakeDatabase().users
    await col.create_index("email", unique=True)
    await col.insert_one({"email": "a@x.cl"})
    with pytest.raises(DuplicateKeyError):
        await col.insert_one({"email": "a@x.cl"})


@pytest.mark.asyncio
async def test_FM01_partial_unique_index_ignores_documents_without_the_field():
    col = FakeDatabase().users
    await col.create_index("email", unique=True, partialFilterExpression={"email": {"$type": "string"}})
    await col.insert_one({"username": "admin"})
    await col.insert_one({"username": "otro"})          # sin email: no choca
    await col.insert_one({"email": "a@x.cl"})
    with pytest.raises(DuplicateKeyError):
        await col.insert_one({"email": "a@x.cl"})


@pytest.mark.asyncio
async def test_FM01_unique_index_also_guards_updates():
    col = FakeDatabase().users
    await col.create_index("email", unique=True)
    await col.insert_one({"email": "a@x.cl"})
    r = await col.insert_one({"email": "b@x.cl"})
    with pytest.raises(DuplicateKeyError):
        await col.update_one({"_id": r.inserted_id}, {"$set": {"email": "a@x.cl"}})


@pytest.mark.asyncio
async def test_FM01_array_equality_and_dotted_paths_follow_mongo_rules():
    col = FakeDatabase().users
    await col.insert_one({"positions": ["DOCENTE", "PIE_ENCARGADO"], "access": [{"platform_id": "datos", "role": "editor"}]})
    assert await col.count_documents({"positions": "DOCENTE"}) == 1       # escalar dentro del array
    assert await col.count_documents({"positions": "DIRECTOR"}) == 0
    assert await col.count_documents({"access.platform_id": "datos"}) == 1
    assert await col.count_documents({"access": {"$elemMatch": {"platform_id": "datos", "role": "editor"}}}) == 1
    assert await col.count_documents({"access": {"$elemMatch": {"platform_id": "datos", "role": "admin"}}}) == 0


@pytest.mark.asyncio
async def test_FM01_operators_and_conditional_update():
    col = FakeDatabase().tokens
    r = await col.insert_one({"used_at": None, "n": 5, "s": "Hola"})
    assert await col.count_documents({"n": {"$gt": 3, "$lt": 9}}) == 1
    assert await col.count_documents({"s": {"$regex": "^hola$", "$options": "i"}}) == 1
    assert await col.count_documents({"missing": {"$exists": False}}) == 1
    # canje atómico: el segundo intento no coincide con el filtro condicional
    first = await col.update_one({"_id": r.inserted_id, "used_at": None}, {"$set": {"used_at": "ya"}})
    second = await col.update_one({"_id": r.inserted_id, "used_at": None}, {"$set": {"used_at": "otra"}})
    assert (first.matched_count, second.matched_count) == (1, 0)


@pytest.mark.asyncio
async def test_FM01_find_sort_skip_limit_projection_and_unsupported_operator():
    col = FakeDatabase().units
    for i, name in enumerate(["c", "a", "b"]):
        await col.insert_one({"name": name, "order": i, "extra": 1})
    docs = await col.find({}, {"name": 1}).sort("name", 1).skip(1).limit(1).to_list()
    assert [d["name"] for d in docs] == ["b"] and "extra" not in docs[0]
    with pytest.raises(NotImplementedError):
        await col.count_documents({"$where": "1"})
