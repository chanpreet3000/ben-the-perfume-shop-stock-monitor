import os
from datetime import datetime
from typing import List, Optional
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database as MongoDatabase
from pymongo.errors import DuplicateKeyError, PyMongoError
from Logger import Logger

load_dotenv()


class DatabaseManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True

        # Initialize database connection
        self.mongo_uri = os.getenv('MONGODB_URI')
        self.db_name = os.getenv('MONGODB_DB_NAME')
        if not self.mongo_uri or not self.db_name:
            raise ValueError("MongoDB URI not found in environment variables")

        self.client: Optional[MongoClient] = None
        self.db: Optional[MongoDatabase] = None

        # Collection names
        self.notification_channels_collection = 'notification_channels'
        self.watch_products_collection = 'watch_products'

        # Connect to database
        self._connect()

        # Create indexes
        self._create_indexes()

    def _connect(self) -> None:
        """Establish connection to MongoDB"""
        try:
            Logger.info("Connecting to MongoDB...")
            self.client = MongoClient(self.mongo_uri)
            self.db = self.client[self.db_name]
            Logger.info("Successfully connected to MongoDB")
        except PyMongoError as e:
            Logger.critical("Failed to connect to MongoDB", e)
            raise

    def _create_indexes(self) -> None:
        """Create necessary indexes for collections"""
        try:
            # Create unique index for channel_id
            self.db[self.notification_channels_collection].create_index(
                "channel_id", unique=True
            )
            # Create unique index for product_url
            self.db[self.watch_products_collection].create_index(
                "product_url", unique=True
            )
            Logger.info("Database indexes created successfully")
        except PyMongoError as e:
            Logger.error("Failed to create indexes", e)
            raise

    def add_discord_channel(self, channel_id: str) -> bool:
        """
        Add a Discord channel ID to notification_channels collection
        Returns True if successful, False if channel already exists
        """
        try:
            result = self.db[self.notification_channels_collection].insert_one({
                "channel_id": channel_id,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            })
            Logger.info(f"Added Discord channel: {channel_id}")
            return True
        except DuplicateKeyError:
            Logger.warn(f"Discord channel already exists: {channel_id}")
            return False
        except PyMongoError as e:
            Logger.error(f"Failed to add Discord channel: {channel_id}", e)
            raise

    def remove_discord_channel(self, channel_id: str) -> bool:
        """
        Remove a Discord channel ID from notification_channels collection
        Returns True if successful, False if channel doesn't exist
        """
        try:
            result = self.db[self.notification_channels_collection].delete_one({
                "channel_id": channel_id
            })
            if result.deleted_count > 0:
                Logger.info(f"Removed Discord channel: {channel_id}")
                return True
            Logger.warn(f"Discord channel not found: {channel_id}")
            return False
        except PyMongoError as e:
            Logger.error(f"Failed to remove Discord channel: {channel_id}", e)
            raise

    def add_watch_product(self, product_url: str) -> bool:
        """
        Add a product URL to watch_products collection
        Returns True if successful, False if product already exists
        """
        try:
            result = self.db[self.watch_products_collection].insert_one({
                "product_url": product_url,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            })
            Logger.info(f"Added watch product: {product_url}")
            return True
        except DuplicateKeyError:
            Logger.warn(f"Product URL already exists: {product_url}")
            return False
        except PyMongoError as e:
            Logger.error(f"Failed to add product URL: {product_url}", e)
            raise

    def remove_watch_product(self, product_url: str) -> bool:
        """
        Remove a product URL from watch_products collection
        Returns True if successful, False if product doesn't exist
        """
        try:
            result = self.db[self.watch_products_collection].delete_one({
                "product_url": product_url
            })
            if result.deleted_count > 0:
                Logger.info(f"Removed watch product: {product_url}")
                return True
            Logger.warn(f"Product URL not found: {product_url}")
            return False
        except PyMongoError as e:
            Logger.error(f"Failed to remove product URL: {product_url}", e)
            raise

    def get_all_watch_products(self) -> List[str]:
        """Return all product URLs from watch_products collection"""
        try:
            products = self.db[self.watch_products_collection].find({}, {"product_url": 1, "_id": 0})
            return [product["product_url"] for product in products]
        except PyMongoError as e:
            Logger.error("Failed to fetch watch products", e)
            raise

    def get_all_notification_channels(self) -> List[str]:
        """Return all channel IDs from notification_channels collection"""
        try:
            channels = self.db[self.notification_channels_collection].find({}, {"channel_id": 1, "_id": 0})
            return [channel["channel_id"] for channel in channels]
        except PyMongoError as e:
            Logger.error("Failed to fetch notification channels", e)
            raise

    def close(self):
        """Close MongoDB connection when object is destroyed"""
        if self.client:
            self.client.close()
            Logger.info("MongoDB connection closed")
