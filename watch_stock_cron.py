import discord

from datetime import datetime
from DatabaseManager import DatabaseManager
from Logger import Logger
from utils import fetch_product_data


async def watch_stock_cron(client: discord.Client):
    try:
        db_manager = DatabaseManager()
        watched_products = db_manager.get_all_watch_products()

        if not watched_products:
            Logger.warn("No products currently being watched")
            return

        Logger.info(f"Starting stock check for {len(watched_products)} watched products at {datetime.utcnow()}")

        for product_url in watched_products:
            try:
                Logger.info(f"Checking stock for product: {product_url}")

                # Fetch product data and create embed
                embed, product_data = await fetch_product_data(product_url)

                if product_data is None:
                    Logger.warn(f"Failed to fetch product data for URL: {product_url}. Skipping...")
                    continue

                option_to_watch = None
                for opt in product_data.options:
                    if opt.product_code == product_data.product_code:
                        option_to_watch = opt
                        break

                Logger.info(f"Found product option to watch ", option_to_watch.to_dict())

                if option_to_watch is None:
                    Logger.warn(f"Could not find product option to watch for URL: {product_url}. Skipping...")
                    continue

                if option_to_watch.is_in_stock:
                    Logger.info(f"Product is now back in stock: {product_url}")

                    await notify_users(
                        client,
                        embed,
                        f'@here Product is now in stock!'
                    )

                    if db_manager.remove_watch_product(product_url):
                        Logger.info(f"Successfully removed in-stock product from watch list: {product_url}")
                    else:
                        Logger.warn(f"Failed to remove product from watch list: {product_url}")
                else:
                    Logger.info(f"Product still out of stock: {product_url}")

            except Exception as e:
                Logger.error(f"Error processing product {product_url}", e)
                continue

    except Exception as e:
        Logger.error(f"Critical error in watch_stock_cron", e)
        raise e


async def notify_users(client: discord.Client, embed: discord.Embed, message: str):
    try:
        Logger.info("Sending notifications to all channels")
        db_manager = DatabaseManager()
        channel_ids = db_manager.get_all_notification_channels()

        if not channel_ids:
            Logger.warn("No notification channels configured")
            return

        Logger.info(f"Attempting to send notifications to {len(channel_ids)} channels")

        for channel_id in channel_ids:
            try:
                channel = client.get_channel(int(channel_id))

                if not channel:
                    Logger.error(f"Could not find Discord channel with ID: {channel_id}")
                    continue

                Logger.info(f"Sending notification to channel {channel_id}")
                Logger.debug(f"Message content: {message[:100]}...")

                await channel.send(
                    content=message,
                    embed=embed if embed else None
                )
                Logger.info(f"Successfully sent notification to channel {channel_id}")
            except Exception as e:
                Logger.error(f"Error sending notification to channel {channel_id}", e)

        Logger.info("Finished sending notifications")
    except Exception as e:
        Logger.error("Critical error in notify_users", e)
        raise e
