
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def check_locations():
    try:
        client = AsyncIOMotorClient('mongodb://localhost:27017')
        db = client['slep_llanquihue']
        collection = db.establishments
        
        total = await collection.count_documents({})
        with_location = await collection.count_documents({"location": {"$exists": True, "$ne": None}})
        
        print(f"Total Establishments: {total}")
        print(f"Establishments with location: {with_location}")
        
        cursor = collection.find({"location": {"$exists": True}}).limit(5)
        samples = await cursor.to_list(length=5)
        
        for s in samples:
            print(f"RBD: {s.get('rbd')} | Location: {s.get('location')}")
    except Exception as e:
        print(f"Connection Error: {e}")

if __name__ == '__main__':
    asyncio.run(check_locations())
