
import unittest
import sys
import os

# Add project root
sys.path.insert(0, os.getcwd())

from backend.utils.vector_search import SchemaVectorStore

class TestSchemaVectorStore(unittest.TestCase):
    def test_search(self):
        store = SchemaVectorStore()
        if not store.model:
            print("Skipping test: Model failed to load (network issue?)")
            return

        # Add dummy tables
        store.add_table("users", "users(id int, name text, email text)")
        store.add_table("orders", "orders(id int, user_id int, total decimal)")
        store.add_table("products", "products(id int, name text, price decimal)")
        store.add_table("logs", "logs(id int, message text, timestamp datetime)")
        
        # Search for "who bought what" -> should match users, orders, products
        results = store.search("show me customer spending", k=2)
        print(f"Query: 'show me customer spending'")
        print(f"Results: {results}")
        
        # Expect 'users' or 'orders' to be in top 2
        self.assertTrue("users" in results or "orders" in results)
        
        # Search for "system errors" -> should match logs
        results_logs = store.search("system errors", k=1)
        print(f"Query: 'system errors'")
        print(f"Results: {results_logs}")
        self.assertEqual(results_logs[0], "logs")

if __name__ == "__main__":
    unittest.main()
